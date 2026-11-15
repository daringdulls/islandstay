from datetime import timedelta

from django.contrib import admin
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from unfold.decorators import display

from directory.admin import BaseAdmin

from .models import LinkLead, LinkPlan, TrackedLink


@admin.register(LinkPlan)
class LinkPlanAdmin(BaseAdmin):
    list_display = ("listing", "state", "starts", "ends", "price_display", "links", "visits_30", "leads_30", "dashboard")
    list_filter = ("is_active", "billing")
    search_fields = ("listing__name",)
    autocomplete_fields = ("listing",)
    fieldsets = (
        (None, {"fields": ("listing", "is_active", ("starts", "ends"))}),
        ("Billing", {"fields": (("price", "currency", "billing"), "notes")}),
    )

    def get_queryset(self, request):
        since = timezone.now() - timedelta(days=30)
        return super().get_queryset(request).select_related("listing").annotate(
            n_links=Count("listing__tracked_links", distinct=True),
            n_visits=Count("listing__tracked_links__visits", filter=Q(listing__tracked_links__visits__created_at__gte=since), distinct=True),
            n_leads=Count("listing__tracked_links__leads", filter=Q(listing__tracked_links__leads__created_at__gte=since), distinct=True),
        )

    @display(description="Status", label={"Live": "success", "Expired": "danger", "Paused": "warning", "Starts later": "info"})
    def state(self, obj):
        today = timezone.localdate()
        if not obj.is_active:
            return "Paused"
        if obj.starts > today:
            return "Starts later"
        return "Live" if obj.is_live else "Expired"

    @display(description="Price")
    def price_display(self, obj):
        return f"{obj.currency} {obj.price:g} / {obj.get_billing_display().lower()}" if obj.price is not None else "–"

    @display(description="Links", ordering="n_links")
    def links(self, obj):
        return obj.n_links

    @display(description="Visits (30 d)", ordering="n_visits")
    def visits_30(self, obj):
        return obj.n_visits

    @display(description="Requests (30 d)", ordering="n_leads")
    def leads_30(self, obj):
        return obj.n_leads

    @display(description="")
    def dashboard(self, obj):
        return format_html('<a href="{}" target="_blank" style="color:#0B6E8A;font-weight:600">Open their page</a>', reverse("links:manage", args=[obj.listing_id]))


@admin.register(TrackedLink)
class TrackedLinkAdmin(BaseAdmin):
    list_display = ("short", "label", "listing", "channel", "clicks", "n_leads", "is_active", "created_at")
    list_filter = ("channel", "is_active")
    search_fields = ("code", "label", "listing__name")
    autocomplete_fields = ("listing",)
    readonly_fields = ("clicks", "created_at")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("listing").annotate(leads_n=Count("leads"))

    @display(description="Link", ordering="code")
    def short(self, obj):
        return format_html('<a href="{}" target="_blank" style="color:#0B6E8A;font-weight:600">/r/{}/</a>', obj.get_absolute_url(), obj.code)

    @display(description="Requests", ordering="leads_n")
    def n_leads(self, obj):
        return obj.leads_n


@admin.register(LinkLead)
class LinkLeadAdmin(BaseAdmin):
    list_display = ("enquiry", "link", "created_at")
    search_fields = ("enquiry__reference", "link__code")
    readonly_fields = ("enquiry", "link", "created_at")

    def has_add_permission(self, request):
        return False
