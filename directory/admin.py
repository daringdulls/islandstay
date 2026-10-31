import io

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
from .models import ActivityType, Amenity, Atoll, Enquiry, Island, IslandSuggestion, IslandPhoto, Listing, ListingPhoto, RoomType, TransportRoute

LISTING_STATUS_COLORS = {"pending": "warning", "approved": "success", "rejected": "danger", "suspended": "info"}
ENQUIRY_STATUS_COLORS = {"new": "warning", "replied": "info", "confirmed": "success", "declined": "danger", "closed": "info"}


class BaseAdmin(ModelAdmin):
    """Shared back-office behaviour: compact forms, filters applied with a button, unsaved-changes warning."""

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
class IslandAdmin(BaseAdmin):
    change_form_before_template = "admin/ai_assist_island.html"
    inlines = [IslandPhotoInline, IslandRouteInline]
    list_display = ("island", "atoll", "island_type", "population", "listing_count", "has_photo", "is_featured", "is_published")
    list_display_links = ("island",)
    list_editable = ("is_featured", "is_published")
    list_filter = (
        ("atoll", RelatedDropdownFilter), ("island_type", ChoicesDropdownFilter), PhotoFilter,
        "is_published", "is_featured", "has_bikini_beach",
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
            ("has_bikini_beach", "has_atm", "has_hospital", "has_pharmacy"), ("has_police", "has_supermarket", "has_4g"),
            "facilities_notes", "local_rules", "accessibility")}),
        ("Facts & sources", {"classes": ["tab"], "fields": (
            ("population", "population_year", "area_km2"), "sources", "wikipedia_title", ("latitude", "longitude"))}),
        ("Cover photo", {"classes": ["tab"], "fields": (
            "cover_preview", "cover_image", "cover_image_url", ("cover_credit", "cover_license"), "cover_source_url")}),
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


@admin.register(Listing)
class ListingAdmin(BaseAdmin):
    change_form_before_template = "admin/ai_assist_listing.html"
    list_display = ("business", "kind_label", "island_name", "status_label", "verified_label", "is_featured", "enquiry_count", "submitted")
    list_display_links = ("business",)
    list_filter = (
        ("status", ChoicesDropdownFilter), VerificationFilter, ("kind", ChoicesDropdownFilter),
        ("island__atoll", RelatedDropdownFilter), ("island", RelatedDropdownFilter), "is_featured",
    )
    search_fields = ("name", "island__name", "owner__email", "contact_email", "registration_number")
    autocomplete_fields = ("island", "owner")
    checkbox_m2m = ("amenities", "activity_types")
    inlines = [RoomInline, PhotoInline, OperatorRouteInline]
    actions = ["approve", "reject", "suspend", "verify"]
    actions_row = ["approve_row"]
    actions_detail = ["approve_detail", "reject_detail", "verify_detail"]
    readonly_fields = ("created_at", "updated_at", "verified_at", "verification_requested_at")
    fieldsets = (
        ("Business", {"classes": ["tab"], "fields": (
            ("name", "slug"), ("kind", "island"), "owner", "short_description", "description", "cover_image")}),
        ("Review & verification", {"classes": ["tab"], "fields": (
            ("status", "is_featured"), "admin_note", ("is_verified", "registration_number"), "verification_document",
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
        return "no", "No"

    @display(description="Requests", ordering="_n")
    def enquiry_count(self, obj):
        return obj._n

    def save_model(self, request, obj, form, change):
        if obj.is_verified and not obj.verified_at:
            obj.verified_at = timezone.now()
        elif not obj.is_verified:
            obj.verified_at = None
        status_changed = change and "status" in form.changed_data
        super().save_model(request, obj, form, change)
        if status_changed:
            notifications.listing_status_changed(obj)

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
        return obj.created_at.strftime("%d %b %Y")

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
