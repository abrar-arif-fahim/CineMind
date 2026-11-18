from django.db.models import Count, F
from django.views.generic import DetailView, ListView, TemplateView

from .forms import MovieFilterForm
from .models import Genre, Movie

LATEST_MOVIES_ON_HOME = 8
MOVIES_PER_PAGE = 12


def release_years():
    """Years that have at least one movie, newest first (for the year filter)."""
    return [day.year for day in Movie.objects.dates("release_date", "year", order="DESC")]


class HomeView(TemplateView):
    """Homepage: the newest movies and the genres people can jump into."""

    template_name = "catalogue/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["latest_movies"] = (
            Movie.objects.prefetch_related("genres")
            # Newest release first; movies without a date go to the end.
            .order_by(F("release_date").desc(nulls_last=True), "title")[:LATEST_MOVIES_ON_HOME]
        )
        context["genres"] = (
            Genre.objects.annotate(movie_count=Count("movies"))
            .filter(movie_count__gt=0)
            .order_by("name")
        )
        context["movie_count"] = Movie.objects.count()
        return context


class MovieListView(ListView):
    """Movie catalogue with title search, genre and year filters, and pages."""

    model = Movie
    template_name = "catalogue/movie_list.html"
    context_object_name = "movies"
    paginate_by = MOVIES_PER_PAGE

    def get_queryset(self):
        self.form = MovieFilterForm(self.request.GET)
        # prefetch_related loads every movie's genres in one extra query,
        # instead of one query per movie card.
        return self.form.filter(Movie.objects.prefetch_related("genres"))

    def paginate_queryset(self, queryset, page_size):
        # get_page() never fails: "?page=abc" shows page 1 and a page number
        # past the end shows the last page, instead of a 404 error.
        paginator = self.get_paginator(queryset, page_size)
        page = paginator.get_page(self.request.GET.get(self.page_kwarg))
        return paginator, page, page.object_list, page.has_other_pages()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected = self.form.cleaned_data
        context.update({
            "form": self.form,
            "query": selected.get("q", ""),
            "selected_genre": selected.get("genre"),
            "selected_year": selected.get("year"),
            "is_filtered": self.form.is_filtered,
            "result_count": context["paginator"].count,
            "genres": Genre.objects.all(),
            "years": release_years(),
        })
        return context


class MovieDetailView(DetailView):
    """One movie's page. An unknown id gives a normal 404 page."""

    queryset = Movie.objects.prefetch_related("genres")
    template_name = "catalogue/movie_detail.html"
    context_object_name = "movie"
