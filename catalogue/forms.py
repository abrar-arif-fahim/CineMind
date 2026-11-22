from django import forms

from .models import Genre


class MovieFilterForm(forms.Form):
    """Search and filter options for the movie catalogue.

    The form is submitted with GET, so the options appear in the address bar
    (for example /movies/?q=matrix&genre=3&year=1999) and can be bookmarked.
    Every field is optional. A field with a bad value (an unknown genre id, a
    year like "abc") is simply ignored, so a broken link never causes an error.
    """

    q = forms.CharField(
        label="Title",
        required=False,
        max_length=100,
        strip=True,
    )
    genre = forms.ModelChoiceField(
        label="Genre",
        queryset=Genre.objects.all(),
        required=False,
        empty_label="All genres",
    )
    year = forms.IntegerField(
        label="Release year",
        required=False,
        min_value=1870,
        max_value=2100,
    )

    def filter(self, queryset):
        """Return `queryset` narrowed down by every field that has a valid value."""
        self.is_valid()  # fills cleaned_data with the valid fields only
        data = self.cleaned_data

        if data.get("q"):
            queryset = queryset.filter(title__icontains=data["q"])
        if data.get("genre"):
            queryset = queryset.filter(genres=data["genre"])
        if data.get("year"):
            queryset = queryset.filter(release_date__year=data["year"])
        return queryset

    @property
    def is_filtered(self):
        """True when at least one search or filter option is active."""
        self.is_valid()
        return any(self.cleaned_data.get(name) for name in ("q", "genre", "year"))
