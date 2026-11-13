import io

from django import forms
from django.contrib import admin, messages
from django.core.management import call_command
from django.db.models import Count, Q
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from unfold.admin import ModelAdmin, StackedInline, TabularInline
from unfold.contrib.filters.admin import ChoicesDropdownFilter, RelatedDropdownFilter
from unfold.decorators import action, display
from unfold.enums import ActionVariant

from . import notifications
from .admin_photos import PhotoManagerMixin
from .models import ContributionPhoto, Guide, GuideTemplate, HomeFeature, IslandContribution, ListingClaim, PageBanner, Review, ActivityType, Amenity, Atoll, Enquiry, Island, IslandSuggestion, IslandPhoto, Listing, ListingPhoto, RoomType, TransportRoute

LISTING_STATUS_COLORS = {"pending": "warning", "approved": "success", "rejected": "danger", "suspended": "danger"}
ENQUIRY_STATUS_COLORS = {"new": "warning", "replied": "info", "confirmed": "success", "declined": "danger", "closed": "info"}


class BaseAdmin(ModelAdmin):
    """Shared back-office behaviour: compact forms, filters applied with a button, unsaved-changes warning."""

    # Quick-view tabs above the list: (label, query parameters, Q filter for the count). See admin/_list_header.html.
    list_before_template = "admin/_list_before.html"
    list_tabs = None

    # Many-to-many fields shown as tick boxes (one click per activity / amenity) instead of the two-box picker.
    checkbox_m2m = ()

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name in self.checkbox_m2m:
            from unfold.widgets import UnfoldAdminCheckboxSelectMultipleWidget

            kwargs["widget"] = UnfoldAdminCheckboxSelectMultipleWidget(attrs={"class": "is-chip-checks"})
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        # Text areas start short and grow with their content (see admin.css / auto-grow script).
        from django import forms as dj_forms

        if field is not None and isinstance(field.widget, dj_forms.Textarea):
            field.widget.attrs.update({"rows": 3, "data-autogrow": "1"})
        return field

    compressed_fields = True
    warn_unsaved_form = True
    list_filter_submit = True
    list_per_page = 50


def photo_preview(url, credit="", license=""):
    if not url:
        return "No photo yet. Run \"Find photos\" from the island list, or paste a link below."
    return format_html('<img src="{}" style="max-width:420px;border-radius:8px;display:block"><small>{} {}</small>',
                       url, credit, f"· {license}" if license else "")


# ---------------------------------------------------------------- reference data

@admin.register(Atoll)
class AtollAdmin(BaseAdmin):
    list_display = ("atoll", "code", "region", "order", "island_count")
    list_editable = ("order",)
    list_filter = (("region", ChoicesDropdownFilter),)
    search_fields = ("name", "official_name")
    prepopulated_fields = {"slug": ("name",)}

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_n=Count("islands"))

    @display(description="Atoll", header=True, ordering="name")
    def atoll(self, obj):
        return [obj.name, obj.official_name]

    @display(description="Island guides", ordering="_n")
    def island_count(self, obj):
        return obj._n


@admin.register(ActivityType)
class ActivityTypeAdmin(BaseAdmin):
    list_display = ("activity", "description", "island_count")
    list_display_links = ("activity",)
    fieldsets = (
        (None, {"fields": (("name", "slug"), "icon", "description")}),
        ("Photo", {"fields": ("photo_preview", "photo_search", "image_url", ("image_credit", "image_license"), "image_source_url")}),
    )
    readonly_fields = ("photo_preview",)

    @display(description="Experience", header=True, ordering="name")
    def activity(self, obj):
        image = {"path": obj.thumb_url, "squared": True} if obj.image_url else None
        return [obj.name, obj.photo_search, obj.name[:2], image]

    @display(description="Current photo")
    def photo_preview(self, obj):
        return photo_preview(obj.thumb_url, obj.image_credit, obj.image_license)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_n=Count("islands", distinct=True))

    @display(description="Islands", ordering="_n")
    def island_count(self, obj):
        return obj._n


@admin.register(Amenity)
class AmenityAdmin(BaseAdmin):
    list_display = ("name", "icon")
    search_fields = ("name",)


# ---------------------------------------------------------------- islands

class PhotoFilter(admin.SimpleListFilter):
    title = "cover photo"
    parameter_name = "photo"

    def lookups(self, request, model_admin):
        return [("yes", "Has a photo"), ("no", "No photo yet")]

    def queryset(self, request, qs):
        has_photo = ~(Q(cover_image="") & Q(cover_image_url=""))
        if self.value() == "yes":
            return qs.filter(has_photo)
        if self.value() == "no":
            return qs.exclude(has_photo)
        return qs


class IslandRouteInline(TabularInline):
    model = TransportRoute
    fk_name = "island"
    extra = 0
    tab = True
    verbose_name_plural = "Transport routes"
    fields = ("mode", "origin", "via", "operator", "operator_name", "duration", "schedule", "is_active", "order")
    autocomplete_fields = ("operator",)


class IslandPhotoInline(TabularInline):
    model = IslandPhoto
    extra = 0
    tab = True
    verbose_name_plural = "Photo gallery"
    fields = ("preview", "image_url", "caption", "credit", "license", "source_url", "order", "is_visible")
    readonly_fields = ("preview",)

    @display(description="Photo")
    def preview(self, obj):
        return format_html('<img src="{}" style="width:96px;height:64px;object-fit:cover;border-radius:6px">', obj.thumb_url) if obj.pk else "–"


def _fetch_photos(admin_obj, request, islands):
    out = io.StringIO()
    for island in islands:
        call_command("fetch_island_photos", island=island.slug, force=True, stdout=out, stderr=out)
    lines = [line for line in out.getvalue().splitlines() if line.strip()]
    admin_obj.message_user(request, " ".join(lines[-6:]) or "Done.")


