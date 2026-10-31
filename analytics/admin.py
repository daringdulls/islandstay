from django.contrib import admin
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import ChoicesDropdownFilter
from unfold.decorators import action, display

from .models import Visitor
from .report import build
from .utils import country_name


class SourceFilter(admin.SimpleListFilter):
    title = "source"
    parameter_name = "source"

    def lookups(self, request, model_admin):
        return [(s, s) for s in Visitor.objects.values_list("first_source", flat=True).distinct().order_by("first_source")[:30] if s]

    def queryset(self, request, qs):
        return qs.filter(first_source=self.value()) if self.value() else qs


class ConvertedFilter(admin.SimpleListFilter):
    title = "sent a request"
    parameter_name = "converted"

    def lookups(self, request, model_admin):
        return [("yes", "Yes"), ("no", "No")]

    def queryset(self, request, qs):
        if self.value() == "yes":
            return qs.filter(enquiries__gt=0)
        if self.value() == "no":
            return qs.filter(enquiries=0)
        return qs


@admin.register(Visitor)
class VisitorAdmin(ModelAdmin):
    list_display = ("who", "where", "source_col", "visits", "pageviews", "requests", "last")
    list_filter = (SourceFilter, ConvertedFilter, "device", "country", "first_seen")
    list_filter_submit = True
    search_fields = ("id", "city", "country", "first_source", "landing_path")
    date_hierarchy = "last_seen"
    list_per_page = 50
    change_form_after_template = "admin/analytics/journey.html"
    actions_list = ["open_dashboard"]
    readonly_fields = [f.name for f in Visitor._meta.fields]
    fieldsets = (
        ("Visitor", {"fields": (("id", "first_seen", "last_seen"), ("country", "region", "city"),
                                ("device", "browser", "os"), ("language", "screen"),
                                ("first_source", "first_campaign"), "first_referrer", "landing_path",
                                ("visits", "pageviews", "enquiries"))}),
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @display(description="Visitor", header=True)
    def who(self, obj):
        return [f"#{obj.short_id}", f"{obj.device or '?'} · {obj.browser or '?'} · {obj.os or '?'}"]

    @display(description="Location")
    def where(self, obj):
        return ", ".join(x for x in (obj.city, country_name(obj.country) if obj.country else "") if x) or "Unknown"

    @display(description="Found us via", ordering="first_source")
    def source_col(self, obj):
        return obj.first_source + (f" · {obj.first_campaign}" if obj.first_campaign else "")

    @display(description="Requests", ordering="enquiries", label={"0": "info"})
    def requests(self, obj):
        return str(obj.enquiries) if obj.enquiries else "0"

    @display(description="Last seen", ordering="last_seen")
    def last(self, obj):
        return timezone.localtime(obj.last_seen).strftime("%d %b, %H:%M")

    @action(description="Analytics dashboard", icon="insights", url_path="go-dashboard")
    def open_dashboard(self, request):
        return redirect("admin:analytics_dashboard")

    def change_view(self, request, object_id, form_url="", extra_context=None):
        visitor = self.get_object(request, object_id)
        extra_context = extra_context or {}
        if visitor:
            visits = []
            for v in visitor.visit_set.order_by("-started_at")[:30]:
                visits.append({"visit": v, "events": list(v.event_set.order_by("ts", "id")[:400])})
            extra_context.update(journey=visits, visitor_enquiries=visitor.enquiry_set.select_related("listing").order_by("-created_at"),
                                 country_label=country_name(visitor.country))
        return super().change_view(request, object_id, form_url, extra_context)

    def get_urls(self):
        return [path("dashboard/", self.admin_site.admin_view(self.dashboard_view), name="analytics_dashboard")] + super().get_urls()

    def dashboard_view(self, request):
        try:
            days = int(request.GET.get("days", 30))
        except ValueError:
            days = 30
        days = days if days in (1, 7, 30, 90, 365) else 30
        ctx = {**self.admin_site.each_context(request), "title": "Analytics", "opts": self.model._meta, **build(days),
               "ranges": [(1, "Today"), (7, "7 days"), (30, "30 days"), (90, "90 days"), (365, "12 months")],
               "visitors_url": reverse("admin:analytics_visitor_changelist"),
               "requests_url": reverse("admin:directory_enquiry_changelist")}
        return TemplateResponse(request, "admin/analytics/dashboard.html", ctx)
