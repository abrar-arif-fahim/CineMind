from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Avg
from django.shortcuts import redirect, resolve_url
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import CreateView, TemplateView

from .forms import RegistrationForm

RECENT_RATINGS_ON_PROFILE = 5
RECENT_WATCHLIST_ON_PROFILE = 4


def safe_next_url(request, fallback):
    """The ?next= address if it points to this site, otherwise `fallback`.

    Checking it stops a link like ?next=https://evil.example from sending
    users to another website after they log in (an "open redirect").
    """
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return resolve_url(fallback)


class RegisterView(CreateView):
    """Create an account, log the new user in and send them on."""

    form_class = RegistrationForm
    template_name = "accounts/register.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(settings.LOGIN_REDIRECT_URL)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, f"Welcome to CineMind, {user.username}! Your account is ready.")
        return redirect(safe_next_url(self.request, settings.LOGIN_REDIRECT_URL))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next"] = self.request.GET.get("next", "")
        return context


class LoginView(auth_views.LoginView):
    """Django's login view with our template and a welcome message.

    Django checks the password and rejects a ?next= that leaves the site.
    """

    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Welcome back, {form.get_user().username}!")
        return response


class LogoutView(auth_views.LogoutView):
    """Log out. Only POST is accepted (a GET link could log people out by accident)."""

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        messages.info(request, "You have been logged out.")
        return response


class ProfileView(LoginRequiredMixin, TemplateView):
    """The signed-in viewer's dashboard: their numbers, latest ratings and watchlist."""

    template_name = "accounts/profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        ratings = user.ratings.all()
        watchlist = user.watchlist_entries.all()
        context.update({
            "rating_count": ratings.count(),
            "average_score": ratings.aggregate(average=Avg("score"))["average"],
            "watchlist_count": watchlist.count(),
            "recent_ratings": ratings.select_related("movie")[:RECENT_RATINGS_ON_PROFILE],
            "recent_watchlist": watchlist.select_related("movie")[:RECENT_WATCHLIST_ON_PROFILE],
        })
        return context
