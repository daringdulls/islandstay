"""Back-office helpers: sidebar badges and the dashboard."""
import json
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.urls import reverse
from django.utils import timezone

from .models import Enquiry, Island, IslandSuggestion, Listing


def _badge(n):
    return str(n) if n else ""


def badge_pending_listings(request):
    return _badge(Listing.objects.filter(status=Listing.STATUS_PENDING).count())


def badge_verification(request):
    return _badge(Listing.objects.filter(verification_requested_at__isnull=False, is_verified=False).count())


def badge_new_enquiries(request):
    return _badge(Enquiry.objects.filter(status=Enquiry.STATUS_NEW).count())


def badge_suggestions(request):
    return _badge(IslandSuggestion.objects.filter(handled=False).count())


def environment_callback(request):
    return ["Development", "warning"] if settings.DEBUG else None


def dashboard_callback(request, context):
    today = timezone.localdate()
    start = today - timedelta(days=13)
    per_day = dict(
        Enquiry.objects.filter(created_at__date__gte=start)
        .annotate(day=TruncDate("created_at")).values("day").annotate(n=Count("id")).values_list("day", "n")
    )
    days = [start + timedelta(days=i) for i in range(14)]
    chart = {
        "labels": [d.strftime("%d %b") for d in days],
        "datasets": [{"label": "Booking requests", "data": [per_day.get(d, 0) for d in days],
                      "backgroundColor": "var(--color-primary-600)"}],
    }

    listing_url = reverse("admin:directory_listing_changelist")
    enquiry_url = reverse("admin:directory_enquiry_changelist")
    island_url = reverse("admin:directory_island_changelist")
    live = Listing.objects.filter(status=Listing.STATUS_APPROVED)
    week_ago = timezone.now() - timedelta(days=7)

    context.update({
        "kpis": [
            {"title": "Listings to review", "value": Listing.objects.filter(status=Listing.STATUS_PENDING).count(),
             "note": "Waiting for approval", "href": listing_url + "?status__exact=pending", "icon": "pending_actions", "alert": True},
            {"title": "New booking requests", "value": Enquiry.objects.filter(status=Enquiry.STATUS_NEW).count(),
             "note": f"{Enquiry.objects.filter(created_at__gte=week_ago).count()} received in the last 7 days",
             "href": enquiry_url + "?status__exact=new", "icon": "mark_email_unread", "alert": True},
            {"title": "Live listings", "value": live.count(),
             "note": f"{live.filter(is_verified=True).count()} verified hosts", "href": listing_url + "?status__exact=approved",
             "icon": "storefront"},
            {"title": "Island guides", "value": Island.objects.filter(is_published=True).count(),
             "note": f"{Island.objects.exclude(cover_image='').count()} with a cover photo", "href": island_url, "icon": "landscape"},
            {"title": "Businesses registered", "value": get_user_model().objects.filter(is_staff=False).count(),
             "note": f"{get_user_model().objects.filter(date_joined__gte=week_ago, is_staff=False).count()} joined this week",
             "href": reverse("admin:auth_user_changelist"), "icon": "group"},
        ],
        "chart_data": json.dumps(chart),
        "requests_total": sum(chart["datasets"][0]["data"]),
        "pending": Listing.objects.filter(status=Listing.STATUS_PENDING).select_related("island", "owner").order_by("created_at")[:6],
        "verification": Listing.objects.filter(verification_requested_at__isnull=False, is_verified=False)
        .select_related("island").order_by("verification_requested_at")[:5],
        "latest_requests": Enquiry.objects.select_related("listing", "listing__island")[:8],
        "suggestions": IslandSuggestion.objects.filter(handled=False)[:5],
        "islands_without_photo": Island.objects.filter(is_published=True, cover_image="").count(),
        "quick_links": [
            {"title": "Add a listing", "icon": "add_business", "href": reverse("admin:directory_listing_add")},
            {"title": "Add an island", "icon": "add_location_alt", "href": reverse("admin:directory_island_add")},
            {"title": "Add a transport route", "icon": "directions_boat", "href": reverse("admin:directory_transportroute_add")},
            {"title": "Islands without a photo", "icon": "hide_image", "href": island_url + "?photo=no"},
        ],
    })
    return context
