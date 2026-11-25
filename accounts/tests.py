"""Tests for registration, login, logout and the profile dashboard."""

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse

from catalogue.models import Movie
from engagement.models import Rating, WatchlistEntry

User = get_user_model()

REGISTER_URL = reverse("accounts:register")
LOGIN_URL = reverse("accounts:login")
LOGOUT_URL = reverse("accounts:logout")
PROFILE_URL = reverse("accounts:profile")
HOME_URL = reverse("catalogue:home")
GOOD_PASSWORD = "Sunny-Movie-2026"


def registration_data(**overrides):
    data = {
        "username": "burak",
        "email": "burak@example.com",
        "password1": GOOD_PASSWORD,
        "password2": GOOD_PASSWORD,
    }
    data.update(overrides)
    return data


def logged_in_user_id(client):
    return client.session.get("_auth_user_id")


def message_texts(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


class UrlTests(TestCase):
    def test_paths(self):
        self.assertEqual(REGISTER_URL, "/accounts/register/")
        self.assertEqual(LOGIN_URL, "/accounts/login/")
        self.assertEqual(LOGOUT_URL, "/accounts/logout/")
        self.assertEqual(PROFILE_URL, "/accounts/profile/")


class RegistrationTests(TestCase):
    def test_page_loads(self):
        response = self.client.get(REGISTER_URL)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/register.html")
        for field in ("username", "email", "password1", "password2"):
            self.assertContains(response, f'name="{field}"')

    def test_valid_registration_creates_user_and_logs_in(self):
        response = self.client.post(REGISTER_URL, registration_data())
        self.assertRedirects(response, HOME_URL)
        user = User.objects.get(username="burak")
        self.assertEqual(user.email, "burak@example.com")
        self.assertEqual(logged_in_user_id(self.client), str(user.pk))
        self.assertIn("Welcome to CineMind, burak! Your account is ready.", message_texts(response))

    def test_password_is_stored_hashed(self):
        self.client.post(REGISTER_URL, registration_data())
        user = User.objects.get(username="burak")
        self.assertNotEqual(user.password, GOOD_PASSWORD)
        self.assertTrue(user.password.startswith(("pbkdf2_", "argon2", "bcrypt", "scrypt")))
        self.assertTrue(user.check_password(GOOD_PASSWORD))

    def test_safe_next_is_followed(self):
        response = self.client.post(REGISTER_URL + "?next=/movies/", registration_data(next="/movies/"))
        self.assertRedirects(response, "/movies/")

    def test_unsafe_next_is_ignored(self):
        response = self.client.post(REGISTER_URL, registration_data(next="https://evil.example/"))
        self.assertRedirects(response, HOME_URL)

    def test_invalid_data_is_rejected(self):
        User.objects.create_user("taken", "taken@example.com", GOOD_PASSWORD)
        cases = {
            "missing email": ({"email": ""}, "email"),
            "invalid email": ({"email": "not-an-email"}, "email"),
            "email already used (any case)": ({"email": "TAKEN@example.com"}, "email"),
            "username already used": ({"username": "taken"}, "username"),
            "passwords differ": ({"password2": "Other-Movie-2026"}, "password2"),
            "too short": ({"password1": "Ab1-x", "password2": "Ab1-x"}, "password2"),
            "too common": ({"password1": "password123", "password2": "password123"}, "password2"),
            "only numbers": ({"password1": "48291736502", "password2": "48291736502"}, "password2"),
            "too similar to username": ({"username": "moviefan2026", "password1": "moviefan2026",
                                         "password2": "moviefan2026"}, "password2"),
        }
        for name, (overrides, field) in cases.items():
            with self.subTest(name):
                response = self.client.post(REGISTER_URL, registration_data(**overrides))
                self.assertEqual(response.status_code, 200)  # form shown again
                self.assertTrue(response.context["form"].errors.get(field), response.context["form"].errors)
                self.assertEqual(User.objects.count(), 1)
                self.assertIsNone(logged_in_user_id(self.client))

    def test_logged_in_user_is_sent_home(self):
        self.client.force_login(User.objects.create_user("burak", password=GOOD_PASSWORD))
        self.assertRedirects(self.client.get(REGISTER_URL), HOME_URL)


class LoginLogoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("burak", "burak@example.com", GOOD_PASSWORD)

    def test_page_loads(self):
        response = self.client.get(LOGIN_URL)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/login.html")
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')

    def test_valid_login(self):
        response = self.client.post(LOGIN_URL, {"username": "burak", "password": GOOD_PASSWORD})
        self.assertRedirects(response, HOME_URL)
        self.assertEqual(logged_in_user_id(self.client), str(self.user.pk))
        self.assertIn("Welcome back, burak!", message_texts(response))

    def test_wrong_password(self):
        response = self.client.post(LOGIN_URL, {"username": "burak", "password": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())
        self.assertIsNone(logged_in_user_id(self.client))

    def test_unknown_user(self):
        response = self.client.post(LOGIN_URL, {"username": "nobody", "password": GOOD_PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(logged_in_user_id(self.client))

    def test_inactive_user_cannot_log_in(self):
        self.user.is_active = False
        self.user.save()
        self.client.post(LOGIN_URL, {"username": "burak", "password": GOOD_PASSWORD})
        self.assertIsNone(logged_in_user_id(self.client))

    def test_next_is_followed_and_kept_in_the_form(self):
        self.assertContains(self.client.get(LOGIN_URL + "?next=/movies/3/"), 'value="/movies/3/"')
        response = self.client.post(LOGIN_URL, {"username": "burak", "password": GOOD_PASSWORD,
                                                "next": "/movies/3/"})
        self.assertRedirects(response, "/movies/3/", fetch_redirect_response=False)

    def test_unsafe_next_is_ignored(self):
        response = self.client.post(LOGIN_URL, {"username": "burak", "password": GOOD_PASSWORD,
                                                "next": "https://evil.example/"})
        self.assertRedirects(response, HOME_URL)

    def test_logged_in_user_is_sent_home(self):
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get(LOGIN_URL), HOME_URL)

    def test_logout_with_post(self):
        self.client.force_login(self.user)
        response = self.client.post(LOGOUT_URL)
        self.assertRedirects(response, HOME_URL)
        self.assertIsNone(logged_in_user_id(self.client))
        self.assertIn("You have been logged out.", message_texts(response))

    def test_logout_with_get_is_refused(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(LOGOUT_URL).status_code, 405)
        self.assertIsNotNone(logged_in_user_id(self.client))

    def test_login_form_needs_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(LOGIN_URL, {"username": "burak", "password": GOOD_PASSWORD})
        self.assertEqual(response.status_code, 403)


class ProfileTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("burak", password=GOOD_PASSWORD)
        cls.other = User.objects.create_user("other", password=GOOD_PASSWORD)
        cls.movies = [Movie.objects.create(title=f"Movie {i}") for i in range(7)]
        for movie, score in zip(cls.movies[:6], [5, 4, 3, 4, 5, 3]):
            Rating.objects.create(user=cls.user, movie=movie, score=score)
        for movie in cls.movies[:2]:
            WatchlistEntry.objects.create(user=cls.user, movie=movie)
        Rating.objects.create(user=cls.other, movie=cls.movies[6], score=1)
        WatchlistEntry.objects.create(user=cls.other, movie=cls.movies[6])

    def test_login_required(self):
        response = self.client.get(PROFILE_URL)
        self.assertRedirects(response, f"{LOGIN_URL}?next={PROFILE_URL}")

    def test_dashboard_numbers(self):
        self.client.force_login(self.user)
        response = self.client.get(PROFILE_URL)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/profile.html")
        self.assertEqual(response.context["rating_count"], 6)
        self.assertEqual(response.context["average_score"], 4.0)
        self.assertEqual(response.context["watchlist_count"], 2)
        self.assertEqual(len(response.context["recent_ratings"]), 5)
        self.assertContains(response, "burak")

    def test_shows_only_own_data(self):
        self.client.force_login(self.user)
        response = self.client.get(PROFILE_URL)
        shown = {r.movie for r in response.context["recent_ratings"]}
        shown |= {e.movie for e in response.context["recent_watchlist"]}
        self.assertNotIn(self.movies[6], shown)

    def test_new_user_has_empty_dashboard(self):
        self.client.force_login(User.objects.create_user("new", password=GOOD_PASSWORD))
        response = self.client.get(PROFILE_URL)
        self.assertEqual(response.context["rating_count"], 0)
        self.assertIsNone(response.context["average_score"])
        self.assertContains(response, "You haven’t rated any movies yet.")
