from django import forms

from .models import SCORE_CHOICES


class RatingForm(forms.Form):
    """The score a viewer picks on the movie page: a whole number from 1 to 5."""

    score = forms.TypedChoiceField(
        choices=SCORE_CHOICES,
        coerce=int,
        error_messages={
            "required": "Choose a rating from 1 to 5.",
            "invalid_choice": "Choose a rating from 1 to 5.",
        },
    )
