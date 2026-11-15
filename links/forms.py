from django import forms
from django.utils.text import slugify

from .models import TrackedLink

RESERVED = {"admin", "api", "static", "media", "new", "edit", "go"}


class TrackedLinkForm(forms.ModelForm):
    class Meta:
        model = TrackedLink
        fields = ["label", "channel", "code", "to_form"]
        widgets = {
            "label": forms.TextInput(attrs={"placeholder": "e.g. Instagram bio"}),
            "code": forms.TextInput(attrs={"placeholder": "leave empty to make one"}),
        }
        labels = {"code": "Short link", "label": "Name"}

    def __init__(self, *args, listing=None, **kwargs):
        self.listing = listing
        super().__init__(*args, **kwargs)
        self.fields["code"].required = False
        self.fields["code"].validators = []
        self.fields["code"].help_text = ""
        self.fields["to_form"].help_text = ""

    def clean_code(self):
        raw = self.cleaned_data.get("code") or ""
        code = slugify(raw)[:40]
        if raw and len(code) < 3:
            raise forms.ValidationError("Use at least 3 letters or numbers.")
        if code in RESERVED:
            raise forms.ValidationError("That word is reserved. Try another.")
        if code and TrackedLink.objects.filter(code=code).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("That short link is taken. Try another.")
        return code

    def save(self, commit=True):
        link = super().save(commit=False)
        if not link.code:
            short = {"instagram": "ig", "facebook": "fb", "tiktok": "tt", "whatsapp": "wa", "booking": "ota", "google": "g",
                     "website": "web", "email": "mail", "print": "qr", "partner": "p", "other": "link"}[link.channel]
            base = f"{slugify(self.listing.name)[:24].strip('-')}-{short}"
            code, n = base, 2
            while TrackedLink.objects.filter(code=code).exists():
                code, n = f"{base}-{n}", n + 1
            link.code = code
        if commit:
            link.save()
        return link


from django.contrib.auth import get_user_model

from .models import Partner, Programme


class ProgrammeForm(forms.ModelForm):
    class Meta:
        model = Programme
        fields = ["is_active", "joining", "commission_type", "rate", "currency", "terms"]
        widgets = {"terms": forms.Textarea(attrs={"rows": 3, "placeholder": "e.g. Paid by bank transfer within 14 days of check-out. Cancelled or no-show bookings don't earn commission."}),
                   "joining": forms.RadioSelect, "commission_type": forms.RadioSelect}

    def clean_rate(self):
        rate = self.cleaned_data["rate"]
        if rate <= 0:
            raise forms.ValidationError("Enter a commission above zero.")
        if self.cleaned_data.get("commission_type") == Programme.TYPE_PERCENT and rate > 50:
            raise forms.ValidationError("Keep a percentage commission at 50% or less.")
        return rate


class InviteForm(forms.Form):
    name = forms.CharField(max_length=80, label="Partner's name or brand", widget=forms.TextInput(attrs={"placeholder": "e.g. Aishath Travels"}))
    email = forms.EmailField(label="Their email", widget=forms.EmailInput(attrs={"placeholder": "partner@example.com"}))


class PartnerProfileForm(forms.ModelForm):
    class Meta:
        model = Partner
        fields = ["name", "instagram", "tiktok", "other_link", "audience", "country", "phone", "payout"]
        widgets = {"payout": forms.Textarea(attrs={"rows": 3, "placeholder": "e.g. BML transfer to Aishath Ali, account 7730000123456"}),
                   "instagram": forms.TextInput(attrs={"placeholder": "@yourhandle"}),
                   "tiktok": forms.TextInput(attrs={"placeholder": "@yourhandle"}),
                   "name": forms.TextInput(attrs={"placeholder": "e.g. Aishath Travels", "autocomplete": "name"}),
                   "other_link": forms.URLInput(attrs={"placeholder": "https://youtube.com/@…"}),
                   "country": forms.TextInput(attrs={"placeholder": "e.g. Maldives", "autocomplete": "country-name"}),
                   "phone": forms.TextInput(attrs={"placeholder": "+960 777 1234", "autocomplete": "tel", "inputmode": "tel"})}
        labels = {"name": "Your name or brand", "other_link": "Website or YouTube", "tiktok": "TikTok"}


class PartnerSignupForm(PartnerProfileForm):
    email = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={"placeholder": "you@example.com", "autocomplete": "email"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "placeholder": "At least 8 characters"}), min_length=8,
                               help_text="At least 8 characters")

    class Meta(PartnerProfileForm.Meta):
        fields = ["name", "email", "password", "instagram", "tiktok", "other_link", "audience", "country", "phone", "payout"]

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        User = get_user_model()
        if User.objects.filter(username__iexact=email).exists() or User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists. Sign in first, then become a partner.")
        return email

    def clean_password(self):
        from django.contrib.auth.password_validation import validate_password
        pw = self.cleaned_data["password"]
        validate_password(pw)
        return pw

    def save(self, commit=True):
        User = get_user_model()
        email = self.cleaned_data["email"]
        first, _, last = self.cleaned_data["name"].partition(" ")
        user = User.objects.create_user(username=email, email=email, password=self.cleaned_data["password"], first_name=first[:150], last_name=last[:150])
        partner = super().save(commit=False)
        partner.user = user
        partner.save()
        return partner
