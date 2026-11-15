import datetime
import json
import tempfile
from io import StringIO
from pathlib import Path

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .models import Genre, Movie

MovieGenre = Movie.genres.through  # the catalogue_moviegenre link table


class GenreModelTests(TestCase):
    def test_str_returns_name(self):
        self.assertEqual(str(Genre(name="Drama")), "Drama")

    def test_name_is_unique_ignoring_case(self):
        Genre.objects.create(name="Action")
        with self.assertRaises(ValidationError):
            Genre(name="action").full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Genre.objects.create(name="ACTION")

    def test_tmdb_id_is_unique(self):
        Genre.objects.create(name="Action", tmdb_id=28)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Genre.objects.create(name="Adventure", tmdb_id=28)

    def test_tmdb_id_is_optional(self):
        # Several hand-made genres without a TMDB id must be allowed.
        Genre.objects.create(name="Indie")
        Genre.objects.create(name="Cult")
        self.assertEqual(Genre.objects.filter(tmdb_id__isnull=True).count(), 2)

    def test_genres_are_ordered_by_name(self):
        for name in ["Thriller", "Action", "Drama"]:
            Genre.objects.create(name=name)
        self.assertEqual(
            list(Genre.objects.values_list("name", flat=True)),
            ["Action", "Drama", "Thriller"],
        )


class MovieModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.action = Genre.objects.create(name="Action", tmdb_id=28)
        cls.scifi = Genre.objects.create(name="Science Fiction", tmdb_id=878)
        cls.movie = Movie.objects.create(
            tmdb_id=603,
            title="The Matrix",
            overview="A hacker learns the world is a simulation.",
            release_date=datetime.date(1999, 3, 31),
            runtime=136,
        )
        cls.movie.genres.add(cls.action, cls.scifi)

    def test_str_includes_release_year(self):
        self.assertEqual(str(self.movie), "The Matrix (1999)")

    def test_str_without_release_date_is_just_title(self):
        self.assertEqual(str(Movie(title="Untitled Project")), "Untitled Project")

    def test_release_year(self):
        self.assertEqual(self.movie.release_year, 1999)
        self.assertIsNone(Movie(title="No date").release_year)

    def test_poster_url(self):
        self.assertEqual(Movie(title="A").poster_url, "")
        self.assertEqual(
            Movie(title="B", poster_path="/abc.jpg").poster_url,
            "https://image.tmdb.org/t/p/w500/abc.jpg",
        )
        full_url = "https://example.com/poster.jpg"
        self.assertEqual(Movie(title="C", poster_path=full_url).poster_url, full_url)

    def test_movie_and_genre_are_linked_both_ways(self):
        self.assertQuerySetEqual(
            self.movie.genres.all(), [self.action, self.scifi], ordered=False
        )
        self.assertIn(self.movie, self.action.movies.all())
        self.assertIn(self.movie, self.scifi.movies.all())

    def test_adding_same_genre_twice_stores_one_link(self):
        self.movie.genres.add(self.action)
        self.assertEqual(
            MovieGenre.objects.filter(movie=self.movie, genre=self.action).count(), 1
        )

    def test_link_table_rejects_duplicate_movie_genre_pair(self):
        # unique(movie, genre) from the Stage 1 class diagram.
        self.assertEqual(MovieGenre._meta.db_table, "catalogue_moviegenre")
        with self.assertRaises(IntegrityError), transaction.atomic():
            MovieGenre.objects.create(movie=self.movie, genre=self.action)

    def test_tmdb_id_is_unique(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Movie.objects.create(title="Copy of The Matrix", tmdb_id=603)

    def test_movies_without_tmdb_id_are_allowed(self):
        Movie.objects.create(title="Student Film 1")
        Movie.objects.create(title="Student Film 2")
        self.assertEqual(Movie.objects.filter(tmdb_id__isnull=True).count(), 2)

    def test_title_is_required(self):
        with self.assertRaises(ValidationError) as ctx:
            Movie(title="").full_clean()
        self.assertIn("title", ctx.exception.message_dict)

    def test_runtime_must_be_at_least_one_minute(self):
        with self.assertRaises(ValidationError) as ctx:
            Movie(title="Zero", runtime=0).full_clean()
        self.assertIn("runtime", ctx.exception.message_dict)

    def test_optional_fields_may_be_empty(self):
        movie = Movie(title="Minimal")
        movie.full_clean()  # must not raise
        movie.save()
        self.assertEqual(movie.genres.count(), 0)

    def test_deleting_a_genre_keeps_the_movie(self):
        self.action.delete()
        self.movie.refresh_from_db()
        self.assertEqual(list(self.movie.genres.all()), [self.scifi])

    def test_deleting_a_movie_keeps_its_genres(self):
        self.movie.delete()
        self.assertTrue(Genre.objects.filter(pk=self.action.pk).exists())
        self.assertEqual(MovieGenre.objects.count(), 0)

    def test_timestamps_are_set_automatically(self):
        self.assertIsNotNone(self.movie.created_at)
        self.assertIsNotNone(self.movie.updated_at)

    def test_movies_are_ordered_by_title(self):
        Movie.objects.create(title="Amelie")
        Movie.objects.create(title="Zodiac")
        titles = list(Movie.objects.values_list("title", flat=True))
        self.assertEqual(titles, sorted(titles))


class LoadSampleMoviesCommandTests(TestCase):
    def run_command(self, *args):
        out = StringIO()
        call_command("load_sample_movies", *args, stdout=out)
        return out.getvalue()

    def write_json(self, data):
        tmp = tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        )
        with tmp:
            json.dump(data, tmp)
        self.addCleanup(Path(tmp.name).unlink)
        return tmp.name

    def test_loads_between_10_and_15_movies_with_genres(self):
        output = self.run_command()
        self.assertTrue(10 <= Movie.objects.count() <= 15)
        self.assertEqual(Movie.objects.count(), 15)
        self.assertEqual(Genre.objects.count(), 14)
        self.assertIn("15 created", output)
        self.assertFalse(Movie.objects.filter(genres__isnull=True).exists())
        matrix = Movie.objects.get(tmdb_id=603)
        self.assertEqual(matrix.title, "The Matrix")
        self.assertEqual(
            set(matrix.genres.values_list("name", flat=True)),
            {"Action", "Science Fiction"},
        )

    def test_running_twice_creates_no_duplicates(self):
        self.run_command()
        links_after_first_run = MovieGenre.objects.count()
        output = self.run_command()
        self.assertEqual(Movie.objects.count(), 15)
        self.assertEqual(Genre.objects.count(), 14)
        self.assertEqual(MovieGenre.objects.count(), links_after_first_run)
        self.assertIn("Movies: 0 created, 0 updated, 15 unchanged", output)

    def test_rerun_restores_edited_movie(self):
        self.run_command()
        movie = Movie.objects.get(tmdb_id=603)
        movie.title = "Edited by mistake"
        movie.save()
        movie.genres.clear()

        output = self.run_command()

        movie.refresh_from_db()
        self.assertEqual(movie.title, "The Matrix")
        self.assertEqual(movie.genres.count(), 2)
        self.assertIn("1 updated", output)

    def test_rerun_keeps_movies_added_by_hand(self):
        self.run_command()
        Movie.objects.create(title="Added in the admin")
        self.run_command()
        self.assertTrue(Movie.objects.filter(title="Added in the admin").exists())
        self.assertEqual(Movie.objects.count(), 16)

    def test_links_hand_made_genre_instead_of_duplicating(self):
        hand_made = Genre.objects.create(name="action")  # no TMDB id, lower case
        self.run_command()
        hand_made.refresh_from_db()
        self.assertEqual(hand_made.tmdb_id, 28)
        self.assertEqual(hand_made.name, "Action")
        self.assertEqual(Genre.objects.filter(name__iexact="action").count(), 1)

    def test_custom_file(self):
        path = self.write_json({
            "genres": [{"tmdb_id": 18, "name": "Drama"}],
            "movies": [{"tmdb_id": 1, "title": "Test Movie", "genres": [18]}],
        })
        self.run_command("--file", path)
        movie = Movie.objects.get()
        self.assertEqual(movie.title, "Test Movie")
        self.assertIsNone(movie.release_date)
        self.assertEqual(list(movie.genres.values_list("name", flat=True)), ["Drama"])

    def test_missing_file_raises_error(self):
        with self.assertRaisesMessage(CommandError, "Data file not found"):
            self.run_command("--file", "does-not-exist.json")

    def test_invalid_json_raises_error(self):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        with tmp:
            tmp.write("{ not json")
        self.addCleanup(Path(tmp.name).unlink)
        with self.assertRaisesMessage(CommandError, "not valid UTF-8 JSON"):
            self.run_command("--file", tmp.name)

    def test_unknown_genre_id_raises_error_and_saves_nothing(self):
        path = self.write_json({
            "genres": [{"tmdb_id": 18, "name": "Drama"}],
            "movies": [
                {"tmdb_id": 1, "title": "Good", "genres": [18]},
                {"tmdb_id": 2, "title": "Bad", "genres": [999]},
            ],
        })
        with self.assertRaisesMessage(CommandError, "[999]"):
            self.run_command("--file", path)
        # The whole load is rolled back, including the valid rows.
        self.assertEqual(Movie.objects.count(), 0)
        self.assertEqual(Genre.objects.count(), 0)

    def test_invalid_values_raise_error_and_save_nothing(self):
        bad_movies = [
            {"tmdb_id": 1, "title": "Bad date", "release_date": "31/12/2020"},
            {"tmdb_id": 1, "title": "Zero runtime", "runtime": 0},
            {"tmdb_id": 1, "title": ""},
            {"title": "No TMDB id"},
        ]
        for bad_movie in bad_movies:
            with self.subTest(bad_movie=bad_movie):
                path = self.write_json({"genres": [], "movies": [bad_movie]})
                with self.assertRaises(CommandError):
                    self.run_command("--file", path)
                self.assertEqual(Movie.objects.count(), 0)

    def test_file_without_required_lists_raises_error(self):
        path = self.write_json({"movies": []})
        with self.assertRaisesMessage(CommandError, '"genres" list'):
            self.run_command("--file", path)


class CatalogueAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = get_user_model().objects.create_superuser(
            username="admin", email="admin@example.com", password="test-pass-123"
        )
        cls.drama = Genre.objects.create(name="Drama", tmdb_id=18)
        cls.music = Genre.objects.create(name="Music", tmdb_id=10402)
        cls.movie = Movie.objects.create(
            title="Whiplash", tmdb_id=244786, release_date=datetime.date(2014, 10, 10)
        )
        cls.movie.genres.add(cls.drama, cls.music)
        Movie.objects.create(title="The Godfather", tmdb_id=238).genres.add(cls.drama)

    def setUp(self):
        self.client.force_login(self.admin_user)

    def test_models_are_registered(self):
        self.assertTrue(admin.site.is_registered(Movie))
        self.assertTrue(admin.site.is_registered(Genre))

    def test_movie_list_page(self):
        response = self.client.get(reverse("admin:catalogue_movie_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Whiplash")
        self.assertContains(response, "Drama, Music")
        self.assertContains(response, "2014")

    def test_movie_search(self):
        url = reverse("admin:catalogue_movie_changelist")
        response = self.client.get(url, {"q": "whip"})
        self.assertContains(response, "Whiplash")
        self.assertNotContains(response, "The Godfather")

    def test_movie_filter_by_genre(self):
        url = reverse("admin:catalogue_movie_changelist")
        response = self.client.get(url, {"genres__id__exact": self.music.pk})
        self.assertContains(response, "Whiplash")
        self.assertNotContains(response, "The Godfather")

    def test_movie_add_and_change_pages_load(self):
        add = self.client.get(reverse("admin:catalogue_movie_add"))
        change = self.client.get(
            reverse("admin:catalogue_movie_change", args=[self.movie.pk])
        )
        self.assertEqual(add.status_code, 200)
        self.assertEqual(change.status_code, 200)

    def test_add_movie_through_admin_form(self):
        response = self.client.post(reverse("admin:catalogue_movie_add"), {
            "title": "Get Out",
            "overview": "",
            "genres": [self.drama.pk],
            "release_date": "2017-02-24",
            "runtime": "104",
            "tmdb_id": "419430",
            "poster_path": "",
        })
        self.assertEqual(response.status_code, 302)  # redirect = saved
        movie = Movie.objects.get(tmdb_id=419430)
        self.assertEqual(list(movie.genres.all()), [self.drama])

    def test_genre_list_shows_movie_counts(self):
        response = self.client.get(reverse("admin:catalogue_genre_changelist"))
        self.assertEqual(response.status_code, 200)
        drama_row = response.context["cl"].result_list.get(pk=self.drama.pk)
        self.assertEqual(drama_row._movie_count, 2)

    def test_duplicate_genre_name_shows_form_error(self):
        response = self.client.post(
            reverse("admin:catalogue_genre_add"), {"name": "drama", "tmdb_id": ""}
        )
        self.assertEqual(response.status_code, 200)  # form shown again, not saved
        self.assertContains(response, "A genre with this name already exists.")
        self.assertEqual(Genre.objects.filter(name__iexact="drama").count(), 1)
