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
