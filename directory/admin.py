from django.contrib import admin, messages
from django.db.models import Count
from django.utils import timezone
from django.utils.html import format_html

from . import notifications
from .models import ActivityType, Amenity, Atoll, Enquiry, Island, IslandSuggestion, Listing, ListingPhoto, RoomType, TransportRoute


@admin.register(Atoll)
class AtollAdmin(admin.ModelAdmin):
    list_display = ("name", "official_name", "code", "region", "order", "island_count")
    list_editable = ("order",)
    list_filter = ("region",)
    search_fields = ("name", "official_name")
    prepopulated_fields = {"slug": ("name",)}

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_n=Count("islands"))

    @admin.display(description="Islands", ordering="_n")
    def island_count(self, obj):
        return obj._n


@admin.register(ActivityType)
class ActivityTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "icon", "description")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ("name", "icon")
    search_fields = ("name",)


class IslandRouteInline(admin.TabularInline):
    model = TransportRoute
    fk_name = "island"
    extra = 0
    fields = ("mode", "origin", "via", "operator", "operator_name", "duration", "schedule", "price_from", "currency", "price_note", "is_active", "order")
    autocomplete_fields = ("operator",)


@admin.register(Island)
class IslandAdmin(admin.ModelAdmin):
    inlines = [IslandRouteInline]
    actions = ["fetch_photos"]

    @admin.action(description="Fetch cover photo from Wikimedia Commons")
    def fetch_photos(self, request, queryset):
        import io

        from django.core.management import call_command

        out = io.StringIO()
        for island in queryset:
            call_command("fetch_island_photos", island=island.slug, force=True, stdout=out, stderr=out)
        self.message_user(request, out.getvalue().strip()[-900:] or "Done.")
    list_display = ("name", "atoll", "island_type", "population", "listing_count", "has_photo", "is_featured", "is_published")
    list_editable = ("is_featured", "is_published")
    list_filter = ("atoll", "island_type", "is_published", "is_featured", "has_bikini_beach", "activities")
    search_fields = ("name", "atoll__name", "tagline")
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("activities",)
    fieldsets = (
        (None, {"fields": ("atoll", "name", "slug", "island_type", "tagline", "is_published", "is_featured")}),
        ("About the island", {"fields": ("overview", "famous_for", "what_to_expect", "best_time_to_visit", "activities")}),
        ("Getting there", {"fields": ("getting_there", "transfer_types", "distance_from_airport_km", "transfer_time", "nearest_airport", "nearest_airport_km")}),
        ("Facts & sources", {"fields": ("population", "population_year", "area_km2", "sources", "wikipedia_title")}),
        ("Facilities", {"fields": ("has_bikini_beach", "has_atm", "has_hospital", "has_pharmacy", "has_police", "has_supermarket", "has_4g", "facilities_notes")}),
        ("Regulations & accessibility", {"fields": ("local_rules", "accessibility")}),
        ("Map", {"classes": ("collapse",), "fields": ("latitude", "longitude")}),
        ("Cover photo", {"fields": ("cover_image", "cover_credit", "cover_license", "cover_source_url", "cover_color")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("atoll").annotate(_n=Count("listings"))

    @admin.display(description="Listings", ordering="_n")
    def listing_count(self, obj):
        return obj._n

    @admin.display(description="Photo", boolean=True)
    def has_photo(self, obj):
        return bool(obj.cover_image)


class PhotoInline(admin.TabularInline):
    model = ListingPhoto
    extra = 0


class OperatorRouteInline(admin.TabularInline):
    model = TransportRoute
    fk_name = "operator"
    extra = 0
    fields = ("island", "mode", "origin", "duration", "schedule", "price_from", "currency", "is_active")
    autocomplete_fields = ("island",)


class VerificationFilter(admin.SimpleListFilter):
    title = "verification"
    parameter_name = "verification"

    def lookups(self, request, model_admin):
        return [("requested", "Requested — awaiting review"), ("verified", "Verified"), ("none", "Not requested")]

    def queryset(self, request, qs):
        if self.value() == "requested":
            return qs.filter(verification_requested_at__isnull=False, is_verified=False)
        if self.value() == "verified":
            return qs.filter(is_verified=True)
        if self.value() == "none":
            return qs.filter(verification_requested_at__isnull=True, is_verified=False)
        return qs


class RoomInline(admin.TabularInline):
    model = RoomType
    extra = 0


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "island", "owner", "status_badge", "is_verified", "is_featured", "enquiry_count", "created_at")
    list_filter = ("status", VerificationFilter, "kind", "is_featured", "island__atoll", "island")
    list_editable = ("is_verified", "is_featured")
    search_fields = ("name", "island__name", "owner__email", "contact_email", "registration_number")
    autocomplete_fields = ("island", "owner")
    filter_horizontal = ("amenities", "activity_types")
    inlines = [RoomInline, PhotoInline, OperatorRouteInline]
    actions = ["approve", "reject", "suspend", "verify"]
    readonly_fields = ("created_at", "updated_at", "verified_at", "verification_requested_at")
    fieldsets = (
        ("Moderation", {"fields": ("status", "admin_note", "is_featured")}),
        ("Verified host", {"fields": ("is_verified", "registration_number", "verification_document", "verification_requested_at", "verified_at")}),
        (None, {"fields": ("owner", "island", "kind", "name", "slug", "short_description", "description", "cover_image")}),
        ("Stay details", {"classes": ("collapse",), "fields": (
            "room_count", "max_guests", "star_rating", "distance_to_beach_m", "check_in_time", "check_out_time", "house_rules")}),
        ("Food", {"classes": ("collapse",), "fields": ("cuisine", "opening_hours", "serves_breakfast", "delivery")}),
        ("Offer", {"fields": ("amenities", "activity_types", "price_from", "currency", "price_unit")}),
        ("Contact", {"fields": ("contact_name", "contact_email", "contact_phone", "whatsapp", "viber", "website", "facebook", "instagram", "address")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("island", "owner").annotate(_n=Count("enquiries"))

    @admin.display(description="Requests", ordering="_n")
    def enquiry_count(self, obj):
        return obj._n

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        colors = {"pending": "#d97706", "approved": "#059669", "rejected": "#dc2626", "suspended": "#6b7280"}
        return format_html('<b style="color:{}">{}</b>', colors.get(obj.status, "#000"), obj.get_status_display())

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
        self.message_user(request, f"{n} listing(s) updated and owners notified.", messages.SUCCESS)

    @admin.action(description="Approve selected listings (go live)")
    def approve(self, request, queryset):
        self._set_status(request, queryset, Listing.STATUS_APPROVED)

    @admin.action(description="Reject selected listings")
    def reject(self, request, queryset):
        self._set_status(request, queryset, Listing.STATUS_REJECTED)

    @admin.action(description="Mark selected as Verified host")
    def verify(self, request, queryset):
        n = queryset.filter(is_verified=False).update(is_verified=True, verified_at=timezone.now())
        self.message_user(request, f"{n} listing(s) marked as verified.", messages.SUCCESS)

    @admin.action(description="Suspend selected listings")
    def suspend(self, request, queryset):
        self._set_status(request, queryset, Listing.STATUS_SUSPENDED)


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = ("reference", "guest_name", "listing", "check_in", "check_out", "adults", "children", "status", "created_at")
    list_filter = ("status", "listing__kind", "listing__island__atoll", "created_at")
    search_fields = ("reference", "guest_name", "guest_email", "listing__name")
    readonly_fields = ("reference", "created_at", "updated_at", "ip_address")
    date_hierarchy = "created_at"


@admin.register(IslandSuggestion)
class IslandSuggestionAdmin(admin.ModelAdmin):
    list_display = ("island_name", "atoll", "submitted_by", "contact_email", "handled", "created_at")
    list_editable = ("handled",)
    list_filter = ("handled",)


@admin.register(TransportRoute)
class TransportRouteAdmin(admin.ModelAdmin):
    list_display = ("island", "mode", "origin", "provider", "duration", "schedule", "price_from", "is_active")
    list_filter = ("mode", "is_active", "island__atoll")
    list_editable = ("is_active",)
    search_fields = ("island__name", "origin", "operator__name", "operator_name")
    autocomplete_fields = ("island", "operator")