@admin.register(Island)
class IslandAdmin(PhotoManagerMixin, BaseAdmin):
    photo_kind = "island"
    change_form_before_template = "admin/ai_assist_island.html"
    inlines = [IslandRouteInline]
    list_display = ("island", "atoll", "island_type", "population", "listing_count", "has_photo", "is_featured", "is_published")
    list_display_links = ("island",)
    list_editable = ("is_featured", "is_published")
    list_filter = (
        ("atoll", RelatedDropdownFilter), ("island_type", ChoicesDropdownFilter), PhotoFilter,
        "is_published", "is_featured", "details_verified", "has_bikini_beach",
    )
    search_fields = ("name", "atoll__name", "tagline")
    prepopulated_fields = {"slug": ("name",)}
    checkbox_m2m = ("activities",)
    actions = ["fetch_photos"]
    actions_detail = ["fetch_photo_detail"]
    actions_list = ["fetch_missing_photos"]

    @action(description="Find missing photos", icon="add_photo_alternate", url_path="fetch-missing-photos")
    def fetch_missing_photos(self, request):
        out = io.StringIO()
        call_command("fetch_island_photos", max_seconds=40, stdout=out, stderr=out)
        lines = [line for line in out.getvalue().splitlines() if line.strip()]
        self.message_user(request, " ".join(lines[-4:]) or "Done.")
        return redirect(reverse("admin:directory_island_changelist"))
    fieldsets = (
        ("Overview", {"classes": ["tab"], "fields": (
            ("name", "slug"), ("atoll", "island_type"), "tagline", ("is_published", "is_featured"),
            "overview", "famous_for", "what_to_expect", "best_time_to_visit", "activities")}),
        ("Getting there", {"classes": ["tab"], "fields": (
            "getting_there", "transfer_types", ("distance_from_airport_km", "transfer_time"), ("nearest_airport", "nearest_airport_km"))}),
        ("Facilities & rules", {"classes": ["tab"], "fields": (
            "details_verified", ("has_bikini_beach", "has_atm", "has_hospital", "has_full_hospital"), ("has_pharmacy", "has_police", "has_supermarket"), ("has_4g", "has_5g"),
            "facilities_notes", "local_rules", "accessibility")}),
        ("Facts & sources", {"classes": ["tab"], "fields": (
            ("population", "population_year", "area_km2"), "sources", "wikipedia_title", ("latitude", "longitude"))}),
    )
    readonly_fields = ("cover_preview",)

    @display(description="Current cover")
    def cover_preview(self, obj):
        return photo_preview(obj.card_photo_url, obj.cover_credit, obj.cover_license)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("atoll").annotate(_n=Count("listings"))

    @display(description="Island", header=True, ordering="name")
    def island(self, obj):
        image = {"path": obj.card_photo_url, "squared": True} if obj.photo_url else None
        return [obj.name, obj.tagline, obj.name[:2], image]

    @display(description="Listings", ordering="_n")
    def listing_count(self, obj):
        return obj._n

    @display(description="Photo", boolean=True)
    def has_photo(self, obj):
        return bool(obj.photo_url)

    @admin.action(description="Find photos on Wikimedia Commons")
    def fetch_photos(self, request, queryset):
        _fetch_photos(self, request, queryset)

    @action(description="Find photos on Wikimedia", icon="add_photo_alternate", url_path="fetch-photo")
    def fetch_photo_detail(self, request, object_id):
        _fetch_photos(self, request, Island.objects.filter(pk=object_id))
        return redirect(reverse("admin:directory_island_change", args=[object_id]))



# ---------------------------------------------------------------- listings

class PhotoInline(TabularInline):
    model = ListingPhoto
    extra = 0
    tab = True
    verbose_name_plural = "Photo gallery"


class RoomInline(TabularInline):
    model = RoomType
    extra = 0
    tab = True
    verbose_name_plural = "Rooms & packages"


class OperatorRouteInline(StackedInline):
    model = TransportRoute
    fk_name = "operator"
    extra = 0
    tab = True
    verbose_name_plural = "Routes operated"
    fields = (("island", "mode"), ("origin", "duration"), "schedule", "is_active")
    autocomplete_fields = ("island",)


class VerificationFilter(admin.SimpleListFilter):
    title = "verification"
    parameter_name = "verification"

    def lookups(self, request, model_admin):
        return [("requested", "Requested, awaiting review"), ("verified", "Verified"), ("none", "Not requested")]

    def queryset(self, request, qs):
        if self.value() == "requested":
            return qs.filter(verification_requested_at__isnull=False, is_verified=False)
        if self.value() == "verified":
            return qs.filter(is_verified=True)
        if self.value() == "none":
            return qs.filter(verification_requested_at__isnull=True, is_verified=False)
        return qs


class ListingAdminForm(forms.ModelForm):
    owner_email = forms.EmailField(
        label="Owner's email", required=False,
        help_text="Type any email to give the owner this listing. If they don't have an account yet, one is created for you "
                  "(no password yet) and you get an invite link to send them. Leave empty to keep the listing with Island Stay.")

    class Meta:
        model = Listing
        exclude = ("owner",)  # set from 'Owner's email' (see ListingAdmin.save_model)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from unfold.widgets import UnfoldAdminEmailInputWidget, UnfoldAdminTextInputWidget
        self.fields["owner_email"].widget = UnfoldAdminEmailInputWidget(attrs={"placeholder": "e.g. owner@tropicaltree.mv", "autocomplete": "off"})
        if "slug" in self.fields:
            self.fields["slug"].validators = []  # clean_slug turns anything typed into a valid address
            self.fields["slug"].label = "Page address"
            self.fields["slug"].help_text = ("Fills in from the name and island. Keep it short; changing it later breaks links people "
                                             "have already shared.")
            self.fields["slug"].widget = UnfoldAdminTextInputWidget(attrs={"prefix_icon": "link", "placeholder": "fills in from the name"})
        if "name" in self.fields:
            self.fields["name"].widget.attrs.setdefault("placeholder", "e.g. Maarehi Thoddoo")
        if "contact_email" in self.fields:
            self.fields["contact_email"].required = False
        owner = self.instance.owner if self.instance.pk and self.instance.owner_id else None
        if owner and not owner.is_staff:
            self.fields["owner_email"].initial = owner.email

    def clean_slug(self):
        from django.utils.text import slugify
        from .models import unique_slug
        value = slugify(self.cleaned_data.get("slug") or "")[:60]
        if value and Listing.objects.filter(slug=value).exclude(pk=self.instance.pk).exists():
            value = unique_slug(self.instance, value)  # taken: add -2, -3 ...
        return value

    def clean(self):
        data = super().clean()
        email = (data.get("owner_email") or "").strip().lower()
        data["owner_email"] = email
        if not data.get("contact_email"):
            if email:
                data["contact_email"] = email  # booking requests go to the owner
            else:
                self.add_error("contact_email", "Enter the email where booking requests should go (or the owner's email).")
        return data


