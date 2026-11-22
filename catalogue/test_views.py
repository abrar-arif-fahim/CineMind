"""Tests for the catalogue pages: homepage, movie list (search, filters,
pagination) and movie details, plus the database queries behind them."""

import datetime

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import resolve, reverse

from . import views
from .forms import MovieFilterForm
from .models import Genre, Movie

HOME_URL = reverse("catalogue:home")
LIST_URL = reverse("catalogue:movie_list")


def make_movie(title, year=None, genres=(), **extra):
    release_date = datetime.date(year, 6, 1) if year else None
    movie = Movie.objects.create(title=title, release_date=release_date, **extra)
    movie.genres.set(genres)
    return movie


class CatalogueDataMixin:
    """A small catalogue shared by the tests below."""

    @classmethod
    def setUpTestData(cls):
        cls.drama = Genre.objects.create(name="Drama", tmdb_id=18)
        cls.scifi = Genre.objects.create(name="Science Fiction", tmdb_id=878)
        cls.comedy = Genre.objects.create(name="Comedy", tmdb_id=35)  # no movies
        cls.matrix = make_movie("The Matrix", 1999, [cls.scifi], runtime=136,
                                overview="A hacker learns the truth.")
        cls.interstellar = make_movie("Interstellar", 2014, [cls.scifi, cls.drama])
        cls.whiplash = make_movie("Whiplash", 2014, [cls.drama])
        cls.godfather = make_movie("The Godfather", 1972, [cls.drama])
        cls.no_date = make_movie("Untitled Project")


class UrlTests(TestCase):
    def test_url_names_and_paths(self):
        self.assertEqual(HOME_URL, "/")
        self.assertEqual(LIST_URL, "/movies/")
        self.assertEqual(reverse("catalogue:movie_detail", args=[7]), "/movies/7/")

    def test_urls_use_the_right_views(self):
        self.assertEqual(resolve("/").func.view_class, views.HomeView)
        self.assertEqual(resolve("/movies/").func.view_class, views.MovieListView)
        self.assertEqual(resolve("/movies/7/").func.view_class, views.MovieDetailView)

    def test_admin_still_works(self):
        self.assertEqual(self.client.get("/admin/").status_code, 302)  # to login


class MovieFilterFormTests(CatalogueDataMixin, TestCase):
    def titles(self, params):
        movies = MovieFilterForm(params).filter(Movie.objects.all())
        return sorted(movies.values_list("title", flat=True))

    def test_no_options_returns_everything(self):
        self.assertEqual(len(self.titles({})), 5)
        self.assertFalse(MovieFilterForm({}).is_filtered)

    def test_title_search_is_partial_and_case_insensitive(self):
        self.assertEqual(self.titles({"q": "MATR"}), ["The Matrix"])
        self.assertEqual(self.titles({"q": "the"}), ["The Godfather", "The Matrix"])

    def test_title_search_ignores_surrounding_spaces(self):
        self.assertEqual(self.titles({"q": "  whiplash  "}), ["Whiplash"])

    def test_blank_search_returns_everything(self):
        self.assertEqual(len(self.titles({"q": "   "})), 5)

    def test_filter_by_genre(self):
        self.assertEqual(
            self.titles({"genre": self.drama.pk}),
            ["Interstellar", "The Godfather", "Whiplash"],
        )

    def test_filter_by_release_year(self):
        self.assertEqual(self.titles({"year": "2014"}), ["Interstellar", "Whiplash"])

    def test_all_options_combined(self):
        params = {"q": "inter", "genre": self.scifi.pk, "year": "2014"}
        self.assertEqual(self.titles(params), ["Interstellar"])
        self.assertTrue(MovieFilterForm(params).is_filtered)

    def test_invalid_values_are_ignored(self):
        bad_inputs = [
            {"genre": "999"},     # no such genre
            {"genre": "drama"},   # not an id
            {"year": "abc"},      # not a number
            {"year": "99999"},    # out of range
        ]
        for params in bad_inputs:
            with self.subTest(params=params):
                self.assertEqual(len(self.titles(params)), 5)
                self.assertFalse(MovieFilterForm(params).is_filtered)

    def test_one_bad_value_does_not_cancel_the_good_ones(self):
        self.assertEqual(self.titles({"q": "matrix", "year": "abc"}), ["The Matrix"])

    def test_no_match_returns_empty(self):
        self.assertEqual(self.titles({"q": "zzz"}), [])

    def test_genre_filter_returns_each_movie_once(self):
        movies = MovieFilterForm({"genre": self.scifi.pk}).filter(Movie.objects.all())
        self.assertEqual(movies.count(), len(set(movies.values_list("pk", flat=True))))


