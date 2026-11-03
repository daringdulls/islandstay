from django import forms
from django.conf import settings
from django.forms import inlineformset_factory

from .models import Amenity, ActivityType, Enquiry, Island, IslandSuggestion, Listing, RoomType, TransportRoute


class DateInput(forms.DateInput):
    input_type = "date"


class EnquiryForm(forms.ModelForm):
    # Honeypot: hidden from people; bots that fill every field get caught. Named so browsers don't autofill it.
    hp_leave_empty = forms.CharField(required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "one-time-code"}))

    class Meta:
        model = Enquiry
        fields = [
            "guest_name", "guest_email", "guest_phone", "guest_country", "preferred_contact",
            "check_in", "check_out", "adults", "children", "rooms", "room_type", "needs_transfer", "message",
        ]
        labels = {
            "guest_name": "Full name", "guest_email": "Email", "guest_phone": "Phone / WhatsApp",
            "guest_country": "Country", "check_in": "Check-in / date", "check_out": "Check-out",
            "rooms": "Rooms", "room_type": "Room / package", "needs_transfer": "I'd like help arranging a transfer",
            "message": "Message to the host (optional)",
        }
        widgets = {
            "check_in": DateInput(), "check_out": DateInput(),
            "preferred_contact": forms.RadioSelect(),
            "adults": forms.NumberInput(attrs={"min": 1, "max": 30}),
            "children": forms.NumberInput(attrs={"min": 0, "max": 30}),
            "rooms": forms.NumberInput(attrs={"min": 1, "max": 30, "placeholder": "1"}),
            "guest_name": forms.TextInput(attrs={"autocomplete": "name", "placeholder": "As on your passport"}),
            "guest_email": forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "you@example.com"}),
            "guest_phone": forms.TextInput(attrs={"autocomplete": "tel", "placeholder": "+44 7700 900123"}),
            "guest_country": forms.TextInput(attrs={"autocomplete": "country-name", "placeholder": "Where you live"}),
            "message": forms.Textarea(attrs={"rows": 4, "placeholder": "Tell the host about your plans, special requests, arrival time…"}),
        }

    def __init__(self, *args, listing=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.listing = listing
        if listing is not None:
            rooms = list(listing.rooms.values_list("name", flat=True))
            if rooms:
                self.fields["room_type"] = forms.ChoiceField(
                    required=False, label="Room / package", choices=[("", "No preference")] + [(r, r) for r in rooms]
                )
            if not listing.is_stay:
                self.fields["check_in"].label = "Preferred date"
                self.fields["adults"].label = "Adults"
                for f in ("check_out", "rooms"):
                    self.fields.pop(f)
        self.fields["preferred_contact"].choices = [c for c in self.fields["preferred_contact"].choices if c[0]]

    def clean_hp_leave_empty(self):
        if self.cleaned_data.get("hp_leave_empty"):
            raise forms.ValidationError("Please clear the hidden field and try again.")
        return ""

    def clean(self):
        data = super().clean()
        ci, co = data.get("check_in"), data.get("check_out")
        if ci and co and co <= ci:
            self.add_error("check_out", "Check-out must be after check-in.")
        from django.utils import timezone

        if ci and ci < timezone.localdate():
            self.add_error("check_in", "Date can't be in the past.")
        return data


class ListingForm(forms.ModelForm):
    island = forms.ModelChoiceField(
        queryset=Island.objects.filter(is_published=True).select_related("atoll").order_by("atoll__order", "name"),
        help_text="Can't find your island? <a href='/suggest-island/' target='_blank'>Suggest an island</a>.",
    )
    amenities = forms.ModelMultipleChoiceField(
        queryset=Amenity.objects.all(), required=False, widget=forms.CheckboxSelectMultiple
    )
    activity_types = forms.ModelMultipleChoiceField(
        queryset=ActivityType.objects.all(), required=False, widget=forms.CheckboxSelectMultiple,
        label="Experiences offered",
    )

    class Meta:
        model = Listing
        fields = [
            "kind", "name", "island", "short_description", "description", "logo", "cover_image",
            "room_count", "max_guests", "star_rating", "distance_to_beach_m", "check_in_time", "check_out_time",
            "house_rules", "amenities", "activity_types", "cuisine", "opening_hours", "serves_breakfast", "delivery",
            "price_from", "currency", "price_unit",
            "contact_name", "contact_email", "contact_phone", "whatsapp", "viber",
            "website", "facebook", "instagram", "address", "registration_number",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
            "house_rules": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "price_from": "Starting price (optional, indicative)",
            "distance_to_beach_m": "Distance to beach (metres)",
        }

    GROUPS = {
        "basics": ["kind", "name", "island", "short_description", "description", "logo", "cover_image"],
        "stay": ["room_count", "max_guests", "star_rating", "distance_to_beach_m", "check_in_time", "check_out_time",
                 "house_rules", "amenities"],
        "food": ["cuisine", "opening_hours", "serves_breakfast", "delivery"],
        "pricing": ["price_from", "currency", "price_unit"],
        "contact": ["contact_name", "contact_email", "contact_phone", "whatsapp", "viber", "website", "facebook",
                    "instagram", "address", "registration_number"],
    }

    def __getattr__(self, name):
        if name in ListingForm.GROUPS:
            return [self[f] for f in ListingForm.GROUPS[name] if f in self.fields]
        raise AttributeError(name)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not settings.SHOW_PRICES:
            for f in ListingForm.GROUPS["pricing"]:
                self.fields.pop(f)
        self.fields["island"].label_from_instance = lambda i: f"{i.name} — {i.atoll.name}"


RoomFormSet = inlineformset_factory(
    Listing, RoomType, fields=["name", "description", "max_guests"] + (["price_from"] if settings.SHOW_PRICES else []),
    extra=2, can_delete=True,
    labels={"name": "Room / package name", "price_from": "From price"},
)


RouteFormSet = inlineformset_factory(
    Listing, TransportRoute, fk_name="operator",
    fields=["island", "mode", "origin", "via", "duration", "schedule", "notes", "is_active"]
    + (["price_from", "currency", "price_note"] if settings.SHOW_PRICES else []),
    extra=2, can_delete=True,
    labels={"island": "To island", "origin": "From", "price_from": "Price from"},
)


class VerificationForm(forms.ModelForm):
    class Meta:
        model = Listing
        fields = ["registration_number", "verification_document"]
        labels = {"registration_number": "Tourism licence / registration number"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["registration_number"].required = True
        self.fields["verification_document"].required = not (self.instance and self.instance.verification_document)

    def clean_verification_document(self):
        f = self.cleaned_data.get("verification_document")
        if f and hasattr(f, "size") and f.size > 8 * 1024 * 1024:
            raise forms.ValidationError("Please upload a file smaller than 8 MB.")
        if f and hasattr(f, "name") and not f.name.lower().rsplit(".", 1)[-1] in ("pdf", "jpg", "jpeg", "png", "webp"):
            raise forms.ValidationError("Upload a PDF, JPG or PNG.")
        return f


class PhotoUploadForm(forms.Form):
    image = forms.ImageField()
    caption = forms.CharField(max_length=120, required=False)


class EnquiryUpdateForm(forms.ModelForm):
    class Meta:
        model = Enquiry
        fields = ["status", "owner_notes"]
        widgets = {"owner_notes": forms.Textarea(attrs={"rows": 3})}


class IslandSuggestionForm(forms.ModelForm):
    class Meta:
        model = IslandSuggestion
        fields = ["island_name", "atoll", "contact_email", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}



class ClaimForm(forms.ModelForm):
    class Meta:
        from .models import ListingClaim

        model = ListingClaim
        fields = ["full_name", "role", "phone", "message", "document"]
        widgets = {"message": forms.Textarea(attrs={"rows": 3})}


class ReviewForm(forms.ModelForm):
    class Meta:
        from .models import Review

        model = Review
        fields = ["rating", "title", "text", "name", "country", "visited"]
        widgets = {"rating": forms.RadioSelect(), "text": forms.Textarea(attrs={"rows": 5, "placeholder": "What was it like? The room, the host, the island, the trips…"}),
                   "title": forms.TextInput(attrs={"placeholder": "Sum it up in a few words"})}
        labels = {"title": "Title (optional)"}


class HostReplyForm(forms.Form):
    reply = forms.CharField(label="Your reply (shown under the review)", widget=forms.Textarea(attrs={"rows": 3}), max_length=1500)
