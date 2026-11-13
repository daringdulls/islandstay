from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Profile

User = get_user_model()


class SignupForm(UserCreationForm):
    full_name = forms.CharField(max_length=120, label="Your full name")
    email = forms.EmailField(label="Email (used to sign in)")
    business_name = forms.CharField(max_length=120, label="Business name", required=False)
    phone = forms.CharField(max_length=30, label="Phone / WhatsApp", required=False)
    island_of_operation = forms.CharField(max_length=80, label="Island you operate on", required=False)

    class Meta:
        model = User
        fields = ("full_name", "email", "business_name", "phone", "island_of_operation")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].help_text = ""
        self.fields["password2"].help_text = ""
        self.fields["password2"].label = "Confirm password"
        attrs = {
            "full_name": {"placeholder": "e.g. Aiman Ibrahim", "autocomplete": "name"},
            "email": {"placeholder": "you@example.com", "autocomplete": "email"},
            "business_name": {"placeholder": "e.g. The Corbin Guest House", "autocomplete": "organization"},
            "phone": {"placeholder": "+960 777 1234", "autocomplete": "tel", "inputmode": "tel"},
            "island_of_operation": {"placeholder": "Start typing, e.g. Dhangethi", "list": "su-islands", "autocomplete": "off"},
            "password1": {"placeholder": "At least 8 characters", "autocomplete": "new-password"},
            "password2": {"placeholder": "Type it again", "autocomplete": "new-password"},
        }
        for name, a in attrs.items():
            self.fields[name].widget.attrs.update(a)

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(username__iexact=email).exists() or User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists. Try signing in.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]
        user.email = self.cleaned_data["email"]
        first, _, last = self.cleaned_data["full_name"].partition(" ")
        user.first_name, user.last_name = first, last
        if commit:
            user.save()
            Profile.objects.create(
                user=user,
                business_name=self.cleaned_data.get("business_name", ""),
                phone=self.cleaned_data.get("phone", ""),
                island_of_operation=self.cleaned_data.get("island_of_operation", ""),
            )
        return user


class EmailLoginForm(AuthenticationForm):
    username = forms.CharField(label="Email", widget=forms.EmailInput(attrs={"autofocus": True}))

    def clean(self):
        try:
            return super().clean()
        except forms.ValidationError:
            if getattr(self.request, "login_locked", False):
                raise forms.ValidationError("Too many sign-in attempts. Please wait 15 minutes and try again, "
                                            "or reset your password.", code="locked")
            raise
