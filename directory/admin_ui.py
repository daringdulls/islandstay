"""Back-office helpers: sidebar badges and the dashboard."""
import json
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
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


def badge_claims(request):
    from .models import ListingClaim

    return _badge(ListingClaim.objects.filter(status="pending").count())


def badge_reviews(request):
    from .models import Review

    return _badge(Review.objects.filter(status="pending").count())


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

    has_photo = ~(Q(cover_image="") & Q(cover_image_url=""))
    listing_url = reverse("admin:directory_listing_changelist")
    enquiry_url = reverse("admin:directory_enquiry_changelist")
    island_url = reverse("admin:directory_island_changelist")
    live = Listing.objects.filter(status=Listing.STATUS_APPROVED)
    week_ago = timezone.now() - timedelta(days=7)

    from collections import Counter

    from analytics.models import Event, Visit
    from .models import ListingClaim, Review

    week_visits = Visit.objects.filter(started_at__gte=week_ago)
    n_visitors = week_visits.values("visitor").distinct().count()
    island_views = Counter()
    for path in Event.objects.filter(type="pageview", ts__gte=week_ago, path__startswith="/islands/").values_list("path", flat=True)[:5000]:
        parts = path.strip("/").split("/")
        if len(parts) == 2:
            island_views[parts[1]] += 1
    names = dict(Island.objects.filter(slug__in=island_views).values_list("slug", "name"))
    sources = Counter(week_visits.values_list("source", flat=True))
    todo = [
        ("Listings to review", Listing.objects.filter(status=Listing.STATUS_PENDING).count(), listing_url + "?status__exact=pending", "pending_actions"),
        ("New booking requests", Enquiry.objects.filter(status=Enquiry.STATUS_NEW).count(), enquiry_url + "?status__exact=new", "mark_email_unread"),
        ("Listing claims", ListingClaim.objects.filter(status="pending").count(), reverse("admin:directory_listingclaim_changelist") + "?status__exact=pending", "how_to_reg"),
        ("Reviews to check", Review.objects.filter(status="pending").count(), reverse("admin:directory_review_changelist") + "?status__exact=pending", "reviews"),
        ("Verification requests", Listing.objects.filter(verification_requested_at__isnull=False, is_verified=False).count(), listing_url + "?verification=requested", "verified_user"),
        ("Island suggestions", IslandSuggestion.objects.filter(handled=False).count(), reverse("admin:directory_islandsuggestion_changelist") + "?handled__exact=0", "add_location_alt"),
    ]
    waiting = sum(t[1] for t in todo)
    no_photo_listings = live.filter(cover_image="").exclude(photos__isnull=False).count()
    health = [
        ("Islands without a cover photo", Island.objects.filter(is_published=True).exclude(has_photo).count(), island_url + "?photo=no", "hide_image"),
        ("Live listings without their own photo", no_photo_listings, listing_url + "?status__exact=approved", "add_photo_alternate"),
        ("Live listings without a logo", live.filter(logo="").count(), listing_url + "?status__exact=approved", "branding_watermark"),
        ("Unclaimed listings", live.filter(is_claimed=False).count(), listing_url + "?is_claimed__exact=0", "storefront"),
    ]
    context.update({
        "waiting": waiting, "todo": todo, "health": health,
        "week": {"visitors": n_visitors, "visits": week_visits.count(),
                 "requests": Enquiry.objects.filter(created_at__gte=week_ago).count(),
                 "islands": [(names.get(k, k), n) for k, n in island_views.most_common(5)],
                 "sources": [(k or "Direct", n) for k, n in sources.most_common(4)]},
        "analytics_url": reverse("admin:analytics_dashboard"),
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
             "note": f"{Island.objects.filter(has_photo).count()} with a cover photo", "href": island_url, "icon": "landscape"},
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
        "islands_without_photo": Island.objects.filter(is_published=True).exclude(has_photo).count(),
        "quick_links": [
            {"title": "Add a listing", "icon": "add_business", "href": reverse("admin:directory_listing_add")},
            {"title": "Add an island", "icon": "add_location_alt", "href": reverse("admin:directory_island_add")},
            {"title": "Add a transport route", "icon": "directions_boat", "href": reverse("admin:directory_transportroute_add")},
            {"title": "Islands without a photo", "icon": "hide_image", "href": island_url + "?photo=no"},
        ],
    })
    return context



def ai_assist_view(request):
    """POST name (+ context) -> drafted fields as JSON for the editor to review. Staff only (via admin_view)."""
    import json as _json

    from django.http import JsonResponse

    from .ai_assist import AssistError, research

    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    kind = request.POST.get("kind")
    name = request.POST.get("name", "").strip()[:120]
    context = request.POST.get("context", "").strip()[:200]
    if kind not in ("island", "listing") or len(name) < 2:
        return JsonResponse({"error": "Type a name first."}, status=400)
    if request.POST.get("mode") == "quick":
        from . import web_lookup

        url = request.POST.get("url", "").strip()[:300]
        result = web_lookup.lookup_island(name, context) if kind == "island" else web_lookup.lookup_listing(name, context, url)
        if not result["fields"]:
            return JsonResponse({"error": "Nothing found. " + result["notes"]}, status=404)
        return JsonResponse(result)
    try:
        result = research(kind, name, context + (f"; website {request.POST.get('url')}" if request.POST.get("url") else ""))
    except AssistError as exc:
        return JsonResponse({"error": str(exc)}, status=502)
    return JsonResponse(result)