class HomeViewTests(CatalogueDataMixin, TestCase):
    def test_page_loads_with_template(self):
        response = self.client.get(HOME_URL)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "catalogue/home.html")
        self.assertTemplateUsed(response, "base.html")

    def test_latest_movies_newest_first_and_undated_last(self):
        latest = list(self.client.get(HOME_URL).context["latest_movies"])
        self.assertEqual(latest[0], self.interstellar)  # 2014, then by title
        self.assertEqual(latest[1], self.whiplash)
        self.assertEqual(latest[-1], self.no_date)

    def test_latest_movies_limited_to_eight(self):
        for i in range(10):
            make_movie(f"Extra {i}", 2000 + i)
        latest = self.client.get(HOME_URL).context["latest_movies"]
        self.assertEqual(len(latest), views.LATEST_MOVIES_ON_HOME)

    def test_genres_have_counts_and_skip_empty_ones(self):
        genres = {g.name: g.movie_count for g in self.client.get(HOME_URL).context["genres"]}
        self.assertEqual(genres, {"Drama": 3, "Science Fiction": 2})

    def test_movie_count(self):
        response = self.client.get(HOME_URL)
        self.assertEqual(response.context["movie_count"], 5)
        self.assertContains(response, "5 movies in the catalogue")

    def test_links_to_movies_and_genre_filter(self):
        response = self.client.get(HOME_URL)
        self.assertContains(response, reverse("catalogue:movie_detail", args=[self.matrix.pk]))
        self.assertContains(response, f"/movies/?genre={self.drama.pk}")


class EmptyCatalogueTests(TestCase):
    """FR-12: an empty catalogue must not break any page."""

    def test_home_with_no_movies(self):
        response = self.client.get(HOME_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["movie_count"], 0)
        self.assertContains(response, "The catalogue is empty")

    def test_list_with_no_movies(self):
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["result_count"], 0)
        self.assertEqual(response.context["years"], [])
        self.assertContains(response, "The catalogue is empty")


class MovieListViewTests(CatalogueDataMixin, TestCase):
    def test_page_loads_with_all_movies_sorted_by_title(self):
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "catalogue/movie_list.html")
        titles = [m.title for m in response.context["movies"]]
        self.assertEqual(titles, sorted(titles))
        self.assertEqual(response.context["result_count"], 5)
        self.assertFalse(response.context["is_filtered"])

    def test_search_by_title(self):
        response = self.client.get(LIST_URL, {"q": "matrix"})
        self.assertEqual(list(response.context["movies"]), [self.matrix])
        self.assertEqual(response.context["query"], "matrix")
        self.assertTrue(response.context["is_filtered"])
        self.assertContains(response, 'value="matrix"')

    def test_filter_by_genre(self):
        response = self.client.get(LIST_URL, {"genre": self.scifi.pk})
        self.assertEqual(set(response.context["movies"]), {self.matrix, self.interstellar})
        self.assertEqual(response.context["selected_genre"], self.scifi)
        self.assertContains(response, f'<option value="{self.scifi.pk}" selected>')

    def test_filter_by_year(self):
        response = self.client.get(LIST_URL, {"year": "2014"})
        self.assertEqual(set(response.context["movies"]), {self.interstellar, self.whiplash})
        self.assertEqual(response.context["selected_year"], 2014)
        self.assertContains(response, '<option value="2014" selected>')

    def test_combined_search_and_filters(self):
        response = self.client.get(LIST_URL, {"q": "i", "genre": self.drama.pk, "year": "2014"})
        self.assertEqual(set(response.context["movies"]), {self.interstellar, self.whiplash})
        self.assertEqual(response.context["result_count"], 2)

    def test_no_results_message(self):
        response = self.client.get(LIST_URL, {"q": "zzz"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["result_count"], 0)
        self.assertContains(response, "No movies match your search")

    def test_invalid_filters_show_all_movies(self):
        response = self.client.get(LIST_URL, {"genre": "abc", "year": "abc"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["result_count"], 5)
        self.assertIsNone(response.context["selected_genre"])
        self.assertIsNone(response.context["selected_year"])

    def test_dropdown_options(self):
        context = self.client.get(LIST_URL).context
        self.assertEqual(context["years"], [2014, 1999, 1972])  # unique, newest first
        self.assertEqual([g.name for g in context["genres"]], ["Comedy", "Drama", "Science Fiction"])

    def test_cards_show_genres_and_link_to_details(self):
        response = self.client.get(LIST_URL, {"q": self.interstellar.title})
        self.assertContains(response, '<span class="movie-genre">Drama</span>', html=True)
        self.assertContains(response, '<span class="movie-genre">Science Fiction</span>', html=True)
        detail_url = reverse("catalogue:movie_detail", args=[self.interstellar.pk])
        self.assertContains(response, f'href="{detail_url}"')

    def test_undated_movie_is_listed_but_not_in_year_filter(self):
        self.assertIn(self.no_date, self.client.get(LIST_URL).context["movies"])
        response = self.client.get(LIST_URL, {"year": "1999"})
        self.assertNotIn(self.no_date, response.context["movies"])


class PaginationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.drama = Genre.objects.create(name="Drama")
        for i in range(30):
            make_movie(f"Movie {i:02d}", 2000, [cls.drama] if i < 15 else [])

    def test_twelve_movies_per_page(self):
        response = self.client.get(LIST_URL)
        self.assertEqual(len(response.context["movies"]), views.MOVIES_PER_PAGE)
        self.assertTrue(response.context["is_paginated"])
        self.assertEqual(response.context["page_obj"].paginator.num_pages, 3)

    def test_last_page(self):
        response = self.client.get(LIST_URL, {"page": 3})
        self.assertEqual(len(response.context["movies"]), 6)

    def test_page_past_the_end_shows_last_page(self):
        response = self.client.get(LIST_URL, {"page": 99})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].number, 3)

    def test_invalid_page_shows_first_page(self):
        response = self.client.get(LIST_URL, {"page": "abc"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].number, 1)

    def test_page_links_keep_the_filters(self):
        response = self.client.get(LIST_URL, {"genre": self.drama.pk})
        self.assertEqual(response.context["result_count"], 15)
        self.assertContains(response, f"?genre={self.drama.pk}&amp;page=2")

    def test_no_pagination_when_results_fit_one_page(self):
        response = self.client.get(LIST_URL, {"q": "Movie 01"})
        self.assertFalse(response.context["is_paginated"])
        self.assertNotContains(response, "Next →")


