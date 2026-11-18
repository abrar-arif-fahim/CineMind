from django.urls import path

from . import views

app_name = "catalogue"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("movies/", views.MovieListView.as_view(), name="movie_list"),
    path("movies/<int:pk>/", views.MovieDetailView.as_view(), name="movie_detail"),
]
