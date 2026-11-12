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

from directory.models import Island

from .models import AdEnquiry, AffiliateOffer, Placement, Sponsor
from .samples import create_samples, remove_samples

PLACEMENT_FIELDS = ("headline", "text", "button", "link", "where", "image_url")
OFFER_FIELDS = ("name", "title", "blurb", "button", "category", "url")


from django.views.decorators.clickjacking import xframe_options_sameorigin  # noqa: E402


@xframe_options_sameorigin
def preview_frame(request):
    """A piece of the public page (real site styles) showing a placement or the 'Before you go' box.

    ?placement=<pk>  or  ?kind=placement&headline=...  (unsaved values from the edit form)
    ?offers=all      or  ?kind=offer&title=...
    """
    g = request.GET
    placement, offers, where = None, [], g.get("where") or "island"
    if g.get("placement"):
        placement = Placement.objects.select_related("sponsor").filter(pk=g["placement"]).first()
    elif g.get("kind") == "placement":
        saved = Placement.objects.filter(pk=g.get("pk") or 0).first()
        placement = Placement(**{f: g.get(f, "") for f in PLACEMENT_FIELDS})
        placement.where = where if where in dict(Placement.WHERE_CHOICES) else "island"
        placement.button = placement.button or "Learn more"
        placement.sponsor = Sponsor.objects.filter(pk=g.get("sponsor") or 0).first() or Sponsor(name="Sponsor name")
        if saved and saved.image and not placement.image_url:
            placement.image = saved.image
    if placement:
        where = placement.where
    if g.get("offers") == "all":
        offers = list(AffiliateOffer.objects.filter(is_active=True).order_by("is_sample", "order")[:4])
    elif g.get("kind") == "offer":
        o = AffiliateOffer(**{f: g.get(f, "") for f in OFFER_FIELDS})
        o.category = o.category if o.category in dict(AffiliateOffer.CATEGORY_CHOICES) else "other"
        o.button = o.button or "See prices"
        offers = [o]
        where = "island"
    island = Island.objects.filter(is_published=True).order_by("-is_featured", "name").first()
    return TemplateResponse(request, "partners/preview_frame.html", {
        "p": placement, "href": "#", "offers": [(o, "#") for o in offers], "where": where, "island": island})


@admin.register(Sponsor)
class SponsorAdmin(BaseAdmin):
    list_display = ("name", "is_sample", "contact_name", "contact_email", "live_count", "total_value")
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
    change_form_template = "admin/partners/change_form.html"
    preview_kind = "placement"
    list_display = ("headline", "sponsor", "where", "dates", "status_label", "views", "clicks", "ctr_col", "report_link")
    actions_list = ["open_preview"]
    list_filter = ("where", "sponsor", "is_active")
    search_fields = ("headline", "sponsor__name")
    autocomplete_fields = ("sponsor", "islands")
    readonly_fields = ("views", "clicks", "created_at")
    fieldsets = (
        ("Placement", {"fields": ("sponsor", ("where", "is_active", "is_sample"), ("starts", "ends"), "islands")}),
        ("Card", {"fields": ("headline", "text", ("image", "image_url"), ("link", "button"))}),
        ("Business", {"fields": (("price", "currency"), ("views", "clicks"), "created_at")}),
    )

    @display(description="Dates")
    def dates(self, obj):
        return f"{obj.starts:%d %b} – {obj.ends:%d %b %Y}"

    @action(description="Preview all", icon="visibility", url_path="go-preview")
    def open_preview(self, request):
        from django.shortcuts import redirect
        return redirect("admin:partners_preview")

    @display(description="Status", label={"Live": "success", "Scheduled": "info", "Ended": "warning", "Paused": "danger", "Sample": "info"})
    def status_label(self, obj):
        today = timezone.localdate()
        if obj.is_sample:
            return "Sample"
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
        view = self.admin_site.admin_view
        return [
            path("<int:pk>/report/", view(self.report_view), name="partners_placement_report"),
            path("preview/", view(self.preview_page), name="partners_preview"),
            path("preview/frame/", view(preview_frame), name="partners_preview_frame"),
        ] + super().get_urls()

    def preview_page(self, request):
        from django.contrib import messages
        from django.shortcuts import redirect

        if request.method == "POST" and self.has_change_permission(request):
            if request.POST.get("samples") == "add":
                n = create_samples(Sponsor, Placement, AffiliateOffer, Island, today=timezone.localdate())
                messages.success(request, f"Added {n} samples." if n else "Samples are already there.")
            elif request.POST.get("samples") == "remove":
                n = remove_samples(Sponsor, Placement, AffiliateOffer)
                messages.success(request, f"Removed {n} samples.")
            return redirect("admin:partners_preview")
        placements = list(Placement.objects.select_related("sponsor").order_by("where", "is_sample", "-starts"))
        groups = []
        for key, label in Placement.WHERE_CHOICES:
            items = [p for p in placements if p.where == key]
            groups.append({"key": key, "label": label, "items": items, "wide": key == "islands"})
        return TemplateResponse(request, "admin/partners/preview.html", {
            **self.admin_site.each_context(request), "opts": self.model._meta, "title": "Preview: sponsors, affiliate links and Advertise page",
            "groups": groups, "today": timezone.localdate(),
            "n_samples": Placement.objects.filter(is_sample=True).count() + AffiliateOffer.objects.filter(is_sample=True).count(),
            "offers": AffiliateOffer.objects.order_by("is_sample", "order")})

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
    change_form_template = "admin/partners/change_form.html"
    preview_kind = "offer"
    list_display = ("title", "name", "category", "where", "is_active", "is_sample", "clicks", "clicks_30", "link_col")
    actions_list = ["open_preview"]

    @action(description="Preview all", icon="visibility", url_path="go-preview")
    def open_preview(self, request):
        from django.shortcuts import redirect
        return redirect("admin:partners_preview")
    list_editable = ("is_active",)
    list_filter = ("category", "is_active", "where")
    search_fields = ("name", "title")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("clicks", "created_at")
    fieldsets = (
        ("Offer", {"fields": (("name", "slug"), ("category", "where"), "title", "blurb", ("url", "button"), ("is_active", "is_sample", "order"))}),
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
