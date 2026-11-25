from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

User = get_user_model()


class RegistrationForm(UserCreationForm):
    """Sign-up form: username, email and the password twice (FR-03).

    UserCreationForm already checks that the username is free, that both
    passwords match and that the password passes the validators in
    settings.AUTH_PASSWORD_VALIDATORS. Django stores it hashed (NFR-04).
    """

    email = forms.EmailField(
        required=True,
        help_text="Used only for your account. We never show it to other users.",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email
