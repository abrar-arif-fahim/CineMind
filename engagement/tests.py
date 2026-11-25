"""Tests for ratings and the watchlist: database rules, validation,
permissions (login, POST only, CSRF, own data only) and the pages."""

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from catalogue.models import Movie

from .models import Rating, WatchlistEntry

User = get_user_model()
PASSWORD = "Sunny-Movie-2026"
WATCHLIST_URL = reverse("engagement:watchlist")
LOGIN_URL = reverse("accounts:login")


def rate_url(movie):
    return reverse("engagement:rate_movie", args=[movie.pk])


def delete_rating_url(movie):
    return reverse("engagement:delete_rating", args=[movie.pk])


def add_url(movie):
    return reverse("engagement:add_to_watchlist", args=[movie.pk])


def remove_url(movie):
    return reverse("engagement:remove_from_watchlist", args=[movie.pk])


def message_texts(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


class EngagementTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("burak", password=PASSWORD)
        cls.other = User.objects.create_user("yeasin", password=PASSWORD)
        cls.movie = Movie.objects.create(title="The Matrix")
        cls.movie2 = Movie.objects.create(title="Whiplash")

    def login(self, user=None):
        self.client.force_login(user or self.user)


class UrlTests(TestCase):
    def test_paths(self):
        self.assertEqual(WATCHLIST_URL, "/watchlist/")
        self.assertEqual(reverse("engagement:rate_movie", args=[3]), "/movies/3/rate/")
        self.assertEqual(reverse("engagement:delete_rating", args=[3]), "/movies/3/rate/delete/")
        self.assertEqual(reverse("engagement:add_to_watchlist", args=[3]), "/movies/3/watchlist/add/")
        self.assertEqual(reverse("engagement:remove_from_watchlist", args=[3]), "/movies/3/watchlist/remove/")


# ---------------------------------------------------------------------------
# Models: the rules hold in the database itself (NFR-06)
# ---------------------------------------------------------------------------

class RatingModelTests(EngagementTestCase):
    def test_str(self):
        rating = Rating(user=self.user, movie=self.movie, score=4)
        self.assertEqual(str(rating), "burak rated The Matrix: 4/5")

    def test_one_rating_per_user_and_movie(self):
        Rating.objects.create(user=self.user, movie=self.movie, score=4)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Rating.objects.create(user=self.user, movie=self.movie, score=2)

    def test_different_users_can_rate_the_same_movie(self):
        Rating.objects.create(user=self.user, movie=self.movie, score=4)
        Rating.objects.create(user=self.other, movie=self.movie, score=2)
        self.assertEqual(self.movie.ratings.count(), 2)

    def test_database_rejects_scores_outside_1_to_5(self):
        for score in (0, 6, 100):
            with self.subTest(score=score), self.assertRaises(IntegrityError), transaction.atomic():
                Rating.objects.create(user=self.user, movie=self.movie, score=score)

    def test_validation_rejects_scores_outside_1_to_5(self):
        for score in (0, 6):
            with self.subTest(score=score), self.assertRaises(ValidationError):
                Rating(user=self.user, movie=self.movie, score=score).full_clean()
        Rating(user=self.user, movie=self.movie, score=1).full_clean()
        Rating(user=self.user, movie=self.movie, score=5).full_clean()

    def test_deleting_movie_or_user_deletes_their_ratings(self):
        Rating.objects.create(user=self.user, movie=self.movie, score=4)
        Rating.objects.create(user=self.other, movie=self.movie2, score=3)
        self.movie.delete()
        self.other.delete()
        self.assertEqual(Rating.objects.count(), 0)


class WatchlistModelTests(EngagementTestCase):
    def test_str(self):
        entry = WatchlistEntry(user=self.user, movie=self.movie)
        self.assertEqual(str(entry), "The Matrix in burak's watchlist")

    def test_one_entry_per_user_and_movie(self):
        WatchlistEntry.objects.create(user=self.user, movie=self.movie)
        with self.assertRaises(IntegrityError), transaction.atomic():
            WatchlistEntry.objects.create(user=self.user, movie=self.movie)

    def test_newest_first(self):
        first = WatchlistEntry.objects.create(user=self.user, movie=self.movie)
        second = WatchlistEntry.objects.create(user=self.user, movie=self.movie2)
        self.assertEqual(list(WatchlistEntry.objects.all()), [second, first])


# ---------------------------------------------------------------------------
# Permissions shared by every action
# ---------------------------------------------------------------------------

class ActionPermissionTests(EngagementTestCase):
    def action_urls(self):
        return [rate_url(self.movie), delete_rating_url(self.movie),
                add_url(self.movie), remove_url(self.movie)]

    def test_anonymous_users_go_to_login_and_back_to_the_movie(self):
        for url in self.action_urls():
            with self.subTest(url=url):
                response = self.client.post(url, {"score": "4"})
                self.assertRedirects(response, f"{LOGIN_URL}?next=/movies/{self.movie.pk}/",
                                     fetch_redirect_response=False)
        self.assertEqual(Rating.objects.count(), 0)
        self.assertEqual(WatchlistEntry.objects.count(), 0)

    def test_get_is_not_allowed(self):
        self.login()
        for url in self.action_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)

    def test_unknown_movie_gives_404(self):
        self.login()
        for name in ("rate_movie", "delete_rating", "add_to_watchlist", "remove_from_watchlist"):
            with self.subTest(name=name):
                response = self.client.post(reverse(f"engagement:{name}", args=[99999]), {"score": "4"})
                self.assertEqual(response.status_code, 404)

    def test_csrf_token_is_required(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        for url in self.action_urls():
            with self.subTest(url=url):
                self.assertEqual(csrf_client.post(url, {"score": "4"}).status_code, 403)
        self.assertEqual(Rating.objects.count(), 0)

    def test_safe_next_is_followed(self):
        self.login()
        response = self.client.post(add_url(self.movie), {"next": WATCHLIST_URL})
        self.assertRedirects(response, WATCHLIST_URL)

    def test_unsafe_next_is_ignored(self):
        self.login()
        response = self.client.post(add_url(self.movie), {"next": "https://evil.example/"})
        self.assertRedirects(response, self.movie.get_absolute_url())


# ---------------------------------------------------------------------------
# Ratings
# ---------------------------------------------------------------------------

class RateMovieTests(EngagementTestCase):
    def test_first_rating_is_saved(self):
        self.login()
        response = self.client.post(rate_url(self.movie), {"score": "4"})
        self.assertRedirects(response, self.movie.get_absolute_url())
        self.assertEqual(Rating.objects.get(user=self.user, movie=self.movie).score, 4)
        self.assertIn("Your rating of 4/5 for “The Matrix” was saved.", message_texts(response))

    def test_rating_again_updates_instead_of_duplicating(self):
        self.login()
        self.client.post(rate_url(self.movie), {"score": "4"})
        response = self.client.post(rate_url(self.movie), {"score": "2"})
        self.assertEqual(Rating.objects.filter(user=self.user, movie=self.movie).count(), 1)
        self.assertEqual(Rating.objects.get(user=self.user, movie=self.movie).score, 2)
        self.assertIn("Your rating of 2/5 for “The Matrix” was updated.", message_texts(response))

    def test_invalid_scores_are_rejected(self):
        self.login()
        for data in ({"score": "0"}, {"score": "6"}, {"score": "3.5"}, {"score": "abc"},
                     {"score": ""}, {}):
            with self.subTest(data=data):
                response = self.client.post(rate_url(self.movie), data)
                self.assertRedirects(response, self.movie.get_absolute_url())
                self.assertIn("Choose a rating from 1 to 5.", message_texts(response))
        self.assertEqual(Rating.objects.count(), 0)

    def test_invalid_score_keeps_the_existing_rating(self):
        self.login()
        Rating.objects.create(user=self.user, movie=self.movie, score=5)
        self.client.post(rate_url(self.movie), {"score": "9"})
        self.assertEqual(Rating.objects.get(user=self.user, movie=self.movie).score, 5)

    def test_rating_never_changes_another_users_rating(self):
        Rating.objects.create(user=self.other, movie=self.movie, score=1)
        self.login()
        self.client.post(rate_url(self.movie), {"score": "5"})
        self.assertEqual(Rating.objects.get(user=self.other, movie=self.movie).score, 1)
        self.assertEqual(Rating.objects.get(user=self.user, movie=self.movie).score, 5)


class DeleteRatingTests(EngagementTestCase):
    def test_removes_own_rating_only(self):
        Rating.objects.create(user=self.user, movie=self.movie, score=4)
        Rating.objects.create(user=self.other, movie=self.movie, score=2)
        self.login()
        response = self.client.post(delete_rating_url(self.movie))
        self.assertRedirects(response, self.movie.get_absolute_url())
        self.assertFalse(Rating.objects.filter(user=self.user).exists())
        self.assertTrue(Rating.objects.filter(user=self.other, movie=self.movie).exists())
        self.assertIn("Your rating for “The Matrix” was removed.", message_texts(response))

    def test_nothing_to_remove(self):
        self.login()
        response = self.client.post(delete_rating_url(self.movie))
        self.assertRedirects(response, self.movie.get_absolute_url())
        self.assertIn("You haven’t rated “The Matrix”.", message_texts(response))


# ---------------------------------------------------------------------------
# Watchlist actions and page
# ---------------------------------------------------------------------------

class WatchlistActionTests(EngagementTestCase):
    def test_add(self):
        self.login()
        response = self.client.post(add_url(self.movie))
        self.assertRedirects(response, self.movie.get_absolute_url())
        self.assertTrue(WatchlistEntry.objects.filter(user=self.user, movie=self.movie).exists())
        self.assertIn("“The Matrix” was added to your watchlist.", message_texts(response))

    def test_adding_twice_keeps_one_entry(self):
        self.login()
        self.client.post(add_url(self.movie))
        response = self.client.post(add_url(self.movie))
        self.assertEqual(WatchlistEntry.objects.filter(user=self.user, movie=self.movie).count(), 1)
        self.assertIn("“The Matrix” is already in your watchlist.", message_texts(response))

    def test_remove_own_entry_only(self):
        WatchlistEntry.objects.create(user=self.user, movie=self.movie)
        WatchlistEntry.objects.create(user=self.other, movie=self.movie)
        self.login()
        response = self.client.post(remove_url(self.movie))
        self.assertFalse(WatchlistEntry.objects.filter(user=self.user).exists())
        self.assertTrue(WatchlistEntry.objects.filter(user=self.other).exists())
        self.assertIn("“The Matrix” was removed from your watchlist.", message_texts(response))

    def test_remove_when_not_saved(self):
        self.login()
        response = self.client.post(remove_url(self.movie))
        self.assertRedirects(response, self.movie.get_absolute_url())
        self.assertIn("“The Matrix” wasn’t in your watchlist.", message_texts(response))

    def test_removing_a_movie_keeps_the_movie(self):
        WatchlistEntry.objects.create(user=self.user, movie=self.movie)
        self.login()
        self.client.post(remove_url(self.movie))
        self.assertTrue(Movie.objects.filter(pk=self.movie.pk).exists())


class WatchlistPageTests(EngagementTestCase):
    def test_login_required(self):
        self.assertRedirects(self.client.get(WATCHLIST_URL), f"{LOGIN_URL}?next={WATCHLIST_URL}")

    def test_shows_own_movies_newest_first(self):
        WatchlistEntry.objects.create(user=self.user, movie=self.movie)
        WatchlistEntry.objects.create(user=self.user, movie=self.movie2)
        WatchlistEntry.objects.create(user=self.other, movie=Movie.objects.create(title="Secret"))
        self.login()
        response = self.client.get(WATCHLIST_URL)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "engagement/watchlist.html")
        self.assertEqual([e.movie for e in response.context["entries"]], [self.movie2, self.movie])
        self.assertEqual(response.context["watchlist_count"], 2)
        self.assertNotContains(response, "Secret")
        self.assertContains(response, f'action="{remove_url(self.movie)}"')

    def test_empty_watchlist(self):
        self.login()
        response = self.client.get(WATCHLIST_URL)
        self.assertEqual(response.context["watchlist_count"], 0)
        self.assertContains(response, "Your watchlist is empty")

    def test_pagination(self):
        for i in range(14):
            WatchlistEntry.objects.create(user=self.user, movie=Movie.objects.create(title=f"M{i}"))
        self.login()
        first = self.client.get(WATCHLIST_URL)
        self.assertEqual(len(first.context["entries"]), 12)
        self.assertEqual(first.context["watchlist_count"], 14)
        self.assertEqual(len(self.client.get(WATCHLIST_URL, {"page": 2}).context["entries"]), 2)
        self.assertEqual(self.client.get(WATCHLIST_URL, {"page": 99}).context["page_obj"].number, 2)

    def test_queries_do_not_grow_with_the_list(self):
        self.login()

        def count():
            with CaptureQueriesContext(connection) as queries:
                self.client.get(WATCHLIST_URL)
            return len(queries)

        WatchlistEntry.objects.create(user=self.user, movie=self.movie)
        few = count()
        for i in range(8):
            WatchlistEntry.objects.create(user=self.user, movie=Movie.objects.create(title=f"M{i}"))
        self.assertEqual(few, count())


