"""Load the sample movie catalogue into the database.

Usage:
    python manage.py load_sample_movies
    python manage.py load_sample_movies --file path/to/other.json

The command is safe to run any number of times. Genres and movies are matched
by their TMDB id (the same rule the real TMDB import will use), so a second
run updates existing rows instead of creating duplicates. Movies that are not
in the file, such as ones added in the admin, are left alone.
"""

import datetime
import json
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalogue.models import Genre, Movie

DEFAULT_DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "sample_movies.json"


class Command(BaseCommand):
    help = (
        "Load sample genres and movies from a JSON file. Safe to re-run: "
        "existing records are updated, never duplicated."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default=str(DEFAULT_DATA_FILE),
            help="JSON file to load (default: catalogue/data/sample_movies.json).",
        )

    def handle(self, *args, **options):
        self.verbosity = options["verbosity"]
        data = self.read_data_file(Path(options["file"]))

        # All or nothing: if any record is invalid, nothing is saved.
        with transaction.atomic():
            genres_by_tmdb_id, genre_counts = self.load_genres(data["genres"])
            movie_counts = self.load_movies(data["movies"], genres_by_tmdb_id)

        self.stdout.write(self.style.SUCCESS(
            f"Genres: {self.format_counts(genre_counts)}. "
            f"Movies: {self.format_counts(movie_counts)}."
        ))

    # ------------------------------------------------------------------
    # Reading the file
    # ------------------------------------------------------------------

    def read_data_file(self, path):
        if not path.is_file():
            raise CommandError(f"Data file not found: {path}")
        try:
            # utf-8-sig also accepts files saved with a BOM (e.g. by Notepad).
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise CommandError(f"{path} is not valid UTF-8 JSON: {exc}") from exc

        if not isinstance(data, dict) or not isinstance(data.get("genres"), list) \
                or not isinstance(data.get("movies"), list):
            raise CommandError(f'{path} must contain a "genres" list and a "movies" list.')
        return data

    # ------------------------------------------------------------------
    # Genres
    # ------------------------------------------------------------------

    def load_genres(self, rows):
        counts = {"created": 0, "updated": 0, "unchanged": 0}
        genres_by_tmdb_id = {}

        for row in rows:
            tmdb_id = self.require(row, "tmdb_id", "genre")
            name = self.require(row, "name", "genre")

            # Match on TMDB id first, then on name, so a genre an admin
            # typed in by hand gets linked instead of duplicated.
            genre = (
                Genre.objects.filter(tmdb_id=tmdb_id).first()
                or Genre.objects.filter(name__iexact=name).first()
            )
            if genre is None:
                genre = Genre(tmdb_id=tmdb_id, name=name)
                status = "created"
            elif genre.tmdb_id != tmdb_id or genre.name != name:
                genre.tmdb_id = tmdb_id
                genre.name = name
                status = "updated"
            else:
                status = "unchanged"

            if status != "unchanged":
                self.validate_and_save(genre, f"Genre '{name}'")
            counts[status] += 1
            genres_by_tmdb_id[tmdb_id] = genre

        return genres_by_tmdb_id, counts

    # ------------------------------------------------------------------
    # Movies
    # ------------------------------------------------------------------

    def load_movies(self, rows, genres_by_tmdb_id):
        counts = {"created": 0, "updated": 0, "unchanged": 0}

        for row in rows:
            tmdb_id = self.require(row, "tmdb_id", "movie")
            title = self.require(row, "title", "movie")
            label = f"Movie '{title}'"

            values = {
                "title": title,
                "overview": row.get("overview", ""),
                "release_date": self.parse_date(row.get("release_date"), label),
                "runtime": row.get("runtime"),
                "poster_path": row.get("poster_path", ""),
            }
            genres = self.lookup_genres(row.get("genres", []), genres_by_tmdb_id, label)

            movie = Movie.objects.filter(tmdb_id=tmdb_id).first()
            if movie is None:
                movie = Movie(tmdb_id=tmdb_id, **values)
                status = "created"
            else:
                changed = [field for field, value in values.items()
                           if getattr(movie, field) != value]
                for field in changed:
                    setattr(movie, field, values[field])
                genres_changed = set(movie.genres.all()) != set(genres)
                status = "updated" if changed or genres_changed else "unchanged"

            if status != "unchanged":
                self.validate_and_save(movie, label)
                movie.genres.set(genres)
            counts[status] += 1

            if self.verbosity >= 2:
                self.stdout.write(f"  {status:<9} {movie}")

        return counts

    def lookup_genres(self, genre_ids, genres_by_tmdb_id, label):
        missing = [genre_id for genre_id in genre_ids if genre_id not in genres_by_tmdb_id]
        if missing:
            raise CommandError(
                f"{label} uses genre id(s) {missing} that are not in the genres list."
            )
        return [genres_by_tmdb_id[genre_id] for genre_id in genre_ids]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def require(row, key, kind):
        value = row.get(key) if isinstance(row, dict) else None
        if value in (None, ""):
            raise CommandError(f'Every {kind} needs a "{key}" value. Problem entry: {row!r}')
        return value

    @staticmethod
    def parse_date(value, label):
        if not value:
            return None
        try:
            return datetime.date.fromisoformat(value)
        except (TypeError, ValueError) as exc:
            raise CommandError(
                f"{label}: release_date must look like YYYY-MM-DD, got {value!r}."
            ) from exc

    @staticmethod
    def validate_and_save(obj, label):
        try:
            obj.full_clean()
        except ValidationError as exc:
            raise CommandError(f"{label} is invalid: {exc.message_dict}") from exc
        obj.save()

    @staticmethod
    def format_counts(counts):
        return ", ".join(f"{number} {status}" for status, number in counts.items())
