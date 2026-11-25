from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

MIN_SCORE = 1
MAX_SCORE = 5
SCORE_CHOICES = [(score, str(score)) for score in range(MIN_SCORE, MAX_SCORE + 1)]


class Rating(models.Model):
    """One viewer's score for one movie (FR-05).

    Each user can rate a movie only once; rating it again updates the score.
    The database itself enforces both rules (NFR-06), so they hold even if a
    request skips the form.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ratings",
    )
    movie = models.ForeignKey(
        "catalogue.Movie",
        on_delete=models.CASCADE,
        related_name="ratings",
    )
    score = models.PositiveSmallIntegerField(
        choices=SCORE_CHOICES,
        validators=[MinValueValidator(MIN_SCORE), MaxValueValidator(MAX_SCORE)],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "movie"],
                name="engagement_rating_unique_user_movie",
                violation_error_message="You have already rated this movie.",
            ),
            models.CheckConstraint(
                condition=Q(score__gte=MIN_SCORE) & Q(score__lte=MAX_SCORE),
                name="engagement_rating_score_1_to_5",
                violation_error_message="A rating must be between 1 and 5.",
            ),
        ]

    def __str__(self):
        return f"{self.user} rated {self.movie}: {self.score}/5"


class WatchlistEntry(models.Model):
    """A movie a viewer saved to watch later (FR-07). No duplicates per user."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="watchlist_entries",
    )
    movie = models.ForeignKey(
        "catalogue.Movie",
        on_delete=models.CASCADE,
        related_name="watchlist_entries",
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-added_at", "-pk"]
        verbose_name_plural = "watchlist entries"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "movie"],
                name="engagement_watchlist_unique_user_movie",
                violation_error_message="This movie is already in the watchlist.",
            ),
        ]

    def __str__(self):
        return f"{self.movie} in {self.user}'s watchlist"
