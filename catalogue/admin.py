from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from .models import Genre, Movie


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ("name", "tmdb_id", "movie_count")
    search_fields = ("name",)
    ordering = ("name",)

    def get_queryset(self, request):
        # Count each genre's movies in the same query as the list.
        return super().get_queryset(request).annotate(_movie_count=Count("movies"))

    @admin.display(description="Movies", ordering="_movie_count")
    def movie_count(self, obj):
        return obj._movie_count


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ("title", "release_year", "runtime", "genre_list", "tmdb_id")
    list_display_links = ("title",)
    list_filter = ("genres",)
    search_fields = ("title", "overview", "tmdb_id")
    date_hierarchy = "release_date"
    filter_horizontal = ("genres",)
    readonly_fields = ("poster_preview", "created_at", "updated_at")
    list_per_page = 25

    fieldsets = (
        (None, {"fields": ("title", "overview", "genres")}),
        ("Details", {"fields": ("release_date", "runtime")}),
        ("TMDB", {"fields": ("tmdb_id", "poster_path", "poster_preview")}),
        ("Record history", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        # Load all genres for the listed movies in one extra query.
        return super().get_queryset(request).prefetch_related("genres")

    @admin.display(description="Year", ordering="release_date")
    def release_year(self, obj):
        return obj.release_year

    @admin.display(description="Genres")
    def genre_list(self, obj):
        return ", ".join(genre.name for genre in obj.genres.all())

    @admin.display(description="Poster")
    def poster_preview(self, obj):
        if not obj.poster_url:
            return "No poster"
        return format_html('<img src="{}" alt="" style="max-height: 200px;">', obj.poster_url)
