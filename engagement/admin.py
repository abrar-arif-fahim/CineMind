from django.contrib import admin

from .models import Rating, WatchlistEntry


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ("movie", "user", "score", "updated_at")
    list_filter = ("score",)
    search_fields = ("movie__title", "user__username")
    autocomplete_fields = ("movie", "user")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("movie", "user")


@admin.register(WatchlistEntry)
class WatchlistEntryAdmin(admin.ModelAdmin):
    list_display = ("movie", "user", "added_at")
    search_fields = ("movie__title", "user__username")
    autocomplete_fields = ("movie", "user")
    readonly_fields = ("added_at",)
    list_select_related = ("movie", "user")
