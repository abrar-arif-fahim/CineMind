from django.shortcuts import render

from .models import Movie


def home(request):
    featured_movies = Movie.objects.prefetch_related("genres").order_by(
        "-created_at", "-pk"
    )[:8]
    return render(request, "home.html", {"featured_movies": featured_movies})
