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
