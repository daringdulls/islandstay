import re
from datetime import timedelta

import segno
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Q
from django.db.models.functions import TruncDate
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from directory.models import Enquiry, Listing
from partners.views import is_bot

from . import tracking
from .forms import TrackedLinkForm
from .models import LinkLead, LinkPlan, LinkVisit, TrackedLink, plan_is_live

MAX_LINKS = 12
ICONS = {"instagram": "instagram", "facebook": "facebook", "tiktok": "share-2", "whatsapp": "message-circle", "booking": "hotel",
         "google": "map-pin", "website": "globe", "email": "mail", "print": "ticket", "partner": "heart-handshake", "other": "share-2"}
MOBILE = re.compile(r"Mobi|Android|iPhone|iPad", re.I)


@never_cache
def follow(request, code):
    """islandstaymv.com/r/<code>/: count the visit, remember it for 30 days, open the listing."""
    link = TrackedLink.objects.select_related("listing").filter(code=code.lower()).first()
    if not link:
        raise Http404
    listing = link.listing
    target = listing.get_absolute_url() + ("#request" if link.to_form else "")
    if link.is_active and listing.is_live and plan_is_live(listing) and not is_bot(request):
        ref = request.headers.get("Referer", "")
        host = re.sub(r"^https?://(www\.)?", "", ref).split("/")[0][:80] if ref else ""
        LinkVisit.objects.create(link=link, device="mobile" if MOBILE.search(request.headers.get("User-Agent", "")) else "desktop",
                                 referrer=host)
        TrackedLink.objects.filter(pk=link.pk).update(clicks=F("clicks") + 1)
        tracking.remember(request, link)
    resp = HttpResponseRedirect(target)
    resp["X-Robots-Tag"] = "noindex, nofollow"
    return resp


def _own(request, pk):
    qs = Listing.objects.all() if request.user.is_staff else request.user.listings.all()
    return get_object_or_404(qs.select_related("island"), pk=pk)


def _full(request, link):
    """Always the public address (www.islandstaymv.com), even when the dashboard is opened on another host."""
    from django.conf import settings

    from accounts.invites import site_url

    return request.build_absolute_uri(link.get_absolute_url()) if settings.DEBUG else site_url() + link.get_absolute_url()


@login_required
def manage(request, pk):
    listing = _own(request, pk)
    plan = LinkPlan.objects.filter(listing=listing).first()
    live = bool(plan and plan.is_live)

    if not live:
        if request.method == "POST" and request.POST.get("action") == "request":
            from partners.models import AdEnquiry

            AdEnquiry.objects.create(
                name=request.user.get_full_name() or request.user.email, company=listing.name, email=request.user.email,
                phone=listing.whatsapp or listing.contact_phone, interest="links",
                message=f"Would like Tracked links for '{listing.name}' (listing #{listing.pk}).")
            messages.success(request, "Thanks! We'll contact you shortly to switch on Tracked links.")
            return redirect("links:manage", pk=listing.pk)
        from django.conf import settings
        from partners.models import AdEnquiry

        requested = AdEnquiry.objects.filter(interest="links", message__contains=f"(listing #{listing.pk})",
                                             status__in=["new", "talking"]).exists()
        return render(request, "links/upsell.html", {"listing": listing, "plan": plan, "requested": requested,
                                                     "price": getattr(settings, "TRACKED_LINKS_PRICE", "")})

    links = listing.tracked_links.all()
    form = TrackedLinkForm(request.POST or None, listing=listing)
    if request.method == "POST":
        action = request.POST.get("action")
        if action in ("pause", "resume"):
            listing.tracked_links.filter(pk=request.POST.get("id")).update(is_active=action == "resume")
            return redirect("links:manage", pk=listing.pk)
        if links.count() >= MAX_LINKS:
            messages.error(request, f"You can have up to {MAX_LINKS} links. Pause one you no longer use, or ask us for more.")
        elif form.is_valid():
            link = form.save(commit=False)
            link.listing = listing
            form.save()
            messages.success(request, f"Your new link is ready: {_full(request, link)}")
            return redirect(f"{request.path}#link-{link.pk}")

    days = 30 if request.GET.get("days") not in ("7", "90") else int(request.GET["days"])
    since = timezone.now() - timedelta(days=days)
    visits = LinkVisit.objects.filter(link__listing=listing, created_at__gte=since)
    leads = LinkLead.objects.filter(link__listing=listing, created_at__gte=since)
    per_day = dict(visits.annotate(d=TruncDate("created_at")).values("d").annotate(n=Count("id")).values_list("d", "n"))
    lead_days = dict(leads.annotate(d=TruncDate("created_at")).values("d").annotate(n=Count("id")).values_list("d", "n"))
    today = timezone.localdate()
    days_list = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]
    top = max(per_day.values(), default=0) or 1
    bars = [{"d": d, "n": per_day.get(d, 0), "r": lead_days.get(d, 0), "h": round(per_day.get(d, 0) / top * 100)} for d in days_list]

    stats = {s["link"]: s for s in visits.values("link").annotate(n=Count("id"))}
    lead_stats = {s["link"]: s["n"] for s in leads.values("link").annotate(n=Count("id"))}
    rows = []
    for l in links:
        n = stats.get(l.pk, {}).get("n", 0)
        r = lead_stats.get(l.pk, 0)
        rows.append({"link": l, "url": _full(request, l), "visits": n, "leads": r, "rate": round(r / n * 100) if n else 0,
                     "icon": ICONS.get(l.channel, "share-2")})
    channels = {}
    for row in rows:
        c = row["link"].get_channel_display()
        channels.setdefault(c, [0, 0])
        channels[c][0] += row["visits"]
        channels[c][1] += row["leads"]
    channels = sorted(channels.items(), key=lambda kv: -kv[1][0])
    ch_top = max((v[0] for _, v in channels), default=0) or 1
    channels = [(name, v[0], v[1], round(v[0] / ch_top * 100)) for name, v in channels]

    total_v, total_l = visits.count(), leads.count()
    devices = dict(visits.values("device").annotate(n=Count("id")).values_list("device", "n"))
    referrers = list(visits.exclude(referrer="").values("referrer").annotate(n=Count("id")).order_by("-n").values_list("referrer", "n")[:6])
    recent = leads.select_related("enquiry", "link")[:8]
    return render(request, "links/manage.html", {
        "listing": listing, "plan": plan, "rows": rows, "form": form, "days": days, "bars": bars,
        "channels": channels, "total_v": total_v, "total_l": total_l, "rate": round(total_l / total_v * 100) if total_v else 0,
        "mobile": round(devices.get("mobile", 0) / total_v * 100) if total_v else 0, "referrers": referrers, "recent": recent,
        "max_links": MAX_LINKS,
    })


@login_required
def qr(request, pk, fmt):
    if fmt not in ("svg", "png"):
        raise Http404
    link = get_object_or_404(TrackedLink.objects.select_related("listing"), pk=pk)
    _own(request, link.listing_id)
    code = segno.make(_full(request, link), error="m")
    from io import BytesIO
    buf = BytesIO()
    if fmt == "svg":
        code.save(buf, kind="svg", scale=10, border=2, dark="#0A3D4C", xmldecl=False)
        resp = HttpResponse(buf.getvalue(), content_type="image/svg+xml")
    else:
        code.save(buf, kind="png", scale=20, border=2, dark="#0A3D4C")
        resp = HttpResponse(buf.getvalue(), content_type="image/png")
    if request.GET.get("download"):
        resp["Content-Disposition"] = f'attachment; filename="islandstay-{link.code}.{fmt}"'
    return resp