class MovieDetailViewTests(CatalogueDataMixin, TestCase):
    def test_page_shows_movie(self):
        response = self.client.get(reverse("catalogue:movie_detail", args=[self.matrix.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "catalogue/movie_detail.html")
        self.assertEqual(response.context["movie"], self.matrix)
        self.assertContains(response, '<h1 id="movie-title" class="display-5 fw-bold mb-4">The Matrix</h1>', html=True)
        self.assertContains(response, "A hacker learns the truth.")
        self.assertContains(response, "136 min")
        self.assertContains(response, "1 June 1999")
        self.assertContains(response, f"/movies/?genre={self.scifi.pk}")

    def test_unknown_movie_gives_404(self):
        response = self.client.get(reverse("catalogue:movie_detail", args=[99999]))
        self.assertEqual(response.status_code, 404)

    def test_missing_data_shows_fallback_text(self):
        response = self.client.get(reverse("catalogue:movie_detail", args=[self.no_date.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Release date unknown")
        self.assertContains(response, "No overview available yet.")
        self.assertContains(response, ' src="/static/images/poster-placeholder.svg"')

    def test_poster_shown_when_available(self):
        movie = make_movie("With Poster", 2020, poster_path="/abc.jpg")
        response = self.client.get(reverse("catalogue:movie_detail", args=[movie.pk]))
        self.assertContains(response, 'src="https://image.tmdb.org/t/p/w500/abc.jpg"')
        self.assertNotContains(response, ' src="/static/images/poster-placeholder.svg"')


class QueryCountTests(TestCase):
    """The number of database queries must not grow with the number of
    movies shown (no "one query per movie" problem). This keeps pages fast
    with 500 movies (NFR-03)."""

    def count_queries(self, url, params=None):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url, params or {})
        self.assertEqual(response.status_code, 200)
        return len(queries)

    def add_movies(self, count, genres):
        for i in range(count):
            make_movie(f"Movie {Movie.objects.count():03d}", 2000 + i % 5, genres)

    def test_list_page_queries_stay_constant(self):
        genres = [Genre.objects.create(name="Drama"), Genre.objects.create(name="Crime")]
        self.add_movies(2, genres)
        few = self.count_queries(LIST_URL)
        self.add_movies(10, genres)
        many = self.count_queries(LIST_URL)
        self.assertEqual(few, many)
        self.assertLessEqual(many, 6)

    def test_filtered_list_queries_stay_constant(self):
        drama = Genre.objects.create(name="Drama")
        self.add_movies(2, [drama])
        params = {"q": "movie", "genre": drama.pk, "year": "2001"}
        few = self.count_queries(LIST_URL, params)
        self.add_movies(10, [drama])
        self.assertEqual(few, self.count_queries(LIST_URL, params))

    def test_home_page_queries_stay_constant(self):
        genres = [Genre.objects.create(name="Drama")]
        self.add_movies(2, genres)
        few = self.count_queries(HOME_URL)
        self.add_movies(10, genres)
        many = self.count_queries(HOME_URL)
        self.assertEqual(few, many)
        self.assertLessEqual(many, 4)

    def test_detail_page_queries(self):
        movie = make_movie("Detail", 2000, [Genre.objects.create(name="Drama"),
                                            Genre.objects.create(name="Crime")])
        self.assertLessEqual(
            self.count_queries(reverse("catalogue:movie_detail", args=[movie.pk])), 2
        )
