import json
import uuid
from datetime import timedelta

from django.db.models import F
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import AnonymousPageview, Event, Visit, Visitor
from .utils import classify_source, geo, is_bot, parse_ua

TYPES = {t for t, _ in Event.TYPES}
VISIT_GAP = timedelta(minutes=30)


def _s(value, n):
    return str(value or "")[:n]


def _uuid(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


@csrf_exempt
@require_POST
def collect(request):
    """Receives batches of events from static/js/track.js (navigator.sendBeacon)."""
    empty = HttpResponse(status=204)
    if is_bot(request) or (request.user.is_authenticated and request.user.is_staff) or len(request.body) > 64_000:
        return empty
    try:
        data = json.loads(request.body or b"{}")
    except ValueError:
        return empty
    events = [e for e in (data.get("events") or [])[:60] if isinstance(e, dict) and e.get("type") in TYPES]
    if not events:
        return empty
    now = timezone.now()

    # Declined analytics cookies: count page views only, no identifiers.
    if request.COOKIES.get("is_consent") != "all":
        for e in events:
            if e["type"] == "pageview":
                row, _ = AnonymousPageview.objects.get_or_create(date=timezone.localdate(), path=_s(e.get("path"), 300))
                AnonymousPageview.objects.filter(pk=row.pk).update(views=F("views") + 1)
        return empty

    vid, sid = _uuid(request.COOKIES.get("is_vid") or data.get("vid")), _uuid(data.get("sid"))
    if not vid or not sid:
        return empty
    ua = request.headers.get("user-agent", "")
    device, browser, os_name = parse_ua(ua)
    country, region, city = geo(request)
    first = events[0]
    own_host = request.get_host().split(":")[0]
    visitor, created = Visitor.objects.get_or_create(pk=vid, defaults=dict(
        first_seen=now, last_seen=now, country=country, region=region, city=city, device=device, browser=browser, os=os_name,
        language=_s(data.get("lang"), 20), screen=_s(data.get("screen"), 15),
        first_source=classify_source(first.get("referrer"), first.get("utm_source", ""), own_host) or "Direct",
        first_referrer=_s(first.get("referrer"), 300), first_campaign=_s(first.get("utm_campaign"), 100),
        landing_path=_s(first.get("path"), 300)))
    visit = Visit.objects.filter(pk=sid, visitor=visitor).first()
    if visit is None:
        visit = Visit.objects.create(
            id=sid, visitor=visitor, started_at=now, last_at=now, entry_path=_s(first.get("path"), 300),
            referrer=_s(first.get("referrer"), 300),
            source=classify_source(first.get("referrer"), first.get("utm_source", ""), own_host) or "Direct",
            medium=_s(first.get("utm_medium"), 60), campaign=_s(first.get("utm_campaign"), 100))
        Visitor.objects.filter(pk=visitor.pk).update(visits=F("visits") + 1)

    rows, pageviews, last_page = [], 0, visit.exit_path
    for e in events:
        offset = e.get("t")
        ts = now - timedelta(milliseconds=min(max(int(offset), 0), 3_600_000)) if isinstance(offset, (int, float)) else now
        rows.append(Event(visit=visit, visitor=visitor, ts=ts, type=e["type"], path=_s(e.get("path"), 300),
                          label=_s(e.get("label"), 200), value=_s(e.get("value"), 300)))
        if e["type"] == "pageview":
            pageviews += 1
            last_page = _s(e.get("path"), 300)
    Event.objects.bulk_create(rows)
    Visit.objects.filter(pk=visit.pk).update(last_at=now, exit_path=last_page, pageviews=F("pageviews") + pageviews,
                                             events=F("events") + len(rows))
    updates = dict(last_seen=now, pageviews=F("pageviews") + pageviews)
    if country and not created:
        updates.update(country=country, region=region, city=city)
    Visitor.objects.filter(pk=visitor.pk).update(**updates)
    return empty


def purge(days=395):
    """Delete analytics older than about 13 months (called by the daily cron)."""
    cutoff = timezone.now() - timedelta(days=days)
    Event.objects.filter(ts__lt=cutoff).delete()
    Visit.objects.filter(last_at__lt=cutoff).delete()
    Visitor.objects.filter(last_seen__lt=cutoff).delete()
    AnonymousPageview.objects.filter(date__lt=cutoff.date()).delete()
    from directory.models import Enquiry

    Enquiry.objects.filter(created_at__lt=timezone.now() - timedelta(days=730)).delete()  # privacy policy: 2 years
    Enquiry.objects.exclude(ip_address=None).update(ip_address=None)
