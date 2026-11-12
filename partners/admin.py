import datetime as dt

from django.contrib import admin
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from unfold.decorators import action, display

from directory.admin import BaseAdmin

from .models import AdEnquiry, AffiliateOffer, Placement, Sponsor


@admin.register(Sponsor)
class SponsorAdmin(BaseAdmin):
    list_display = ("name", "contact_name", "contact_email", "live_count", "total_value")
    search_fields = ("name", "contact_name", "contact_email")

    def get_queryset(self, request):
        today = timezone.localdate()
        return super().get_queryset(request).annotate(
            _live=Count("placements", filter=Q(placements__is_active=True, placements__starts__lte=today, placements__ends__gte=today)))

    @display(description="Live placements", ordering="_live")
    def live_count(self, obj):
        return obj._live

    @display(description="Agreed (all placements)")
    def total_value(self, obj):
        totals = {}
        for p in obj.placements.exclude(price=None):
            totals[p.currency] = totals.get(p.currency, 0) + p.price
        return ", ".join(f"{c} {v:,.0f}" for c, v in totals.items()) or "–"


@admin.register(Placement)
class PlacementAdmin(BaseAdmin):
    list_display = ("headline", "sponsor", "where", "dates", "status_label", "views", "clicks", "ctr_col", "report_link")
    list_filter = ("where", "sponsor", "is_active")
    search_fields = ("headline", "sponsor__name")
    autocomplete_fields = ("sponsor",)
    filter_horizontal = ("islands",)
    readonly_fields = ("views", "clicks", "created_at")
    fieldsets = (
        ("Placement", {"fields": ("sponsor", ("where", "is_active"), ("starts", "ends"), "islands")}),
        ("Card", {"fields": ("headline", "text", "image", ("link", "button"))}),
        ("Business", {"fields": (("price", "currency"), ("views", "clicks"), "created_at")}),
    )

    @display(description="Dates")
    def dates(self, obj):
        return f"{obj.starts:%d %b} – {obj.ends:%d %b %Y}"

    @display(description="Status", label={"Live": "success", "Scheduled": "info", "Ended": "warning", "Paused": "danger"})
    def status_label(self, obj):
        today = timezone.localdate()
        if not obj.is_active:
            return "Paused"
        if obj.starts > today:
            return "Scheduled"
        if obj.ends < today:
            return "Ended"
        return "Live"

    @display(description="Click rate")
    def ctr_col(self, obj):
        return obj.ctr_label

    @display(description="Report")
    def report_link(self, obj):
        return format_html('<a href="{}" style="color:#0B6E8A;font-weight:600">Open report</a>', reverse("admin:partners_placement_report", args=[obj.pk]))

    def get_urls(self):
        return [path("<int:pk>/report/", self.admin_site.admin_view(self.report_view), name="partners_placement_report")] + super().get_urls()

    def report_view(self, request, pk):
        p = get_object_or_404(Placement.objects.select_related("sponsor"), pk=pk)
        days = (p.click_log.annotate(day=TruncDate("created_at")).values("day").annotate(n=Count("id")).order_by("day"))
        pages = p.click_log.exclude(page="").values("page").annotate(n=Count("id")).order_by("-n")[:10]
        islands = p.click_log.exclude(island="").values("island").annotate(n=Count("id")).order_by("-n")[:10]
        return TemplateResponse(request, "admin/partners/report.html", {
            **self.admin_site.each_context(request), "opts": self.model._meta, "title": f"Report: {p}", "p": p,
            "days": list(days), "pages": list(pages), "islands": list(islands), "today": timezone.localdate()})


@admin.register(AffiliateOffer)
class AffiliateOfferAdmin(BaseAdmin):
    list_display = ("title", "name", "category", "where", "is_active", "clicks", "clicks_30", "link_col")
    list_editable = ("is_active",)
    list_filter = ("category", "is_active", "where")
    search_fields = ("name", "title")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("clicks", "created_at")
    fieldsets = (
        ("Offer", {"fields": (("name", "slug"), ("category", "where"), "title", "blurb", ("url", "button"), ("is_active", "order"))}),
        ("Programme", {"fields": (("network", "commission"), ("clicks", "created_at"))}),
    )

    def get_queryset(self, request):
        since = timezone.now() - dt.timedelta(days=30)
        return super().get_queryset(request).annotate(_c30=Count("click_log", filter=Q(click_log__created_at__gte=since)))

    @display(description="Clicks (30 days)", ordering="_c30")
    def clicks_30(self, obj):
        return obj._c30

    @display(description="Tracked link")
    def link_col(self, obj):
        return format_html('<code>{}</code>', obj.get_click_url())


@admin.register(AdEnquiry)
class AdEnquiryAdmin(BaseAdmin):
    list_display = ("company", "name", "email", "phone", "interest", "status", "created_at")
    list_editable = ("status",)
    list_filter = ("status", "interest")
    search_fields = ("company", "name", "email")
    readonly_fields = ("created_at",)