# ---------------------------------------------------------------------------
# What the movie detail page receives
# ---------------------------------------------------------------------------

class MovieDetailContextTests(EngagementTestCase):
    def get_detail(self):
        return self.client.get(self.movie.get_absolute_url())

    def test_anonymous_visitor(self):
        context = self.get_detail().context
        self.assertIsNone(context["user_rating"])
        self.assertFalse(context["in_watchlist"])
        self.assertEqual(context["rating_choices"], [1, 2, 3, 4, 5])
        self.assertIsNone(context["movie"].average_rating)
        self.assertEqual(context["movie"].rating_count, 0)

    def test_logged_in_viewer_sees_own_rating_and_watchlist_state(self):
        Rating.objects.create(user=self.user, movie=self.movie, score=4)
        Rating.objects.create(user=self.other, movie=self.movie, score=1)
        WatchlistEntry.objects.create(user=self.user, movie=self.movie)
        self.login()
        context = self.get_detail().context
        self.assertEqual(context["user_rating"], 4)
        self.assertTrue(context["in_watchlist"])
        self.assertEqual(context["movie"].average_rating, 2.5)
        self.assertEqual(context["movie"].rating_count, 2)

    def test_other_users_data_does_not_leak(self):
        Rating.objects.create(user=self.other, movie=self.movie, score=1)
        WatchlistEntry.objects.create(user=self.other, movie=self.movie)
        self.login()
        context = self.get_detail().context
        self.assertIsNone(context["user_rating"])
        self.assertFalse(context["in_watchlist"])

    def test_detail_page_queries_for_logged_in_viewer(self):
        self.login()
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(self.get_detail().status_code, 200)
        # session + user, movie (with average), genres, own rating, watchlist check
        self.assertLessEqual(len(queries), 6)
