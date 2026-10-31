"""Numbers for the Analytics page in the back office."""
import json
from collections import Counter
from datetime import timedelta

from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from directory.models import Enquiry, Island, Listing

from .models import AnonymousPageview, Event, Visit, Visitor
from .utils import country_name

PALETTE = ["#0B6E8A", "#4CC3C7", "#0A3D4C", "#EBA62A", "#1E7A55", "#E8664A", "#7D9399", "#5B3A22"]


def _pct(a, b):
    return round(100 * a / b, 1) if b else 0


def _dur(seconds):
    seconds = int(seconds or 0)
    return f"{seconds // 60}m {seconds % 60:02d}s"


def _rows(counter, total=None, n=10, label=lambda k: k or "Unknown"):
    total = total or sum(counter.values()) or 1
    return [{"label": label(k), "n": v, "pct": _pct(v, total)} for k, v in counter.most_common(n)]


def build(days=30):
    now = timezone.now()
    since = now - timedelta(days=days)
    prev = since - timedelta(days=days)
    visits = Visit.objects.filter(started_at__gte=since)
    events = Event.objects.filter(ts__gte=since)
    pageviews = events.filter(type="pageview")
    enquiries = Enquiry.objects.filter(created_at__gte=since).select_related("listing", "listing__island")

    n_visitors = visits.values("visitor").distinct().count()
    n_prev_visitors = Visit.objects.filter(started_at__gte=prev, started_at__lt=since).values("visitor").distinct().count()
    n_visits = visits.count()
    n_pageviews = pageviews.count()
    n_anon = AnonymousPageview.objects.filter(date__gte=since.date()).aggregate(n=Sum("views"))["n"] or 0
    bounces = visits.filter(pageviews__lte=1).count()
    durations = [v.seconds for v in visits.only("started_at", "last_at")[:5000]]
    n_new = Visitor.objects.filter(first_seen__gte=since).count()
    n_req = enquiries.count()
    n_prev_req = Enquiry.objects.filter(created_at__gte=prev, created_at__lt=since).count()
    n_sent = enquiries.exclude(sent_via="").count()
    tracked_req = enquiries.exclude(visitor=None).count()
    live = Visit.objects.filter(last_at__gte=now - timedelta(minutes=5)).count()

    def change(a, b):
        if not b:
            return ""
        d = round(100 * (a - b) / b)
        return f"{'+' if d >= 0 else ''}{d}% vs previous {days} days"

    kpis = [
        {"title": "Visitors", "value": n_visitors, "note": change(n_visitors, n_prev_visitors) or f"{n_new} new", "icon": "group"},
        {"title": "Visits", "value": n_visits, "note": f"{_pct(bounces, n_visits)}% left after one page", "icon": "login"},
        {"title": "Page views", "value": n_pageviews + n_anon, "note": f"{n_anon} anonymous (essential cookies only)", "icon": "visibility"},
        {"title": "Average visit", "value": _dur(sum(durations) / len(durations) if durations else 0),
         "note": f"{round(n_pageviews / n_visits, 1) if n_visits else 0} pages per visit", "icon": "timer"},
        {"title": "Booking requests", "value": n_req, "note": change(n_req, n_prev_req) or "in this period", "icon": "mark_email_unread"},
        {"title": "Conversion", "value": f"{_pct(tracked_req, n_visitors)}%", "note": "of visitors sent a request", "icon": "trending_up"},
        {"title": "Sent to host", "value": f"{_pct(n_sent, n_req)}%", "note": f"{n_sent} of {n_req} requests passed on by the guest", "icon": "send"},
        {"title": "On the site now", "value": live, "note": "active in the last 5 minutes", "icon": "radio_button_checked"},
    ]

    # Daily chart: visitors and requests
    day_list = [(since + timedelta(days=i + 1)).date() for i in range(days)]
    v_by_day = dict(visits.annotate(d=TruncDate("started_at")).values("d").annotate(n=Count("visitor", distinct=True)).values_list("d", "n"))
    r_by_day = dict(enquiries.annotate(d=TruncDate("created_at")).values("d").annotate(n=Count("id")).values_list("d", "n"))
    chart = json.dumps({
        "labels": [d.strftime("%d %b") for d in day_list],
        "datasets": [
            {"label": "Visitors", "data": [v_by_day.get(d, 0) for d in day_list], "borderColor": PALETTE[0], "backgroundColor": PALETTE[0]},
            {"label": "Booking requests", "data": [r_by_day.get(d, 0) for d in day_list], "borderColor": PALETTE[3], "backgroundColor": PALETTE[3]},
        ],
    })

    # Funnel
    viewed_listing = pageviews.filter(path__startswith="/listing/").values("visitor").distinct().count()
    started = events.filter(type="request_start").values("visitor").distinct().count()
    pressed = events.filter(type="request_submit").values("visitor").distinct().count()
    sent_tracked = enquiries.exclude(visitor=None).exclude(sent_via="").count()
    funnel = [(label, n, _pct(n, n_visitors)) for label, n in [
        ("Visited the site", n_visitors), ("Viewed a listing", viewed_listing), ("Started the request form", started),
        ("Pressed Send request", pressed), ("Request saved", tracked_req), ("Sent it to the host", sent_tracked)]]

    # Content
    top_pages = list(pageviews.values("path").annotate(n=Count("id"), u=Count("visitor", distinct=True)).order_by("-n")[:15])
    listing_views = Counter()
    island_views = Counter()
    for path, n in pageviews.filter(Q(path__startswith="/listing/") | Q(path__startswith="/islands/")).values_list("path").annotate(n=Count("id")):
        parts = path.strip("/").split("/")
        if len(parts) == 2 and parts[0] == "listing":
            listing_views[parts[1]] += n
        elif len(parts) == 2 and parts[0] == "islands":
            island_views[parts[1]] += n
    req_by_listing = Counter(enquiries.values_list("listing__slug", flat=True))
    listings = {l.slug: l for l in Listing.objects.filter(slug__in=list(listing_views) + list(req_by_listing)).select_related("island")}
    top_listings = []
    for slug in sorted(set(listing_views) | set(req_by_listing), key=lambda s: (-listing_views[s], -req_by_listing[s]))[:12]:
        l = listings.get(slug)
        top_listings.append({"name": l.name if l else slug, "island": l.island.name if l else "", "views": listing_views[slug],
                             "requests": req_by_listing[slug],
                             "rate": f"{_pct(req_by_listing[slug], listing_views[slug])}%" if 0 < req_by_listing[slug] <= listing_views[slug] or (listing_views[slug] and not req_by_listing[slug]) else "–",
                             "url": l.get_absolute_url() if l else ""})
    island_names = dict(Island.objects.filter(slug__in=island_views).values_list("slug", "name"))
    top_islands = [{"label": island_names.get(s, s), "n": n} for s, n in island_views.most_common(12)]
    searches = _rows(Counter(v.strip().lower() for v in events.filter(type="search").values_list("value", flat=True) if v.strip()), n=15)
    clicks = list(events.filter(type__in=["click", "outbound"]).exclude(label="").values("label").annotate(n=Count("id")).order_by("-n")[:15])
    exits = Counter(visits.exclude(exit_path="").values_list("exit_path", flat=True))

    # Audience
    visitor_qs = Visitor.objects.filter(visit_set__started_at__gte=since).distinct()
    audience = {
        "sources": _rows(Counter(visits.values_list("source", flat=True)), n=12),
        "countries": _rows(Counter(visitor_qs.values_list("country", flat=True)), n=12, label=country_name),
        "devices": _rows(Counter(visitor_qs.values_list("device", flat=True))),
        "browsers": _rows(Counter(visitor_qs.values_list("browser", flat=True)), n=8),
        "campaigns": _rows(Counter(c for c in visits.values_list("campaign", flat=True) if c), n=8),
        "languages": _rows(Counter(l.split("-")[0] for l in visitor_qs.values_list("language", flat=True) if l), n=8),
    }

    # Booking requests
    req = list(enquiries)
    n = len(req) or 1
    nights = [e.nights for e in req if e.nights]
    leads = [e.lead_days for e in req if e.lead_days is not None and e.lead_days >= 0]
    status = Counter(e.get_status_display() for e in req)
    answered = sum(1 for e in req if e.status != Enquiry.STATUS_NEW)
    confirmed = sum(1 for e in req if e.status == "confirmed")
    booking = {
        "kpis": [
            {"title": "Requests", "value": len(req), "note": f"{sum(1 for e in req if e.listing.is_stay)} for stays"},
            {"title": "Host replied", "value": f"{_pct(answered, len(req))}%", "note": f"{answered} marked replied, confirmed, declined or closed"},
            {"title": "Confirmed", "value": f"{_pct(confirmed, len(req))}%", "note": f"{confirmed} confirmed by the host"},
            {"title": "Average group", "value": round(sum(e.guests for e in req) / n, 1), "note": f"{sum(1 for e in req if e.children)} requests with children"},
            {"title": "Average stay", "value": f"{round(sum(nights) / len(nights), 1) if nights else 0} nights", "note": f"from {len(nights)} requests with both dates"},
            {"title": "Booking ahead", "value": f"{round(sum(leads) / len(leads)) if leads else 0} days", "note": "between request and arrival"},
            {"title": "Want a transfer", "value": f"{_pct(sum(1 for e in req if e.needs_transfer), len(req))}%", "note": "asked the host for help"},
            {"title": "Guests reached", "value": sum(e.guests for e in req), "note": "adults and children in all requests"},
        ],
        "status": _rows(status, total=len(req)),
        "by_island": _rows(Counter(e.listing.island.name for e in req), total=len(req)),
        "by_kind": _rows(Counter(e.listing.get_kind_display() for e in req), total=len(req)),
        "by_country": _rows(Counter(e.country or (e.guest_country or "")[:20] for e in req), total=len(req), label=country_name),
        "contact": _rows(Counter(e.get_preferred_contact_display() for e in req), total=len(req)),
        "sent_via": _rows(Counter(e.get_sent_via_display() or "Not sent yet" for e in req), total=len(req)),
        "sources": _rows(Counter(e.source or "Unknown (no analytics consent)" for e in req), total=len(req)),
        "devices": _rows(Counter(e.device or "Unknown" for e in req), total=len(req)),
        "months": _rows(Counter(e.check_in.strftime("%b %Y") for e in req if e.check_in), total=len(req), n=12),
    }

    recent = Visit.objects.select_related("visitor").order_by("-last_at")[:15]
    return {
        "days": days, "kpis": kpis, "chart": chart, "funnel": funnel, "top_pages": top_pages, "top_listings": top_listings,
        "top_islands": top_islands, "searches": searches, "clicks": clicks,
        "exits": [{"label": k, "n": v} for k, v in exits.most_common(10)], "audience": audience, "booking": booking,
        "recent": recent, "has_data": n_visits > 0 or n_req > 0,
    }