@admin.register(Listing)
class ListingAdmin(PhotoManagerMixin, BaseAdmin):
    form = ListingAdminForm
    list_tabs = [
        ("All", {}, None),
        ("Pending review", {"status__exact": "pending"}, Q(status="pending")),
        ("Live", {"status__exact": "approved"}, Q(status="approved")),
        ("Verification requests", {"verification": "requested"}, Q(verification_requested_at__isnull=False, is_verified=False)),
        ("Suspended", {"status__exact": "suspended"}, Q(status="suspended")),
        ("Rejected", {"status__exact": "rejected"}, Q(status="rejected")),
    ]
    photo_kind = "listing"

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        initial.setdefault("is_claimed", False)
        initial.setdefault("status", Listing.STATUS_APPROVED)
        return initial

    change_form_before_template = "admin/ai_assist_listing.html"
    list_display = ("business", "kind_label", "island_name", "status_label", "verified_label", "is_featured", "enquiry_count", "submitted")
    list_display_links = ("business",)
    list_filter = (
        ("status", ChoicesDropdownFilter), VerificationFilter, ("kind", ChoicesDropdownFilter),
        ("island__atoll", RelatedDropdownFilter), ("island", RelatedDropdownFilter), "is_featured", "is_claimed",
    )
    search_fields = ("name", "island__name", "owner__email", "contact_email", "registration_number")
    autocomplete_fields = ("island",)
    checkbox_m2m = ("amenities", "activity_types")
    inlines = [RoomInline, OperatorRouteInline]
    actions = ["approve", "reject", "suspend", "verify"]
    actions_row = ["approve_row"]
    actions_detail = ["approve_detail", "reject_detail", "verify_detail"]
    readonly_fields = ("created_at", "updated_at", "verified_at", "verification_requested_at", "owner_access")
    fieldsets = (
        ("Business", {"classes": ["tab"], "fields": (
            ("name", "slug"), ("kind", "island"), "owner_email", "owner_access", "short_description", "description")}),
        ("Review & verification", {"classes": ["tab"], "fields": (
            ("status", "is_featured", "is_claimed"), "admin_note", ("is_verified", "registration_number"), "verification_document",
            ("verification_requested_at", "verified_at"), ("created_at", "updated_at"))}),
        ("Details", {"classes": ["tab"], "fields": (
            ("room_count", "max_guests", "star_rating"), ("distance_to_beach_m", "check_in_time", "check_out_time"), "house_rules",
            ("cuisine", "opening_hours"), ("serves_breakfast", "delivery"), "amenities", "activity_types",
            ("price_from", "currency", "price_unit"))}),
        ("Contact", {"classes": ["tab"], "fields": (
            ("contact_name", "contact_email"), ("contact_phone", "whatsapp", "viber"), ("website", "facebook", "instagram"), "address")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("island", "owner").annotate(_n=Count("enquiries"))

    @display(description="Business", header=True, ordering="name")
    def business(self, obj):
        image = {"path": obj.cover_image.url, "squared": True} if obj.cover_image else None
        return [obj.name, obj.owner.email, obj.name[:2], image]

    @display(description="Island", ordering="island__name")
    def island_name(self, obj):
        return obj.island.name

    @display(description="Type", ordering="kind")
    def kind_label(self, obj):
        return obj.get_kind_display()

    @display(description="Status", ordering="status", label=LISTING_STATUS_COLORS)
    def status_label(self, obj):
        return obj.status, obj.get_status_display()

    @display(description="Verified", label={"yes": "success", "requested": "warning", "no": "info"})
    def verified_label(self, obj):
        if obj.is_verified:
            return "yes", "Verified"
        if obj.verification_requested_at:
            return "requested", "Requested"
        return "no", "Not verified"

    @display(description="Requests", ordering="_n")
    def enquiry_count(self, obj):
        return obj._n

    def get_fieldsets(self, request, obj=None):
        sets = super().get_fieldsets(request, obj)
        if obj is None:  # new listing: nothing to show under 'Owner access' yet
            sets = [(name, {**opts, "fields": tuple(f for f in opts["fields"] if f != "owner_access")}) for name, opts in sets]
        return sets

    @display(description="Owner access")
    def owner_access(self, obj):
        from accounts.invites import invite_link
        owner = obj.owner if obj and obj.pk else None
        if not owner or owner.is_staff:
            return "Held by Island Stay. Type the owner's email above to give it to them."
        if owner.has_usable_password():
            return format_html("<b>{}</b> manages this listing (they have set a password).", owner.email)
        link = invite_link(owner)
        first = (obj.contact_name or "").split(" ")[0] or f"{obj.name} team"
        msg = (f"Hello {first},\n\nYour Island Stay page for {obj.name} is ready. To manage it (photos, prices and booking "
               f"requests), choose your password here:\n{link}\n\nThe link works for 14 days.\n\nKind regards,\nIsland Stay team")
        return format_html(
            '<div style="display:flex;flex-direction:column;gap:8px;max-width:640px">'
            '<span><b>{}</b> has an account but hasn\'t set a password yet. Send them this invite:</span>'
            '<input type="text" readonly value="{}" onclick="this.select()" style="width:100%;border:1px solid #7D9399;border-radius:8px;padding:6px 10px;font-size:13px">'
            '<span style="display:flex;gap:8px;flex-wrap:wrap">'
            '<button type="button" data-msg="{}" onclick="navigator.clipboard.writeText(this.dataset.msg);this.textContent=\'Copied\'" '
            'style="padding:6px 14px;border-radius:999px;background:#0B6E8A;color:#fff;font-weight:600;font-size:13px">Copy invite message</button>'
            '<button type="button" data-msg="{}" onclick="navigator.clipboard.writeText(this.dataset.msg);this.textContent=\'Copied\'" '
            'style="padding:6px 14px;border-radius:999px;border:1px solid #7D9399;font-weight:600;font-size:13px">Copy link only</button></span>'
            '<small style="color:#4A6068">Works for 14 days and stops working once they set a password. Reload this page for a fresh link.</small></div>',
            owner.email, link, msg, link)

    def save_model(self, request, obj, form, change):
        from accounts.invites import owner_for_email
        email = form.cleaned_data.get("owner_email")
        created = False
        current = obj.owner if obj.owner_id else None
        if email:
            if not current or current.email.lower() != email:
                obj.owner, created = owner_for_email(email, obj.name)
            obj.is_claimed = True
        elif not current or not current.is_staff:
            obj.owner = request.user  # empty: the listing stays with Island Stay until it's claimed
            obj.is_claimed = False
        if not obj.contact_email:
            obj.contact_email = email or request.user.email
        if obj.is_verified and not obj.verified_at:
            obj.verified_at = timezone.now()
        elif not obj.is_verified:
            obj.verified_at = None
        status_changed = change and "status" in form.changed_data
        super().save_model(request, obj, form, change)
        if status_changed:
            notifications.listing_status_changed(obj)
        if email and not obj.owner.has_usable_password():
            messages.success(request, f"{'Created an owner account for' if created else 'Linked the owner account'} {email}. "
                                      "Open the Business tab to copy their invite link and send it to them.")

    def _set_status(self, request, queryset, status):
        n = 0
        for listing in queryset.exclude(status=status):
            listing.status = status
            listing.save(update_fields=["status", "updated_at"])
            notifications.listing_status_changed(listing)
            n += 1
        self.message_user(request, f"{n} listing(s) updated and owners notified by email.", messages.SUCCESS)

    def _mark_verified(self, request, queryset):
        n = queryset.filter(is_verified=False).update(is_verified=True, verified_at=timezone.now())
        self.message_user(request, f"{n} listing(s) marked as Verified host.", messages.SUCCESS)

    # Bulk actions (tick listings, choose an action)
    @admin.action(description="Approve and publish")
    def approve(self, request, queryset):
        self._set_status(request, queryset, Listing.STATUS_APPROVED)

    @admin.action(description="Reject (owner can edit and resubmit)")
    def reject(self, request, queryset):
        self._set_status(request, queryset, Listing.STATUS_REJECTED)

    @admin.action(description="Mark as Verified host")
    def verify(self, request, queryset):
        self._mark_verified(request, queryset)

    @admin.action(description="Suspend (hide from the website)")
    def suspend(self, request, queryset):
        self._set_status(request, queryset, Listing.STATUS_SUSPENDED)

    def get_actions_detail(self, request, object_id):
        """Only offer the buttons that make sense for this listing's current state."""
        listing = Listing.objects.filter(pk=object_id).first()
        hidden = set()
        if listing:
            if listing.status == Listing.STATUS_APPROVED:
                hidden.add("approve_detail")
            if listing.status == Listing.STATUS_REJECTED:
                hidden.add("reject_detail")
            if listing.is_verified:
                hidden.add("verify_detail")
        return [a for a in super().get_actions_detail(request, object_id) if not any(a.action_name.endswith(h) for h in hidden)]

    @display(description="Submitted", ordering="created_at")
    def submitted(self, obj):
        from django.utils.html import format_html
        return format_html('<span style="white-space:nowrap">{}</span>', obj.created_at.strftime("%d %b %Y"))

    # One-click buttons
    @action(description="Approve", icon="check_circle", url_path="approve-row")
    def approve_row(self, request, object_id):
        self._set_status(request, Listing.objects.filter(pk=object_id), Listing.STATUS_APPROVED)
        return redirect(request.META.get("HTTP_REFERER") or reverse("admin:directory_listing_changelist"))

    @action(description="Approve & publish", icon="check_circle", url_path="approve", variant=ActionVariant.SUCCESS)
    def approve_detail(self, request, object_id):
        self._set_status(request, Listing.objects.filter(pk=object_id), Listing.STATUS_APPROVED)
        return redirect(reverse("admin:directory_listing_change", args=[object_id]))

    @action(description="Reject", icon="block", url_path="reject", variant=ActionVariant.DANGER)
    def reject_detail(self, request, object_id):
        self._set_status(request, Listing.objects.filter(pk=object_id), Listing.STATUS_REJECTED)
        return redirect(reverse("admin:directory_listing_change", args=[object_id]))

    @action(description="Mark verified", icon="verified", url_path="verify")
    def verify_detail(self, request, object_id):
        self._mark_verified(request, Listing.objects.filter(pk=object_id))
        return redirect(reverse("admin:directory_listing_change", args=[object_id]))


# ---------------------------------------------------------------- requests & suggestions

@admin.register(Enquiry)
class EnquiryAdmin(BaseAdmin):
    list_tabs = [
        ("All", {}, None), ("New", {"status__exact": "new"}, Q(status="new")), ("Replied", {"status__exact": "replied"}, Q(status="replied")),
        ("Confirmed", {"status__exact": "confirmed"}, Q(status="confirmed")), ("Declined", {"status__exact": "declined"}, Q(status="declined")),
        ("Closed", {"status__exact": "closed"}, Q(status="closed")),
    ]
    list_display = ("reference_col", "guest", "listing", "dates", "party", "origin", "sent_label", "status_label")
    list_display_links = ("reference_col",)
    list_filter = (("status", ChoicesDropdownFilter), ("sent_via", ChoicesDropdownFilter), ("listing__kind", ChoicesDropdownFilter),
                   ("listing__island", RelatedDropdownFilter), "needs_transfer", "device", "source", "created_at")
    search_fields = ("reference", "guest_name", "guest_email", "guest_phone", "listing__name", "listing__island__name")
    readonly_fields = ("reference", "created_at", "updated_at", "sent_via", "sent_at", "visitor_link", "source", "campaign",
                       "landing_path", "country", "city", "device", "browser", "os", "language", "nights_col", "lead_col")
    autocomplete_fields = ("listing",)
    date_hierarchy = "created_at"
    actions = ["mark_closed", "export_csv"]
    actions_list = ["open_analytics"]
    fieldsets = (
        ("Request", {"classes": ["tab"], "fields": (
            ("reference", "status"), "listing", ("check_in", "check_out"), ("nights_col", "lead_col"),
            ("adults", "children", "rooms"), "room_type", "needs_transfer", "message", "owner_notes")}),
        ("Guest", {"classes": ["tab"], "fields": (
            ("guest_name", "guest_email"), ("guest_phone", "guest_country"), "preferred_contact", ("sent_via", "sent_at"))}),
        ("Source & device", {"classes": ["tab"], "fields": (
            "visitor_link", ("source", "campaign"), "landing_path", ("country", "city", "language"), ("device", "browser", "os"),
            ("created_at", "updated_at"))}),
    )

    @display(description="Guest journey")
    def visitor_link(self, obj):
        if not obj.visitor_id:
            return "Not available: the guest didn't accept analytics cookies"
        url = reverse("admin:analytics_visitor_change", args=[obj.visitor_id])
        return format_html('<a class="text-primary-600 font-semibold" href="{}">See every page and click before this request</a>', url)

    @display(description="Nights")
    def nights_col(self, obj):
        return obj.nights or "–"

    @display(description="Days before arrival")
    def lead_col(self, obj):
        return obj.lead_days if obj.lead_days is not None else "–"

    @display(description="From", header=True)
    def origin(self, obj):
        from analytics.utils import country_name

        place = ", ".join(x for x in (obj.city, country_name(obj.country) if obj.country else "") if x)
        return [place or obj.guest_country or "–", " · ".join(x for x in (obj.source, obj.device) if x)]

    @display(description="Sent to host", label={"Not yet": "warning", "WhatsApp": "success", "Viber": "success",
                                                 "Email": "success", "Phone call": "success", "Copied the message": "info"})
    def sent_label(self, obj):
        return obj.get_sent_via_display() or "Not yet"

    @action(description="Analytics", icon="insights", url_path="go-analytics")
    def open_analytics(self, request):
        return redirect("admin:analytics_dashboard")

    @admin.action(description="Export selected to CSV (Excel)")
    def export_csv(self, request, queryset):
        import csv

        from django.http import HttpResponse

        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="booking-requests-{timezone.localdate()}.csv"'
        resp.write("\ufeff")
        w = csv.writer(resp)
        cols = ["Reference", "Received", "Status", "Listing", "Type", "Island", "Atoll", "Check-in", "Check-out", "Nights",
                "Days before arrival", "Adults", "Children", "Rooms", "Room / package", "Transfer", "Guest", "Email", "Phone",
                "Guest country", "Reply by", "Sent to host via", "Sent at", "Found us via", "Campaign", "First page",
                "Country (detected)", "City", "Device", "Browser", "OS", "Language", "Message"]
        w.writerow(cols)
        for e in queryset.select_related("listing", "listing__island", "listing__island__atoll"):
            w.writerow([e.reference, timezone.localtime(e.created_at).strftime("%Y-%m-%d %H:%M"), e.get_status_display(),
                        e.listing.name, e.listing.get_kind_display(), e.listing.island.name, e.listing.island.atoll.name,
                        e.check_in or "", e.check_out or "", e.nights or "", e.lead_days if e.lead_days is not None else "",
                        e.adults, e.children, e.rooms or "", e.room_type, "Yes" if e.needs_transfer else "No", e.guest_name,
                        e.guest_email, e.guest_phone, e.guest_country, e.get_preferred_contact_display(), e.get_sent_via_display(),
                        timezone.localtime(e.sent_at).strftime("%Y-%m-%d %H:%M") if e.sent_at else "", e.source, e.campaign,
                        e.landing_path, e.country, e.city, e.device, e.browser, e.os, e.language, e.message])
        return resp

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("listing", "listing__island")

    @display(description="Request", header=True, ordering="reference")
    def reference_col(self, obj):
        return [obj.reference, obj.created_at.strftime("%d %b %Y, %H:%M")]

    @display(description="Guest", header=True, ordering="guest_name")
    def guest(self, obj):
        return [obj.guest_name, obj.guest_country or obj.guest_email]

    @display(description="Dates", ordering="check_in")
    def dates(self, obj):
        if not obj.check_in:
            return "–"
        return obj.check_in.strftime("%d %b") + (f" – {obj.check_out.strftime('%d %b %Y')}" if obj.check_out else "")

    @display(description="Guests")
    def party(self, obj):
        return f"{obj.adults} + {obj.children}" if obj.children else str(obj.adults)

    @display(description="Status", ordering="status", label=ENQUIRY_STATUS_COLORS)
    def status_label(self, obj):
        return obj.status, obj.get_status_display()

    @admin.action(description="Mark as closed")
    def mark_closed(self, request, queryset):
        n = queryset.update(status="closed")
        self.message_user(request, f"{n} request(s) closed.", messages.SUCCESS)


@admin.register(IslandSuggestion)
class IslandSuggestionAdmin(BaseAdmin):
    list_display = ("island_name", "atoll", "submitted_by", "contact_email", "handled", "created_at")
    list_editable = ("handled",)
    list_filter = ("handled",)
    search_fields = ("island_name", "contact_email")


@admin.register(TransportRoute)
class TransportRouteAdmin(BaseAdmin):
    list_display = ("route", "mode_label", "provider", "duration", "schedule", "is_active")
    list_display_links = ("route",)
    list_filter = (("mode", ChoicesDropdownFilter), "is_active", ("island", RelatedDropdownFilter))
    list_editable = ("is_active",)
    search_fields = ("island__name", "origin", "operator__name", "operator_name")
    autocomplete_fields = ("island", "operator")
    fieldsets = (
        (None, {"fields": (("island", "mode"), ("origin", "via"), ("operator", "operator_name"), ("duration", "schedule"),
                           "notes", ("price_from", "currency", "price_note"), ("is_active", "order"))}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("island", "operator")

    @display(description="Route", header=True, ordering="island__name")
    def route(self, obj):
        return [f"To {obj.island.name}", f"From {obj.origin}"]

    @display(description="Type", ordering="mode", label={
        "ferry": "info", "speedboat": "success", "private": "success", "flight": "warning", "seaplane": "warning"})
    def mode_label(self, obj):
        return obj.mode, obj.get_mode_display()


@admin.register(HomeFeature)
class HomeFeatureAdmin(BaseAdmin):
    list_display = ("island_col", "section_label", "has_photo", "is_active")
    list_display_links = ("island_col",)
    list_filter = ("section",)
    list_editable = ("is_active",)
    ordering_field = "order"
    hide_ordering_field = True
    autocomplete_fields = ("island",)
    fields = ("section", "island", "is_active")
    actions_list = ["view_home"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("island", "island__atoll").order_by("section", "order", "id")

    @display(description="Island", header=True)
    def island_col(self, obj):
        return obj.island.name, obj.island.atoll.name

    @display(description="Where on the home page", label={"hero": "info", "portrait": "success", "popular": "warning"})
    def section_label(self, obj):
        return obj.section, {"hero": "Slideshow", "portrait": "Island portraits", "popular": "Popular links"}[obj.section]

    @display(description="Photo", boolean=True)
    def has_photo(self, obj):
        return bool(obj.island.photo_url)

    def save_model(self, request, obj, form, change):
        if not change and not obj.order:
            last = HomeFeature.objects.filter(section=obj.section).order_by("-order").first()
            obj.order = (last.order + 1) if last else 1
        super().save_model(request, obj, form, change)
        if obj.section == HomeFeature.SECTION_HERO and not obj.island.photo_url:
            messages.warning(request, f"{obj.island.name} has no photo, so it won't appear in the slideshow until you add one.")
        limit = HomeFeature.LIMITS[obj.section]
        n = HomeFeature.objects.filter(section=obj.section, is_active=True).count()
        if n > limit:
            messages.warning(request, f"{obj.get_section_display()}: only the first {limit} are shown ({n} are switched on).")

    @action(description="View home page", icon="open_in_new", url_path="view-home")
    def view_home(self, request):
        return redirect("/")


@admin.register(ListingClaim)
class ListingClaimAdmin(BaseAdmin):
    list_tabs = [("All", {}, None), ("Waiting for review", {"status__exact": "pending"}, Q(status="pending")),
                 ("Approved", {"status__exact": "approved"}, Q(status="approved")), ("Rejected", {"status__exact": "rejected"}, Q(status="rejected"))]
    list_display = ("claim", "listing", "phone", "status_label", "created_at")
    list_display_links = ("claim",)
    list_filter = (("status", ChoicesDropdownFilter),)
    search_fields = ("full_name", "phone", "listing__name", "user__email")
    readonly_fields = ("listing", "user", "full_name", "role", "phone", "message", "document", "created_at")
    fields = ("listing", "user", ("full_name", "role"), "phone", "message", "document", "status", "admin_note", "created_at")
    actions = ["approve_claims", "reject_claims"]
    actions_detail = ["approve_detail"]

    @display(description="Claim", header=True)
    def claim(self, obj):
        return obj.full_name, f"{obj.role} · {obj.user.email}"

    @display(description="Status", label={"pending": "warning", "approved": "success", "rejected": "danger"})
    def status_label(self, obj):
        return obj.status, obj.get_status_display()

    @admin.action(description="Approve: give the listing to the claimant")
    def approve_claims(self, request, queryset):
        n = 0
        for c in queryset.filter(status="pending").select_related("listing"):
            c.approve()
            n += 1
        self.message_user(request, f"{n} claim{'s' if n != 1 else ''} approved; the listings are now in the owners' dashboards.", messages.SUCCESS)

    @admin.action(description="Reject")
    def reject_claims(self, request, queryset):
        n = queryset.filter(status="pending").update(status="rejected")
        self.message_user(request, f"{n} claim{'s' if n != 1 else ''} rejected.", messages.SUCCESS)

    @action(description="Approve claim", icon="verified", url_path="approve-claim")
    def approve_detail(self, request, object_id):
        claim = ListingClaim.objects.get(pk=object_id)
        if claim.status == "pending":
            claim.approve()
            messages.success(request, f"{claim.listing.name} now belongs to {claim.full_name}.")
        return redirect(reverse("admin:directory_listingclaim_change", args=[object_id]))


@admin.register(Review)
class ReviewAdmin(BaseAdmin):
    list_tabs = [("All", {}, None), ("Waiting for review", {"status__exact": "pending"}, Q(status="pending")),
                 ("Published", {"status__exact": "published"}, Q(status="published")), ("Hidden", {"status__exact": "rejected"}, Q(status="rejected"))]
    list_display = ("review", "listing", "stars_col", "status_label", "created_at")
    list_display_links = ("review",)
    list_filter = (("status", ChoicesDropdownFilter), "rating", ("listing__island", RelatedDropdownFilter))
    search_fields = ("name", "text", "listing__name", "enquiry__reference")
    readonly_fields = ("enquiry", "created_at", "host_replied_at")
    autocomplete_fields = ("listing",)
    fields = ("listing", "enquiry", ("name", "country", "visited"), "rating", "title", "text", "status", "host_reply", ("created_at", "host_replied_at"))
    actions = ["publish", "hide"]

    @display(description="Review", header=True)
    def review(self, obj):
        return obj.title or obj.text[:60], f"{obj.name}{' · ' + obj.country if obj.country else ''}"

    @display(description="Rating")
    def stars_col(self, obj):
        return "★" * obj.rating + "☆" * (5 - obj.rating)

    @display(description="Status", label={"pending": "warning", "published": "success", "rejected": "danger"})
    def status_label(self, obj):
        return obj.status, obj.get_status_display()

    @admin.action(description="Publish")
    def publish(self, request, queryset):
        for r in queryset:
            r.status = "published"
            r.save()
        self.message_user(request, f"{queryset.count()} review(s) published.", messages.SUCCESS)

    @admin.action(description="Hide")
    def hide(self, request, queryset):
        for r in queryset:
            r.status = "rejected"
            r.save()
        self.message_user(request, f"{queryset.count()} review(s) hidden.", messages.SUCCESS)


@admin.register(PageBanner)
class PageBannerAdmin(BaseAdmin):
    list_display = ("page_col", "preview", "credit", "is_active", "updated_at")
    list_display_links = ("page_col",)
    list_editable = ("is_active",)
    fields = ("page", "preview_large", "image", "image_url", "credit", "is_active")
    readonly_fields = ("preview_large",)

    PATHS = {"stays": "/stays/", "experiences": "/experiences/", "transport": "/transport/", "food": "/food/",
             "list_business": "/list-your-business/", "islands": "/islands/", "atolls": "/atolls/", "how_it_works": "/how-it-works/", "guides": "/guides/", "shops": "/shops/", "home": "/"}

    @display(description="Page", header=True)
    def page_col(self, obj):
        return obj.get_page_display(), self.PATHS.get(obj.page, "")

    @display(description="Photo")
    def preview(self, obj):
        if not obj.url:
            return "–"
        return format_html('<img src="{}" style="width:120px;height:60px;object-fit:cover;border-radius:8px">', obj.url)

    @display(description="Current photo")
    def preview_large(self, obj):
        if not obj or not obj.url:
            return "No photo yet: the page uses an automatic island or activity photo."
        return format_html('<img src="{}" style="max-width:520px;width:100%;aspect-ratio:16/7;object-fit:cover;border-radius:12px">', obj.url)


class GuideForm(forms.ModelForm):
    blocks = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Guide
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        import json
        super().__init__(*args, **kwargs)
        self.initial["blocks"] = json.dumps(self.instance.blocks or [])

    def clean_blocks(self):
        import json
        from .guide_blocks import clean_blocks
        try:
            return clean_blocks(json.loads(self.cleaned_data.get("blocks") or "[]"))
        except ValueError:
            raise forms.ValidationError("The content blocks could not be read. Reload the page and try again.")


@admin.register(Guide)
class GuideAdmin(BaseAdmin):
    form = GuideForm
    list_display = ("title_col", "category", "words", "is_published", "is_featured", "published_at")
    list_display_links = ("title_col",)
    list_editable = ("is_published", "is_featured")
    list_filter = ("category", "is_published", "is_featured")
    search_fields = ("title", "summary", "body")
    filter_horizontal = ("islands",)
    prepopulated_fields = {"slug": ("title",)}
    change_form_before_template = "admin/guide_editor.html"
    fieldsets = (
        (None, {"fields": ("title", "slug", "category", "summary", "blocks", "body")}),
        ("Questions and answers", {"fields": ("faqs",)}),
        ("Islands and photo", {"fields": ("islands", "cover_image", "cover_image_url", "cover_credit")}),
        ("Publishing", {"fields": ("author", "is_published", "is_featured", "published_at")}),
    )

    @display(description="Guide", header=True)
    def title_col(self, obj):
        return obj.title, obj.get_absolute_url()

    @display(description="Length")
    def words(self, obj):
        return f"{len(obj.body.split())} words · {obj.reading_minutes} min"

    def get_urls(self):
        from django.urls import path
        return [path("preview/", self.admin_site.admin_view(self.preview_view), name="directory_guide_preview"),
                path("upload/", self.admin_site.admin_view(self.upload_view), name="directory_guide_upload")] + super().get_urls()

    def upload_view(self, request):
        """Photo upload for image blocks. Returns the stored file's address."""
        import uuid
        from django.core.files.storage import default_storage
        from django.http import JsonResponse
        from PIL import Image
        f = request.FILES.get("file")
        if request.method != "POST" or not f:
            return JsonResponse({"error": "Choose a photo to upload."}, status=400)
        if f.size > 12 * 1024 * 1024:
            return JsonResponse({"error": "That photo is larger than 12 MB."}, status=400)
        try:
            img = Image.open(f)
            img.verify()
            fmt = (img.format or "").lower()
        except Exception:
            return JsonResponse({"error": "That file isn't a photo we can read (use JPG, PNG or WebP)."}, status=400)
        ext = {"jpeg": "jpg", "png": "png", "webp": "webp", "gif": "gif"}.get(fmt)
        if not ext:
            return JsonResponse({"error": "Use a JPG, PNG or WebP photo."}, status=400)
        f.seek(0)
        name = default_storage.save(f"guides/{uuid.uuid4().hex[:12]}.{ext}", f)
        return JsonResponse({"url": default_storage.url(name)})

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        from django.middleware.csrf import get_token
        live = Listing.objects.filter(status=Listing.STATUS_APPROVED).select_related("island")
        extra_context["guide_templates"] = GuideTemplate.objects.filter(is_active=True)
        extra_context["ge_data"] = {
            "csrf": get_token(request),
            "preview": reverse("admin:directory_guide_preview"),
            "upload": reverse("admin:directory_guide_upload"),
            "templates": [{"id": t.pk, "name": t.name, "category": t.category, "title": t.title, "summary": t.summary,
                           "body": t.body, "faqs": t.faqs} for t in extra_context["guide_templates"]],
            "islands": [{"id": i.pk, "name": i.name, "slug": i.slug, "atoll": i.atoll.name, "time": i.transfer_time.lstrip("≈"),
                         "km": i.distance_from_airport_km or ""} for i in Island.objects.filter(is_published=True).select_related("atoll")],
            "pick": {
                "listings": [{"id": l.pk, "name": l.name, "sub": f"{l.get_kind_display()} · {l.island.name}",
                              "group": "stay" if l.kind in Listing.STAY_KINDS else "experience" if l.kind in Listing.EXPERIENCE_KINDS + Listing.TRANSPORT_KINDS else "other"}
                             for l in live],
                "guides": [{"id": g.pk, "name": g.title, "sub": g.get_category_display()} for g in Guide.objects.exclude(pk=object_id or 0)],
            },
        }
        return super().changeform_view(request, object_id, form_url, extra_context)

    def preview_view(self, request):
        """Render the unsaved guide with the real public template, for the live preview in the editor."""
        from django.http import HttpResponseNotAllowed
        from django.shortcuts import render
        from django.utils import timezone
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        P = request.POST
        cats = dict(Guide.CATEGORY_CHOICES)
        g = Guide(title=P.get("title") or "Untitled guide", slug="preview", summary=P.get("summary", ""),
                  body=P.get("body", ""), faqs=P.get("faqs", ""), category=P.get("category") if P.get("category") in cats else "planning",
                  cover_image_url=P.get("cover_image_url", ""), cover_credit=P.get("cover_credit", ""),
                  author=P.get("author") or "Island Stay team")
        g.published_at = g.updated_at = timezone.now()
        ids = [int(x) for x in P.getlist("islands") if x.isdigit()]
        islands = list(Island.objects.filter(pk__in=ids).select_related("atoll"))
        g.preview_islands = islands
        import json
        from .guide_blocks import blocks_to_text, clean_blocks
        from .views import guide_segments
        try:
            g.blocks = clean_blocks(json.loads(P.get("blocks") or "[]"))
        except ValueError:
            g.blocks = []
        if g.blocks:
            g.body = blocks_to_text(g.blocks)
        if not g.cover_image_url and P.get("current_photo"):
            g.cover_image_url = P["current_photo"]
        return render(request, "directory/guide_detail.html", {"guide": g, "islands": islands, "more": [], "ld": [], "preview": True,
                                                               "segments": guide_segments(g)})


@admin.register(GuideTemplate)
class GuideTemplateAdmin(BaseAdmin):
    list_display = ("name", "category", "description", "order", "is_active")
    list_editable = ("order", "is_active")
    fields = ("name", "description", "icon", "category", "title", "summary", "body", "faqs", "order", "is_active")


# ---------------------------------------------------------------- updates from the public
class ContributionPhotoInline(TabularInline):
    model = ContributionPhoto
    extra = 0
    fields = ("preview", "caption", "added_to_gallery")
    readonly_fields = ("preview", "added_to_gallery")
    can_delete = True

    @display(description="Photo")
    def preview(self, obj):
        try:
            return format_html('<a href="{0}" target="_blank"><img src="{0}" style="width:140px;height:96px;object-fit:cover;border-radius:8px"></a>', obj.image.url)
        except Exception:
            return "–"


@admin.register(IslandContribution)
class IslandContributionAdmin(BaseAdmin):
    list_tabs = [("All", {}, None), ("New", {"status__exact": "new"}, Q(status="new")),
                 ("Applied", {"status__exact": "applied"}, Q(status="applied")), ("Not used", {"status__exact": "rejected"}, Q(status="rejected"))]
    list_display = ("summary", "island_link", "relation", "answers", "photo_count", "status_label", "created_at")
    list_display_links = ("summary",)
    list_filter = ("status", ("island__atoll", RelatedDropdownFilter), "relation")
    search_fields = ("name", "email", "island__name", "famous_for", "tips", "corrections")
    readonly_fields = ("island", "name", "email", "relation", "answers_table", "transfer_time", "getting_there", "famous_for",
                       "tips", "corrections", "photo_credit", "photo_consent", "show_name", "created_at")
    fieldsets = (
        ("From", {"fields": (("island", "relation"), ("name", "email"), "show_name", "created_at")}),
        ("Facilities", {"fields": ("answers_table",)}),
        ("Information", {"fields": ("transfer_time", "getting_there", "famous_for", "tips", "corrections")}),
        ("Photos", {"fields": (("photo_credit", "photo_consent"),)}),
        ("Review", {"fields": ("status", "admin_note")}),
    )
    inlines = [ContributionPhotoInline]
    actions = ["apply_facilities", "add_photos", "apply_all", "mark_not_used"]
    actions_detail = ["apply_all_detail"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("island", "island__atoll").annotate(_photos=Count("photos"))

    @display(description="Update", header=True)
    def summary(self, obj):
        bits = []
        if obj.facilities:
            bits.append(f"{len(obj.facility_answers)} facility answers")
        if obj._photos:
            bits.append(f"{obj._photos} photo{'s' if obj._photos != 1 else ''}")
        if obj.famous_for or obj.tips or obj.getting_there or obj.corrections:
            bits.append("notes")
        return obj.name, " · ".join(bits) or "—"

    @display(description="Island")
    def island_link(self, obj):
        return format_html('<a href="{}" target="_blank">{}</a>', obj.island.get_absolute_url(), obj.island.name)

    @display(description="Answers")
    def answers(self, obj):
        return ", ".join(f"{l}: {v}" for l, v in obj.facility_answers)[:80] or "–"

    @display(description="Photos", ordering="_photos")
    def photo_count(self, obj):
        return obj._photos

    @display(description="Status", label={"New": "warning", "Applied": "success", "Not used": "danger"})
    def status_label(self, obj):
        return obj.get_status_display()

    @display(description="Facility answers")
    def answers_table(self, obj):
        rows = []
        for key, label in IslandContribution.FACILITIES:
            ans = obj.facilities.get(key)
            if ans not in ("yes", "no"):
                continue
            now = "yes" if getattr(obj.island, key) else ("no" if obj.island.details_verified else "not confirmed")
            same = (ans == "yes") == bool(getattr(obj.island, key)) and obj.island.details_verified
            rows.append(format_html('<tr><td style="padding:4px 14px 4px 0">{}</td><td style="padding:4px 14px 4px 0"><b>{}</b></td><td style="padding:4px 0;color:{}">guide now: {}</td></tr>',
                                    label, ans.title(), "#1E7A55" if same else "#9A5F05", now))
        from django.utils.safestring import mark_safe
        return mark_safe("<table>" + "".join(str(r) for r in rows) + "</table>") if rows else "No answers"

    # ---- applying
    def _apply_facilities(self, c):
        isl = c.island
        fields = []
        for key, ans in c.facilities.items():
            if key in dict(IslandContribution.FACILITIES) and ans in ("yes", "no"):
                setattr(isl, key, ans == "yes")
                fields.append(key)
        if c.transfer_time and not isl.transfer_time:
            isl.transfer_time = c.transfer_time[:60]
            fields.append("transfer_time")
        if c.getting_there and not isl.getting_there:
            isl.getting_there = c.getting_there
            fields.append("getting_there")
        if c.famous_for and not isl.famous_for:
            isl.famous_for = c.famous_for
            fields.append("famous_for")
        if c.tips and not isl.what_to_expect:
            isl.what_to_expect = c.tips
            fields.append("what_to_expect")
        if c.facilities:
            isl.details_verified = True
            fields.append("details_verified")
        if fields:
            isl.save(update_fields=list(set(fields)))
        return bool(fields)

    def _add_photos(self, c):
        from django.core.files.storage import default_storage  # noqa: F401
        n = 0
        start = (c.island.photos.order_by("-order").values_list("order", flat=True).first() or 0) + 1
        for p in c.photos.filter(added_to_gallery=False):
            try:
                url = p.image.url
            except Exception:
                continue
            IslandPhoto.objects.create(island=c.island, image_url=url, caption=p.caption, order=start + n,
                                       credit=(c.photo_credit or c.name)[:200], license="Shared with Island Stay")
            p.added_to_gallery = True
            p.save(update_fields=["added_to_gallery"])
            n += 1
        if n and not c.island.photo_url:
            first = c.island.photos.order_by("order").first()
            c.island.cover_image_url, c.island.cover_credit = first.image_url, first.credit
            c.island.save(update_fields=["cover_image_url", "cover_credit"])
        return n

    @admin.action(description="Apply facility answers and empty fields to the island")
    def apply_facilities(self, request, queryset):
        n = sum(self._apply_facilities(c) for c in queryset)
        queryset.update(status="applied")
        self.message_user(request, f"Updated {n} island(s). Check the island pages, and edit the text there if needed.", messages.SUCCESS)

    @admin.action(description="Add photos to the island gallery")
    def add_photos(self, request, queryset):
        n = sum(self._add_photos(c) for c in queryset)
        queryset.update(status="applied")
        self.message_user(request, f"Added {n} photo(s) to island galleries.", messages.SUCCESS)

    @admin.action(description="Apply everything (facilities, empty fields and photos)")
    def apply_all(self, request, queryset):
        islands = sum(self._apply_facilities(c) for c in queryset)
        photos = sum(self._add_photos(c) for c in queryset)
        queryset.update(status="applied")
        self.message_user(request, f"Updated {islands} island(s) and added {photos} photo(s).", messages.SUCCESS)

    @admin.action(description="Mark as not used")
    def mark_not_used(self, request, queryset):
        queryset.update(status="rejected")

    @action(description="Apply everything", icon="done_all", url_path="apply-all")
    def apply_all_detail(self, request, object_id):
        c = IslandContribution.objects.get(pk=object_id)
        changed, photos = self._apply_facilities(c), self._add_photos(c)
        c.status = "applied"
        c.save(update_fields=["status"])
        self.message_user(request, f"{c.island.name}: {'facilities updated' if changed else 'nothing to change'}, {photos} photo(s) added.", messages.SUCCESS)
        return redirect(reverse("admin:directory_islandcontribution_change", args=[object_id]))
