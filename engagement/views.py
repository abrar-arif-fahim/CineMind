"""Rating and watchlist actions.

Every action that changes data:
- accepts only POST (Django's CSRF protection then applies automatically),
- needs a logged-in user; anonymous users are sent to the login page and come
  back to the movie afterwards,
- only ever touches the logged-in user's own rows, because rows are looked up
  by (request.user, movie). There is no way to name another user's rating.
"""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from accounts.views import safe_next_url
from catalogue.models import Movie

from .forms import RatingForm
from .models import Rating, WatchlistEntry

WATCHLIST_PER_PAGE = 12


def login_required_for_movie(view):
    """Like @login_required, but after logging in the user returns to the movie
    page (or the page they came from), not to the POST-only action URL."""

    @wraps(view)
    def wrapper(request, pk, *args, **kwargs):
        if not request.user.is_authenticated:
            movie = get_object_or_404(Movie, pk=pk)
            messages.info(request, "Please log in to rate movies and manage your watchlist.")
            return redirect_to_login(safe_next_url(request, movie.get_absolute_url()))
        return view(request, pk, *args, **kwargs)

    return wrapper


def back_to(request, movie):
    """Where to go after an action: a safe ?next= address, else the movie page."""
    return redirect(safe_next_url(request, movie.get_absolute_url()))


@require_POST
@login_required_for_movie
def rate_movie(request, pk):
    """Create the user's rating for a movie, or change it (FR-05)."""
    movie = get_object_or_404(Movie, pk=pk)
    form = RatingForm(request.POST)
    if form.is_valid():
        score = form.cleaned_data["score"]
        _, created = Rating.objects.update_or_create(
            user=request.user, movie=movie, defaults={"score": score}
        )
        verb = "saved" if created else "updated"
        messages.success(request, f"Your rating of {score}/5 for “{movie.title}” was {verb}.")
    else:
        messages.error(request, form.errors["score"][0])
    return back_to(request, movie)


@require_POST
@login_required_for_movie
def delete_rating(request, pk):
    """Remove the user's rating for a movie (FR-06)."""
    movie = get_object_or_404(Movie, pk=pk)
    deleted, _ = Rating.objects.filter(user=request.user, movie=movie).delete()
    if deleted:
        messages.success(request, f"Your rating for “{movie.title}” was removed.")
    else:
        messages.info(request, f"You haven’t rated “{movie.title}”.")
    return back_to(request, movie)


@require_POST
@login_required_for_movie
def add_to_watchlist(request, pk):
    """Save a movie to the user's watchlist; doing it twice changes nothing (FR-07)."""
    movie = get_object_or_404(Movie, pk=pk)
    _, created = WatchlistEntry.objects.get_or_create(user=request.user, movie=movie)
    if created:
        messages.success(request, f"“{movie.title}” was added to your watchlist.")
    else:
        messages.info(request, f"“{movie.title}” is already in your watchlist.")
    return back_to(request, movie)


@require_POST
@login_required_for_movie
def remove_from_watchlist(request, pk):
    """Take a movie off the user's watchlist (FR-07)."""
    movie = get_object_or_404(Movie, pk=pk)
    deleted, _ = WatchlistEntry.objects.filter(user=request.user, movie=movie).delete()
    if deleted:
        messages.success(request, f"“{movie.title}” was removed from your watchlist.")
    else:
        messages.info(request, f"“{movie.title}” wasn’t in your watchlist.")
    return back_to(request, movie)


class WatchlistView(LoginRequiredMixin, ListView):
    """The logged-in user's saved movies, newest first."""

    template_name = "engagement/watchlist.html"
    context_object_name = "entries"
    paginate_by = WATCHLIST_PER_PAGE

    def get_queryset(self):
        return (
            WatchlistEntry.objects.filter(user=self.request.user)
            .select_related("movie")
            .prefetch_related("movie__genres")
        )

    def paginate_queryset(self, queryset, page_size):
        paginator = self.get_paginator(queryset, page_size)
        page = paginator.get_page(self.request.GET.get(self.page_kwarg))
        return paginator, page, page.object_list, page.has_other_pages()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["watchlist_count"] = context["paginator"].count
        return context


def movie_engagement_context(user, movie):
    """Variables the movie detail page needs for its rating and watchlist panels."""
    context = {
        "rating_choices": [score for score, _ in RatingForm.base_fields["score"].choices],
        "user_rating": None,
        "in_watchlist": False,
    }
    if user.is_authenticated:
        context["user_rating"] = (
            Rating.objects.filter(user=user, movie=movie).values_list("score", flat=True).first()
        )
        context["in_watchlist"] = WatchlistEntry.objects.filter(user=user, movie=movie).exists()
    return context
