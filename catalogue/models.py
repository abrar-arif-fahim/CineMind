from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.functions import Lower

# Base URL for TMDB poster images. Movie.poster_path stores only the file
# part that TMDB returns (for example "/abc123.jpg").
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"


class Genre(models.Model):
    """A movie genre such as Action or Drama.

    tmdb_id holds TMDB's own genre id (for example 28 = Action), so the
    TMDB import can match genres it has already saved instead of creating
    duplicates. It is optional so an admin can also add genres by hand.
    """

    tmdb_id = models.PositiveIntegerField(
        "TMDB id",
        unique=True,
        null=True,
        blank=True,
        help_text="Genre id on TMDB. Leave empty for genres added by hand.",
    )
    name = models.CharField(max_length=50)

    class Meta:
        ordering = ["name"]
        constraints = [
            # "Action" and "action" count as the same genre.
            models.UniqueConstraint(
                Lower("name"),
                name="catalogue_genre_name_unique_ci",
                violation_error_message="A genre with this name already exists.",
            ),
        ]

    def __str__(self):
        return self.name


class Movie(models.Model):
    """A movie in the CineMind catalogue.

    Movies and genres are many-to-many. Django stores the links in the
    catalogue_moviegenre table (the MovieGenre entity from the Stage 1 class
    diagram), and that table allows each movie-genre pair only once.
    """

    tmdb_id = models.PositiveIntegerField(
        "TMDB id",
        unique=True,
        null=True,
        blank=True,
        help_text="Movie id on TMDB, used to match movies on re-import. "
        "Leave empty for movies added by hand.",
    )
    title = models.CharField(max_length=255)
    overview = models.TextField(
        blank=True,
        help_text="Short plot summary. Also used by the recommendation engine.",
    )
    release_date = models.DateField(null=True, blank=True)
    runtime = models.PositiveSmallIntegerField(
        "runtime (minutes)",
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )
    poster_path = models.CharField(
        max_length=255,
        blank=True,
        help_text='TMDB poster file path, for example "/abc123.jpg".',
    )
    genres = models.ManyToManyField(
        Genre,
        related_name="movies",
        blank=True,
        db_table="catalogue_moviegenre",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title", "release_date"]
        indexes = [
            # Speeds up searching and sorting movies by title.
            models.Index(fields=["title"], name="catalogue_movie_title_idx"),
        ]

    def __str__(self):
        if self.release_year:
            return f"{self.title} ({self.release_year})"
        return self.title

    @property
    def release_year(self):
        return self.release_date.year if self.release_date else None

    @property
    def poster_url(self):
        """Full image URL for templates, or an empty string if there is no poster."""
        if not self.poster_path:
            return ""
        if self.poster_path.startswith(("http://", "https://")):
            return self.poster_path
        return f"{TMDB_IMAGE_BASE_URL}{self.poster_path}"
