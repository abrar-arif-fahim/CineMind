from django.urls import path

from . import views

app_name = "engagement"

urlpatterns = [
    path("watchlist/", views.WatchlistView.as_view(), name="watchlist"),
    # Actions (POST only). <pk> is the movie's id.
    path("movies/<int:pk>/rate/", views.rate_movie, name="rate_movie"),
    path("movies/<int:pk>/rate/delete/", views.delete_rating, name="delete_rating"),
    path("movies/<int:pk>/watchlist/add/", views.add_to_watchlist, name="add_to_watchlist"),
    path("movies/<int:pk>/watchlist/remove/", views.remove_from_watchlist, name="remove_from_watchlist"),
]
