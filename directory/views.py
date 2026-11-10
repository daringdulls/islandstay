from urllib.parse import urlencode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, F, Min, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import notifications
from django.utils import timezone

from .forms import (
    EnquiryForm, EnquiryUpdateForm, IslandSuggestionForm, ListingForm, PhotoUploadForm, RoomFormSet, RouteFormSet,
    VerificationForm,
)
from .models import ActivityType, Amenity, Atoll, Enquiry, Island, IslandPhoto, Listing, ListingPhoto, PageBanner, TransportRoute, Guide

APPROVED = Listing.STATUS_APPROVED


def _islands():
    return (
        Island.objects.filter(is_published=True)
        .select_related("atoll")
        .annotate(
            stay_count=Count("listings", filter=Q(listings__status=APPROVED, listings__kind__in=Listing.STAY_KINDS), distinct=True),
            service_count=Count("listings", filter=Q(listings__status=APPROVED, listings__kind__in=Listing.EXPERIENCE_KINDS), distinct=True),
            food_count=Count("listings", filter=Q(listings__status=APPROVED, listings__kind__in=Listing.FOOD_KINDS), distinct=True),
            route_count=Count("routes", filter=Q(routes__is_active=True), distinct=True),
            min_price=Min("listings__price_from", filter=Q(listings__status=APPROVED, listings__kind__in=Listing.STAY_KINDS)),
        )
    )


def _live_listings():
    return Listing.objects.filter(status=APPROVED, island__is_published=True).select_related("island", "island__atoll")


# ---------------------------------------------------------------- public pages

def home(request):
    atoll_counts = Atoll.objects.annotate(n=Count("islands", filter=Q(islands__is_published=True))).order_by("order", "name")
    featured = sorted(_islands().filter(is_featured=True).prefetch_related("activities"),
                      key=lambda i: (not i.photo_url, i.name))
    from .models import HomeFeature

    def chosen(section):
        """Islands picked in the back office (Home page), annotated like the rest, or None."""
        picked = HomeFeature.islands_for(section)
        if not picked:
            return None
        by_pk = {i.pk: i for i in _islands().filter(pk__in=[i.pk for i in picked]).prefetch_related("activities")}
        return [by_pk[i.pk] for i in picked if i.pk in by_pk]

    slides = chosen(HomeFeature.SECTION_HERO)
    slides = [i for i in slides if i.photo_url] if slides else None
    if not slides:
        slides = [i for i in featured if i.photo_url][:5]
        if len(slides) < 3:
            extra = [i for i in _islands().exclude(pk__in=[x.pk for x in slides]).prefetch_related("activities") if i.photo_url]
            slides += extra[: 5 - len(slides)]
    portraits = chosen(HomeFeature.SECTION_PORTRAIT) or featured[:3]
    popular = chosen(HomeFeature.SECTION_POPULAR) or featured[:5]
    from .models import Review
    banner, banner_credit = PageBanner.for_page("home", "")
    hero_photos = [{"url": banner, "credit": banner_credit, "island": None}] if banner else []
    hero_photos += [{"url": i.photo_url, "credit": i.cover_credit, "island": i} for i in (slides or []) if i.photo_url][: 4 - len(hero_photos)]
    pop4 = list(popular)[:4]
    if len(pop4) < 4:
        pop4 += [i for i in _islands().filter(details_verified=True).order_by("-stay_count", "name") if i not in pop4 and i.photo_url][: 4 - len(pop4)]
    ideas = [a for a in ActivityType.objects.annotate(n=Count("islands", filter=Q(islands__is_published=True))).filter(n__gt=0).order_by("-n") if a.image_url][:6]
    return render(request, "directory/home.html", {
        "hero_photos": hero_photos,
        "popular4": pop4,
        "ideas": ideas,
        "guides": Guide.objects.filter(is_published=True, published_at__lte=timezone.now()).prefetch_related("islands")[:3],
        "reviews": Review.objects.filter(status="published").select_related("listing", "listing__island").order_by("-created_at")[:3],
        "needs": _plan_by_need(featured),
        "slides": slides or featured[:1],
        "popular": popular,
        "figures": _figures(),
        "atoll_index": atoll_counts,
        "hero_island": featured[0] if featured else None,
        "portraits": portraits,
        "more_islands": [i for i in featured if i not in portraits][:6],
        "featured_routes": TransportRoute.objects.filter(is_active=True, island__is_published=True)
        .filter(Q(operator__isnull=True) | Q(operator__status=APPROVED)).select_related("island", "operator")
        .order_by(F("operator").desc(nulls_last=True), "-island__is_featured", "island__name")[:4],
        "featured_stays": _live_listings().filter(kind__in=Listing.STAY_KINDS).order_by("-is_featured", "-created_at")[:4],
        "featured_services": _live_listings().filter(kind__in=Listing.EXPERIENCE_KINDS).order_by("-is_featured", "-created_at")[:4],
        "featured_food": _live_listings().filter(kind__in=Listing.FOOD_KINDS).order_by("-is_featured", "-created_at")[:4],
        "island_options": Island.objects.filter(is_published=True).select_related("atoll").order_by("name"),
        "activities": ActivityType.objects.annotate(n=Count("islands")).filter(n__gt=0).order_by("-n")[:8],
        "stats": {
            "islands": Island.objects.filter(is_published=True).count(),
            "stays": _live_listings().filter(kind__in=Listing.STAY_KINDS).count(),
            "services": _live_listings().filter(kind__in=Listing.EXPERIENCE_KINDS).count(),
            "routes": TransportRoute.objects.filter(is_active=True).count(),
            "food": _live_listings().filter(kind__in=Listing.FOOD_KINDS).count(),
            "verified": _live_listings().filter(is_verified=True).count(),
        },
    })


def _figures():
    """Numbers for the strip under the hero. Listing counts appear only once they're large enough to impress."""
    islands = Island.objects.filter(is_published=True)
    live = _live_listings()
    figs = [
        {"n": islands.count(), "label": "island guides", "count": True},
        {"n": islands.values("atoll").distinct().count(), "label": "atolls covered", "count": True},
        {"n": TransportRoute.objects.filter(is_active=True).count(), "label": "boat and flight routes", "count": True},
    ]
    stays = live.filter(kind__in=Listing.STAY_KINDS).count()
    hosts = live.count()
    if stays >= 20:
        figs.append({"n": stays, "label": "places to stay", "count": True})
    elif hosts >= 20:
        figs.append({"n": hosts, "label": "local businesses", "count": True})
    else:
        figs.append({"n": ActivityType.objects.filter(islands__isnull=False).distinct().count(), "label": "kinds of experiences", "count": True})
    figs.append({"text": "0%", "label": "booking fees, ever"})
    return figs


def _plan_by_need(featured_islands):
    """The four 'Plan by need' cards on the home page: photo, count, quick links and a short preview."""
    from django.urls import reverse

    live = _live_listings().select_related("island")
    island_photos = [i.photo_url for i in featured_islands if i.photo_url]
    acts = list(ActivityType.objects.exclude(image_url="").annotate(n=Count("islands")).order_by("-n"))

    def photo(listings, fallback_index):
        for l in listings:
            if l.has_own_photo:
                return l.photo_url
        return island_photos[fallback_index % len(island_photos)] if island_photos else ""

    stays = list(live.filter(kind__in=Listing.STAY_KINDS).order_by("-is_featured", "-is_verified", "-created_at")[:3])
    exps = list(live.filter(kind__in=Listing.EXPERIENCE_KINDS).order_by("-is_featured", "-is_verified", "-created_at")[:3])
    food = list(live.filter(kind__in=Listing.FOOD_KINDS).order_by("-is_featured", "-is_verified", "-created_at")[:3])
    routes_qs = (TransportRoute.objects.filter(is_active=True, island__is_published=True)
                 .filter(Q(operator__isnull=True) | Q(operator__status=APPROVED)).select_related("island"))
    routes = list(routes_qs.order_by(F("operator").desc(nulls_last=True), "-island__is_featured", "island__name")[:3])
    mode_counts = dict(routes_qs.values_list("mode").annotate(n=Count("id")))
    stay_url, exp_url = reverse("directory:stay_list"), reverse("directory:service_list")
    food_url, tr_url = reverse("directory:food_list"), reverse("directory:transport_list")
    n_stays = live.filter(kind__in=Listing.STAY_KINDS).count()
    n_exps = live.filter(kind__in=Listing.EXPERIENCE_KINDS).count()
    n_food = live.filter(kind__in=Listing.FOOD_KINDS).count()
    n_routes = routes_qs.count()
    exp_photo = next((a.image_url for a in acts), "") or photo(exps, 1)

    def plural(n, one, many):
        return f"{n} {one if n == 1 else many}"

    return [
        {"key": "stays", "title": "Stays", "icon": "house", "url": stay_url, "photo": photo(stays, 0),
         "count": plural(n_stays, "place to stay", "places to stay"), "n": n_stays,
         "text": "Guest houses and small hotels run by island families, a short walk from the beach.",
         "chips": [("Guest houses", f"{stay_url}?kind=guesthouse"), ("Island hotels", f"{stay_url}?kind=hotel"),
                   ("Home stays", f"{stay_url}?kind=villa"), ("Resorts", f"{stay_url}?kind=resort")],
         "items": [{"name": l.name, "meta": l.island.name + (" · Verified" if l.is_verified else ""), "url": l.get_absolute_url(),
                    "img": l.photo_url, "icon": l.kind_icon} for l in stays],
         "empty": "Local guest houses are joining now.", "cta": "All stays"},
        {"key": "exp", "title": "Experiences", "icon": "sailboat", "url": exp_url, "photo": exp_photo,
         "count": plural(n_exps, "operator", "operators") if n_exps else f"{len(acts)} activities to choose from", "n": n_exps,
         "text": "Snorkelling, diving, sandbank trips and fishing with the people who know the reef.",
         "chips": [(a.name, f"{exp_url}?activity={a.slug}") for a in acts[:4]] or [("Dive centres", f"{exp_url}?kind=dive")],
         "items": [{"name": l.name, "meta": f"{l.island.name} · {l.get_kind_display()}", "url": l.get_absolute_url(),
                    "img": l.photo_url, "icon": l.kind_icon} for l in exps],
         "empty": "Dive centres and excursion operators are joining now.", "cta": "All experiences"},
        {"key": "transport", "title": "Getting there", "icon": "ship", "url": tr_url, "photo": photo([], 2),
         "count": plural(n_routes, "route", "routes"), "n": n_routes,
         "text": "Public ferries, shared speedboats and domestic flights from Malé and Velana Airport.",
         "chips": [(label, f"{tr_url}?mode={mode}") for mode, label in TransportRoute.MODE_CHOICES if mode_counts.get(mode)][:4],
         "items": [{"name": f"{r.mode_label} to {r.island.name}", "meta": r.duration + (f" · {r.provider}" if r.provider else ""),
                    "url": r.island.get_absolute_url() + "#transport", "img": "", "icon": r.mode_icon} for r in routes],
         "empty": "Routes are being added.", "cta": "Ferries, speedboats and flights"},
        {"key": "food", "title": "Food", "icon": "utensils", "url": food_url, "photo": photo(food, 3),
         "count": plural(n_food, "place to eat", "places to eat"), "n": n_food,
         "text": "Island cafés and family restaurants: mas huni (tuna and coconut) breakfasts, reef fish and fresh juice.",
         "chips": [],
         "items": [{"name": l.name, "meta": l.island.name + (f" · {l.cuisine}" if l.cuisine else ""), "url": l.get_absolute_url(),
                    "img": l.photo_url, "icon": l.kind_icon} for l in food],
         "empty": "Island cafés and restaurants are joining now.", "cta": "All places to eat"},
    ]


def island_list(request):
    qs = _islands()
    q = request.GET.get("q", "").strip()
    atoll = request.GET.get("atoll", "")
    activity = request.GET.get("activity", "")
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(atoll__name__icontains=q) | Q(atoll__official_name__icontains=q)
                       | Q(tagline__icontains=q) | Q(famous_for__icontains=q))
    if atoll:
        qs = qs.filter(atoll__slug=atoll)
    if activity:
        qs = qs.filter(activities__slug=activity)
    if request.GET.get("bikini"):
        qs = qs.filter(has_bikini_beach=True)
    if request.GET.get("type"):
        qs = qs.filter(island_type=request.GET["type"])
    sort = request.GET.get("sort", "name")
    qs = qs.order_by({"stays": "-stay_count", "near": "distance_from_airport_km", "atoll": "atoll__order", "size": "-population"}.get(sort, "name"))
    page = Paginator(qs.distinct(), 18).get_page(request.GET.get("page"))
    base = _islands()

    def link(**kw):
        params = {k: v for k, v in {"q": q, "atoll": atoll}.items() if v}
        params.update(kw)
        return urlencode(params)

    chips = [
        ("All islands", link(), not (activity or request.GET.get("bikini") or sort != "name"), "map"),
        ("Bikini beach", link(bikini=1), bool(request.GET.get("bikini")), "umbrella"),
        ("Closest to Malé", link(sort="near"), sort == "near", "plane-landing"),
    ]
    for slug, label, ic in [("whale-shark-excursion", "Whale sharks", "fish"), ("manta-ray-snorkeling", "Mantas", "waves"),
                            ("surfing", "Surf", "waves"), ("scuba-diving", "Diving", "anchor"), ("turtle-snorkeling", "Turtles", "turtle"),
                            ("sandbank-picnic", "Sandbanks", "sun")]:
        if base.filter(activities__slug=slug).exists():
            chips.append((label, link(activity=slug), activity == slug, ic))
    chips.append(("Most places to stay", link(sort="stays"), sort == "stays", "bed-double"))
    atoll_strip = list(Atoll.objects.filter(islands__is_published=True).annotate(n=Count("islands", filter=Q(islands__is_published=True))).order_by("order", "name").prefetch_related("islands"))
    auto = next((i.photo_url for i in base.filter(is_featured=True) if i.photo_url), "") or next((i.photo_url for i in base[:12] if i.photo_url), "")
    hero_photo, hero_credit = PageBanner.for_page("islands", auto)
    filtered = bool(q or atoll or activity or request.GET.get("bikini") or request.GET.get("type"))
    return render(request, "directory/island_list.html", {
        "page": page, "atolls": Atoll.objects.all(), "activities": ActivityType.objects.all(),
        "q": q, "atoll_sel": atoll, "activity_sel": activity, "sort": sort, "chips": chips,
        "atoll_strip": atoll_strip, "hero_photo": hero_photo, "hero_credit": hero_credit, "filtered": filtered,
        "atoll_obj": next((a for a in atoll_strip if a.slug == atoll), None),
        "regions": [("all", "All")] + [(k, v) for k, v in Atoll._meta.get_field("region").choices if any(a.region == k for a in atoll_strip)],
        "region_sel": next((a.region for a in atoll_strip if a.slug == atoll), "all"),
        "checked": base.filter(details_verified=True).count(),
        "to_check": list(base.filter(details_verified=False).order_by("-population")[:6]),
        "figures": {"islands": base.count(), "atolls": len(atoll_strip), "bikini": base.filter(has_bikini_beach=True).count(),
                    "stays": _live_listings().filter(kind__in=Listing.STAY_KINDS).count(), "min_shown": 20},
    })


def island_detail(request, slug):
    island = get_object_or_404(_islands().prefetch_related("activities", "photos"), slug=slug)
    listings = _live_listings().filter(island=island).prefetch_related("activity_types")
    kind = request.GET.get("kind", "")
    stays = listings.filter(kind__in=Listing.STAY_KINDS)
    if kind:
        stays = stays.filter(kind=kind)
    nearby = _islands().filter(atoll=island.atoll).exclude(pk=island.pk)[:4]
    url = request.build_absolute_uri(island.get_absolute_url())
    place = {"@context": "https://schema.org", "@type": "TouristDestination", "name": f"{island.name}, {island.atoll.name}",
             "description": island.tagline or island.overview[:200], "url": url,
             "containedInPlace": {"@type": "AdministrativeArea", "name": island.atoll.official_name or island.atoll.name,
                                  "containedInPlace": {"@type": "Country", "name": "Maldives"}}}
    if island.photo_url:
        place["image"] = request.build_absolute_uri(island.photo_url)
    if island.latitude and island.longitude:
        place["geo"] = {"@type": "GeoCoordinates", "latitude": float(island.latitude), "longitude": float(island.longitude)}
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Islands", "item": request.build_absolute_uri(reverse("directory:island_list"))},
        {"@type": "ListItem", "position": 2, "name": island.atoll.name, "item": request.build_absolute_uri(island.atoll.get_absolute_url())},
        {"@type": "ListItem", "position": 3, "name": island.name, "item": url}]}
    return render(request, "directory/island_detail.html", {
        "island": island, "stays": stays, "kind": kind, "nearby": nearby, "ld": [place, crumbs],
        "guides": island.guides.filter(is_published=True)[:3],
        "helpers": island_helpers(island),
        "services": listings.filter(kind__in=Listing.EXPERIENCE_KINDS),
        "food": listings.filter(kind__in=Listing.FOOD_KINDS),
        "shops": listings.filter(kind__in=Listing.SHOP_KINDS),
        "transport": listings.filter(kind__in=Listing.TRANSPORT_KINDS),
        "routes": island.routes.filter(is_active=True).filter(Q(operator__isnull=True) | Q(operator__status=APPROVED)).select_related("operator"),
        "stay_kinds": Listing.KIND_CHOICES[0][1],
    })


def atoll_list(request):
    atolls = Atoll.objects.order_by("order", "name").annotate(
        n_islands=Count("islands", filter=Q(islands__is_published=True), distinct=True),
        n_listings=Count("islands__listings", filter=Q(islands__listings__status=APPROVED), distinct=True),
    )
    return render(request, "directory/atoll_list.html", {"atolls": atolls})


def atoll_detail(request, slug):
    atoll = get_object_or_404(Atoll, slug=slug)
    islands = _islands().filter(atoll=atoll)
    return render(request, "directory/atoll_detail.html", {
        "atoll": atoll, "islands": islands,
    })


def _filtered_listings(request, kinds):
    qs = _live_listings().filter(kind__in=kinds)
    f = {k: request.GET.get(k, "") for k in ("q", "island", "atoll", "kind", "max_price", "guests", "activity", "amenity")}
    if f["q"]:
        qs = qs.filter(Q(name__icontains=f["q"]) | Q(island__name__icontains=f["q"]) | Q(short_description__icontains=f["q"]) | Q(cuisine__icontains=f["q"]))
    if f["island"]:
        qs = qs.filter(island__slug=f["island"])
    if f["atoll"]:
        qs = qs.filter(island__atoll__slug=f["atoll"])
    if f["kind"] in kinds:
        qs = qs.filter(kind=f["kind"])
    if settings.SHOW_PRICES and f["max_price"].isdigit():
        qs = qs.filter(price_from__lte=int(f["max_price"]))
    if f["guests"].isdigit():
        qs = qs.filter(Q(max_guests__gte=int(f["guests"])) | Q(max_guests__isnull=True))
    if f["activity"]:
        qs = qs.filter(activity_types__slug=f["activity"])
    if request.GET.get("verified"):
        qs = qs.filter(is_verified=True)
    if f["amenity"].isdigit():
        qs = qs.filter(amenities__id=int(f["amenity"]))
    if request.GET.get("breakfast"):
        qs = qs.filter(serves_breakfast=True)
    if request.GET.get("delivery"):
        qs = qs.filter(delivery=True)
    sort = request.GET.get("sort", "")
    if sort == "price" and settings.SHOW_PRICES:
        qs = qs.order_by("price_from")
    elif sort == "new":
        qs = qs.order_by("-created_at")
    return Paginator(qs.distinct(), 12).get_page(request.GET.get("page")), f, sort


def stay_list(request):
    from .models import PageBanner

    page, f, sort = _filtered_listings(request, Listing.STAY_KINDS)
    island = Island.objects.filter(slug=f["island"]).first() if f["island"] else None
    amen = {a.name: a.id for a in Amenity.objects.all()}
    base = {k: v for k, v in request.GET.items() if k not in ("page", "kind", "amenity", "verified")
            and (k != "max_price" or settings.SHOW_PRICES)}

    def link(**extra):
        from urllib.parse import urlencode

        return "?" + urlencode({**base, **extra}) + "#stays"

    chips = [("All stays", link(), not (f["kind"] or f["amenity"] or request.GET.get("verified")), "house")]
    for key, label, ic in (("guesthouse", "Guest houses", "house"), ("hotel", "Island hotels", "hotel"), ("villa", "Home stays & villas", "bed-double")):
        chips.append((label, link(kind=key), f["kind"] == key, ic))
    for name, label, ic in (("Breakfast included", "Breakfast included", "coffee"), ("Sea view", "Sea view", "waves"),
                            ("Family rooms", "Family rooms", "baby"), ("Airport transfer arranged", "Transfer arranged", "ship")):
        if name in amen:
            chips.append((label, link(amenity=amen[name]), f["amenity"] == str(amen[name]), ic))
    chips.append(("Verified hosts", link(verified=1), bool(request.GET.get("verified")), "badge-check"))
    top_islands = [i for i in _islands().filter(stay_count__gt=0).order_by("-stay_count", "name")[:8]]
    if len(top_islands) < 4:
        top_islands += [i for i in _islands().filter(is_featured=True).exclude(pk__in=[i.pk for i in top_islands])][: 8 - len(top_islands)]
    auto = (island.photo_url if island and island.photo_url else "") or next((i.photo_url for i in _islands().filter(is_featured=True) if i.photo_url), "")
    hero_photo, hero_credit = (auto, "") if island and island.photo_url else PageBanner.for_page("stays", auto)
    live = _live_listings().filter(kind__in=Listing.STAY_KINDS)
    return render(request, "directory/stay_list.html", {
        "page": page, "f": f, "sort": sort, "chips": chips, "island": island, "top_islands": top_islands,
        "islands": Island.objects.filter(is_published=True).order_by("name"),
        "hero_photo": hero_photo, "hero_credit": hero_credit,
        "n_stays": live.count(), "n_islands": live.values("island").distinct().count(), "n_verified": live.filter(is_verified=True).count(),
        "filtered": any(request.GET.get(k) for k in ("q", "island", "atoll", "kind", "amenity", "guests", "verified")),
    })


def service_list(request):
    page, f, sort = _filtered_listings(request, Listing.EXPERIENCE_KINDS)
    live = _live_listings().filter(kind__in=Listing.EXPERIENCE_KINDS)
    activities = list(ActivityType.objects.annotate(
        n_islands=Count("islands", filter=Q(islands__is_published=True), distinct=True),
        n_ops=Count("listings", filter=Q(listings__status=APPROVED, listings__kind__in=Listing.EXPERIENCE_KINDS), distinct=True),
    ).filter(Q(n_islands__gt=0) | Q(n_ops__gt=0)).order_by("-n_islands", "name"))
    activity = next((a for a in activities if a.slug == f["activity"]), None)
    island = Island.objects.filter(slug=f["island"]).first() if f["island"] else None
    best_islands = list(_islands().filter(activities=activity).order_by("-is_featured", "name")[:8]) if activity else []
    hero_photo = (activity.image_url if activity and activity.image_url else "") or (island.photo_url if island and island.photo_url else "") \
        or next((a.image_url for a in activities if a.image_url and a.slug in ("manta-ray-snorkeling", "snorkeling", "scuba-diving")), "") \
        or next((a.image_url for a in activities if a.image_url), "")
    from .models import PageBanner

    if not (activity and activity.image_url) and not (island and island.photo_url):
        hero_photo, hero_credit = PageBanner.for_page("experiences", hero_photo)
    else:
        hero_credit = ""
    return render(request, "directory/experience_list.html", {"hero_credit": hero_credit,
        "page": page, "f": f, "sort": sort, "activity": activity, "island": island, "activities": activities,
        "best_islands": best_islands, "hero_photo": hero_photo,
        "islands": Island.objects.filter(is_published=True).order_by("name"),
        "n_ops": live.count(), "n_acts": len(activities),
        "n_islands": Island.objects.filter(is_published=True, activities__isnull=False).distinct().count(),
        "filtered": any(request.GET.get(k) for k in ("q", "island", "atoll", "activity", "verified")),
    })


def food_list(request):
    page, f, sort = _filtered_listings(request, Listing.FOOD_KINDS)
    food = _live_listings().filter(kind__in=Listing.FOOD_KINDS)
    photos = [i.photo_url for i in _islands().filter(is_featured=True) if i.photo_url]
    island = Island.objects.filter(slug=f["island"]).first() if f["island"] else None
    q = (f["q"] or "").lower()
    chips = [
        ("Restaurants", "kind=restaurant", f["kind"] == "restaurant", "utensils"),
        ("Cafés & teashops", "kind=cafe", f["kind"] == "cafe", "coffee"),
        ("Beach huts & kiosks", "kind=hut", f["kind"] == "hut", "tree-palm"),
        ("Food trucks", "kind=food_truck", f["kind"] == "food_truck", "car-front"),
        ("Breakfast", "breakfast=1", bool(request.GET.get("breakfast")), "sun"),
        ("Delivers to guest houses", "delivery=1", bool(request.GET.get("delivery")), "bike"),
        ("Seafood", "q=seafood", q == "seafood", "fish"),
        ("Maldivian", "q=maldivian", q == "maldivian", "soup"),
    ]
    from .models import PageBanner

    auto = (island.photo_url if island and island.photo_url else "") or (photos[1] if len(photos) > 1 else (photos[0] if photos else ""))
    banner, hero_credit = PageBanner.for_page("food", "")
    return render(request, "directory/food_list.html", {
        "page": page, "f": f, "sort": sort, "chips": chips, "island": island, "hero_credit": hero_credit,
        "islands": Island.objects.filter(is_published=True).order_by("name"),
        "hero_photo": (island.photo_url if island and island.photo_url else "") or banner or auto,
        "n_food": food.count(), "n_islands": food.values("island").distinct().count(),
        "filtered": any(request.GET.get(k) for k in ("q", "island", "atoll", "breakfast", "delivery", "verified", "kind")),
    })


def shop_list(request):
    """Shops, supermarkets and souvenir and handicraft shops on the local islands."""
    page, f, sort = _filtered_listings(request, Listing.SHOP_KINDS)
    shops = _live_listings().filter(kind__in=Listing.SHOP_KINDS)
    island = Island.objects.filter(slug=f["island"]).first() if f["island"] else None
    chips = [
        ("Souvenirs & handicrafts", "kind=souvenir", f["kind"] == "souvenir", "shell"),
        ("Shops & supermarkets", "kind=shop", f["kind"] == "shop", "shopping-cart"),
        ("Verified", "verified=1", bool(request.GET.get("verified")), "badge-check"),
    ]
    auto = (island.photo_url if island and island.photo_url else "") or next((i.photo_url for i in _islands().filter(is_featured=True) if i.photo_url), "")
    hero_photo, hero_credit = PageBanner.for_page("shops", auto)
    if island and island.photo_url:
        hero_photo, hero_credit = island.photo_url, ""
    return render(request, "directory/shop_list.html", {
        "page": page, "f": f, "sort": sort, "chips": chips, "island": island, "hero_photo": hero_photo, "hero_credit": hero_credit,
        "islands": Island.objects.filter(is_published=True).order_by("name"),
        "n_shops": shops.count(), "n_islands": shops.values("island").distinct().count(),
        "filtered": any(request.GET.get(k) for k in ("q", "island", "atoll", "verified", "kind")),
    })


def transport_list(request):
    """Getting around: routes to each island plus transfer operators you can contact."""
    island_slug = request.GET.get("island", "")
    mode = request.GET.get("mode", "")
    routes = (
        TransportRoute.objects.filter(is_active=True, island__is_published=True)
        .filter(Q(operator__isnull=True) | Q(operator__status=APPROVED))
        .select_related("island", "island__atoll", "operator")
        .order_by("island__name", "order")
    )
    operators = _live_listings().filter(kind__in=Listing.TRANSPORT_KINDS)
    island = None
    if island_slug:
        island = Island.objects.filter(slug=island_slug).first()
        routes = routes.filter(island__slug=island_slug)
        operators = operators.filter(Q(island__slug=island_slug) | Q(routes__island__slug=island_slug)).distinct()
    all_routes = routes
    if mode:
        routes = routes.filter(mode=mode)
    # Group routes by destination island, fastest-looking first within each
    groups, by_island = [], {}
    for r in routes:
        if r.island_id not in by_island:
            by_island[r.island_id] = {"island": r.island, "routes": []}
            groups.append(by_island[r.island_id])
        by_island[r.island_id]["routes"].append(r)
    priority = {"speedboat": 0, "flight": 1, "private": 2, "ferry": 3, "seaplane": 4}
    for g in groups:
        g["routes"].sort(key=lambda r: (priority.get(r.mode, 9), r.order))
    counts = dict(all_routes.order_by().values_list("mode").annotate(n=Count("id")))
    mode_info = {
        "ferry": ("Cheapest way to travel, on fixed timetables between Malé and the islands.", "Slow", "$", "No service on most Fridays"),
        "speedboat": ("Shared boats timed around international flights. The usual choice for nearby atolls.", "Fast", "$$", "Book a day ahead"),
        "private": ("Your own boat, any time of day. Good for families, late flights and groups.", "Fastest by sea", "$$$", "Price per boat"),
        "flight": ("Domestic flights to regional airports, then a short boat ride. Best for far atolls.", "Fast over distance", "$$$", "20 kg bags is common"),
        "seaplane": ("Scenic flights, mostly to resorts. Daylight only.", "Fast", "$$$$", "Daylight only"),
    }
    modes = [{"key": k, "label": lbl, "icon": TransportRoute.MODE_ICONS.get(k, "ship"), "n": counts.get(k, 0),
              "text": mode_info.get(k, ("", "", "", ""))[0], "speed": mode_info.get(k, ("", "", "", ""))[1],
              "cost": mode_info.get(k, ("", "", "", ""))[2], "note": mode_info.get(k, ("", "", "", ""))[3]}
             for k, lbl in TransportRoute.MODE_CHOICES]
    acts = {a.slug: a.image_url for a in ActivityType.objects.exclude(image_url="")}
    hero_photo = (island.photo_url if island and island.photo_url else "") or acts.get("island-hopping") or acts.get("dolphin-cruise") or next(
        (i.photo_url for i in _islands().filter(is_featured=True) if i.photo_url), "")
    from .models import PageBanner

    if island and island.photo_url:
        hero_credit = ""
    else:
        hero_photo, hero_credit = PageBanner.for_page("transport", hero_photo)
    return render(request, "directory/transport_list.html", {"hero_credit": hero_credit,
        "routes": routes, "groups": groups, "operators": operators.select_related("island"), "island": island, "mode": mode,
        "modes": modes, "mode_label": dict(TransportRoute.MODE_CHOICES).get(mode, ""),
        "islands": Island.objects.filter(is_published=True).select_related("atoll").order_by("name"),
        "hero_photo": hero_photo, "n_routes": all_routes.count(), "n_islands": all_routes.order_by().values("island").distinct().count(),
    })


def listing_detail(request, slug):
    listing = get_object_or_404(
        Listing.objects.select_related("island", "island__atoll", "owner").prefetch_related("amenities", "activity_types", "photos", "rooms"),
        slug=slug,
    )
    is_owner = request.user.is_authenticated and (request.user == listing.owner or request.user.is_staff)
    if not listing.is_live and not is_owner:
        raise Http404
    form = EnquiryForm(request.POST or None, listing=listing, initial={"adults": 2, "children": 0})
    if request.method == "POST":
        if not listing.is_live:
            messages.error(request, "This listing isn't live yet, so it can't receive requests.")
        elif form.is_valid():
            from analytics.utils import request_snapshot

            enquiry = form.save(commit=False)
            enquiry.listing = listing
            enquiry.ip_address = None  # not stored (privacy policy)
            for field, value in request_snapshot(request).items():
                setattr(enquiry, field, value)
            enquiry.save()
            if enquiry.visitor_id:
                from analytics.models import Visitor
                Visitor.objects.filter(pk=enquiry.visitor_id).update(enquiries=F("enquiries") + 1)
            notifications.enquiry_created(enquiry, request)
            request.session["last_enquiry"] = enquiry.reference
            return redirect("directory:enquiry_sent", ref=enquiry.reference)
    more = _live_listings().filter(island=listing.island).exclude(pk=listing.pk)[:3]
    reviews = listing.reviews.filter(status="published")[:20]
    return render(request, "directory/listing_detail.html", {"listing": listing, "form": form, "is_owner": is_owner, "more": more,
                                                             "reviews": reviews, "ld": [_listing_ld(request, listing, reviews)]})


def _listing_ld(request, listing, reviews):
    """schema.org data so search engines can show the business, its location and its star rating."""
    kind = "LodgingBusiness" if listing.is_stay else ("Restaurant" if listing.kind in Listing.FOOD_KINDS else "TouristAttraction" if listing.kind == Listing.KIND_ACTIVITY else "LocalBusiness")
    if listing.kind == Listing.KIND_GUESTHOUSE:
        kind = "BedAndBreakfast"
    elif listing.kind == Listing.KIND_HOTEL:
        kind = "Hotel"
    elif listing.kind == Listing.KIND_RESORT:
        kind = "Resort"
    elif listing.kind == Listing.KIND_DIVE:
        kind = "SportsActivityLocation"
    data = {"@context": "https://schema.org", "@type": kind, "name": listing.name, "description": listing.short_description,
            "url": request.build_absolute_uri(listing.get_absolute_url()),
            "address": {"@type": "PostalAddress", "streetAddress": listing.address or listing.island.name,
                        "addressLocality": listing.island.name, "addressRegion": listing.island.atoll.official_name or listing.island.atoll.name,
                        "addressCountry": "MV"}}
    if listing.photo_url:
        data["image"] = request.build_absolute_uri(listing.photo_url)
    if listing.island.latitude and listing.island.longitude:
        data["geo"] = {"@type": "GeoCoordinates", "latitude": float(listing.island.latitude), "longitude": float(listing.island.longitude)}
    if listing.kind in Listing.FOOD_KINDS and listing.cuisine:
        data["servesCuisine"] = listing.cuisine
    if listing.rating_count:
        data["aggregateRating"] = {"@type": "AggregateRating", "ratingValue": float(listing.rating_avg), "reviewCount": listing.rating_count, "bestRating": 5}
        data["review"] = [{"@type": "Review", "author": {"@type": "Person", "name": r.name},
                           "reviewRating": {"@type": "Rating", "ratingValue": r.rating, "bestRating": 5},
                           "reviewBody": r.text[:500]} for r in list(reviews)[:5]]
    return data


def enquiry_sent(request, ref):
    if request.session.get("last_enquiry") != ref:
        raise Http404
    enquiry = get_object_or_404(Enquiry.objects.select_related("listing", "listing__island"), reference=ref)
    return render(request, "directory/enquiry_sent.html", {
        "e": enquiry, "l": enquiry.listing, "msg": enquiry.as_message(),
        "subject": f"Request from Island Stay: {enquiry.listing.name} ({enquiry.reference})",
        "review_url": review_link(request, enquiry),
    })


@require_POST
def enquiry_sent_via(request, ref):
    """Records which button the guest used to send their saved request to the host."""
    channel = request.POST.get("channel", "")
    if request.session.get("last_enquiry") == ref and channel in dict(Enquiry.SENT_VIA_CHOICES):
        Enquiry.objects.filter(reference=ref).update(sent_via=channel)
        Enquiry.objects.filter(reference=ref, sent_at__isnull=True).update(sent_at=timezone.now())
    return HttpResponse(status=204)


def list_your_business(request):
    from .models import HomeFeature, PageBanner

    islands = list(_islands().filter(is_featured=True))
    photo_islands = [i for i in (HomeFeature.islands_for(HomeFeature.SECTION_HERO) or []) + islands if i.photo_url]
    acts = {a.slug: a for a in ActivityType.objects.exclude(image_url="")}

    def act_img(*slugs):
        for s in slugs:
            if s in acts:
                return acts[s].image_url
        return ""

    pick = lambda n: photo_islands[n % len(photo_islands)].photo_url if photo_islands else ""  # noqa: E731
    return render(request, "directory/list_your_business.html", {
        "islands_count": Island.objects.filter(is_published=True).count(),
        "atolls_count": Island.objects.filter(is_published=True).values("atoll").distinct().count(),
        "routes_count": TransportRoute.objects.filter(is_active=True).count(),
        "hero_photo": PageBanner.for_page("list_business", pick(0))[0],
        "hero_credit": PageBanner.for_page("list_business", pick(0))[1],
        "kinds": [
            {"title": "Stays", "icon": "house", "img": pick(1), "text": "Guest houses, island hotels, home stays and private villas."},
            {"title": "Experiences", "icon": "sailboat", "img": act_img("snorkeling", "scuba-diving", "sandbank-picnic") or pick(2),
             "text": "Dive centres, excursion and fishing trips, sandbank picnics, spa and photography."},
            {"title": "Transport", "icon": "ship", "img": act_img("island-hopping", "dolphin-cruise") or pick(3),
             "text": "Speedboat and transfer services. Add your routes once and appear on every island you serve."},
            {"title": "Food", "icon": "utensils", "img": pick(4), "text": "Cafés and restaurants, with your cuisine, opening hours and table requests."},
        ],
    })


def privacy(request):
    return render(request, "directory/privacy.html")


def cookies(request):
    return render(request, "directory/cookies.html")


def photo_credits(request):
    return render(request, "directory/photo_credits.html", {
        "islands": Island.objects.filter(is_published=True).exclude(cover_image_url="").order_by("name"),
        "gallery": IslandPhoto.objects.filter(is_visible=True, island__is_published=True).select_related("island"),
        "activities": ActivityType.objects.exclude(image_url=""),
    })


def how_it_works(request):
    return render(request, "directory/how_it_works.html")


def suggest_island(request):
    form = IslandSuggestionForm(request.POST or None, initial={"contact_email": getattr(request.user, "email", "")})
    if request.method == "POST" and form.is_valid():
        s = form.save(commit=False)
        if request.user.is_authenticated:
            s.submitted_by = request.user
        s.save()
        messages.success(request, f"Thanks! We'll review '{s.island_name}' and add it soon.")
        return redirect("directory:dashboard" if request.user.is_authenticated else "directory:home")
    return render(request, "directory/form_page.html", {
        "form": form, "title": "Suggest an island", "intro": "Is your island missing? Tell us and our team will add it with local information.", "submit": "Send suggestion",
    })


# ---------------------------------------------------------------- owner dashboard

@login_required
def dashboard(request):
    listings = request.user.listings.select_related("island").annotate(
        n_enquiries=Count("enquiries"), n_new=Count("enquiries", filter=Q(enquiries__status=Enquiry.STATUS_NEW))
    )
    recent = Enquiry.objects.filter(listing__owner=request.user).select_related("listing")[:8]
    live_count = sum(1 for l in listings if l.is_live)
    return render(request, "dashboard/home.html", {"listings": listings, "recent": recent, "live_count": live_count})


def _own_listing(request, pk):
    qs = Listing.objects.all() if request.user.is_staff else request.user.listings.all()
    return get_object_or_404(qs, pk=pk)


@login_required
def listing_create(request):
    initial = {"contact_email": request.user.email, "contact_name": request.user.get_full_name()}
    profile = getattr(request.user, "profile", None)
    if profile:
        initial.update(name=profile.business_name, contact_phone=profile.phone, whatsapp=profile.phone)
        isl = Island.objects.filter(name__iexact=profile.island_of_operation).first()
        if isl:
            initial["island"] = isl
    if request.GET.get("island"):
        initial["island"] = Island.objects.filter(slug=request.GET["island"]).first()
    form = ListingForm(request.POST or None, request.FILES or None, initial=initial)
    rooms = RoomFormSet(request.POST or None, prefix="rooms")
    if request.method == "POST" and form.is_valid() and rooms.is_valid():
        listing = form.save(commit=False)
        listing.owner = request.user
        listing.status = Listing.STATUS_PENDING
        listing.save()
        form.save_m2m()
        rooms.instance = listing
        rooms.save()
        notifications.listing_submitted(listing, request)
        messages.success(request, f"'{listing.name}' was submitted for review. We'll email you once it's approved.")
        return redirect("directory:listing_photos", pk=listing.pk)
    return render(request, "dashboard/listing_form.html", {"form": form, "rooms": rooms, "creating": True})


@login_required
def listing_edit(request, pk):
    listing = _own_listing(request, pk)
    form = ListingForm(request.POST or None, request.FILES or None, instance=listing)
    rooms = RoomFormSet(request.POST or None, instance=listing, prefix="rooms")
    if request.method == "POST" and form.is_valid() and rooms.is_valid():
        listing = form.save(commit=False)
        if listing.status == Listing.STATUS_REJECTED:
            listing.status = Listing.STATUS_PENDING
            notifications.listing_submitted(listing, request)
        listing.save()
        form.save_m2m()
        rooms.save()
        messages.success(request, "Listing updated.")
        return redirect("directory:dashboard")
    return render(request, "dashboard/listing_form.html", {"form": form, "rooms": rooms, "listing": listing})


@login_required
def listing_routes(request, pk):
    listing = _own_listing(request, pk)
    formset = RouteFormSet(request.POST or None, instance=listing, prefix="routes")
    if request.method == "POST" and formset.is_valid():
        formset.save()
        messages.success(request, "Routes saved.")
        return redirect("directory:listing_routes", pk=listing.pk)
    return render(request, "dashboard/listing_routes.html", {"listing": listing, "formset": formset})


@login_required
def listing_verify(request, pk):
    listing = _own_listing(request, pk)
    form = VerificationForm(request.POST or None, request.FILES or None, instance=listing)
    if request.method == "POST" and form.is_valid():
        listing = form.save(commit=False)
        listing.verification_requested_at = timezone.now()
        listing.save()
        notifications.verification_requested(listing, request)
        messages.success(request, "Thanks! Our team will check your documents and add the Verified host badge.")
        return redirect("directory:dashboard")
    return render(request, "dashboard/listing_verify.html", {"listing": listing, "form": form})


@login_required
def listing_photos(request, pk):
    listing = _own_listing(request, pk)
    form = PhotoUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        ListingPhoto.objects.create(listing=listing, image=form.cleaned_data["image"], caption=form.cleaned_data["caption"], order=listing.photos.count())
        if not listing.cover_image:
            listing.cover_image = form.cleaned_data["image"]
            listing.save(update_fields=["cover_image"])
        messages.success(request, "Photo added.")
        return redirect("directory:listing_photos", pk=listing.pk)
    return render(request, "dashboard/listing_photos.html", {"listing": listing, "form": form})


@login_required
@require_POST
def photo_delete(request, pk):
    qs = ListingPhoto.objects.all() if request.user.is_staff else ListingPhoto.objects.filter(listing__owner=request.user)
    photo = get_object_or_404(qs, pk=pk)
    listing_pk = photo.listing_id
    photo.image.delete(save=False)
    photo.delete()
    messages.success(request, "Photo removed.")
    return redirect("directory:listing_photos", pk=listing_pk)


@login_required
def enquiry_list(request):
    qs = Enquiry.objects.filter(listing__owner=request.user).select_related("listing")
    status = request.GET.get("status", "")
    if status:
        qs = qs.filter(status=status)
    return render(request, "dashboard/enquiry_list.html", {
        "page": Paginator(qs, 20).get_page(request.GET.get("page")), "status": status, "statuses": Enquiry.STATUS_CHOICES,
    })


@login_required
def enquiry_detail(request, ref):
    qs = Enquiry.objects.all() if request.user.is_staff else Enquiry.objects.filter(listing__owner=request.user)
    enquiry = get_object_or_404(qs.select_related("listing", "listing__island"), reference=ref)
    form = EnquiryUpdateForm(request.POST or None, instance=enquiry)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Request updated.")
        return redirect("directory:enquiry_detail", ref=ref)
    return render(request, "dashboard/enquiry_detail.html", {"e": enquiry, "form": form, "review_url": review_link(request, enquiry)})


# ---------------------------------------------------------------- claims, reviews, host insights

def listing_claim(request, slug):
    from .forms import ClaimForm

    listing = get_object_or_404(Listing, slug=slug)
    if listing.is_claimed:
        messages.info(request, "This listing is already managed by its owner.")
        return redirect(listing.get_absolute_url())
    if not request.user.is_authenticated:
        messages.info(request, "Create a free account (or log in) first, then we'll take you back to claim the listing.")
        from urllib.parse import urlencode

        return redirect(reverse("accounts:signup") + "?" + urlencode({"next": request.path}))
    existing = listing.claims.filter(user=request.user, status="pending").first()
    form = ClaimForm(request.POST or None, request.FILES or None,
                     initial={"full_name": request.user.get_full_name(), "phone": getattr(getattr(request.user, "profile", None), "phone", "")})
    if request.method == "POST" and not existing and form.is_valid():
        claim = form.save(commit=False)
        claim.listing, claim.user = listing, request.user
        claim.save()
        messages.success(request, "Thanks! We'll check your claim, usually within a day, and then the listing will appear in your dashboard.")
        return redirect(listing.get_absolute_url())
    return render(request, "directory/listing_claim.html", {"listing": listing, "form": form, "existing": existing})


def review_create(request, ref, token):
    from .forms import ReviewForm
    from .models import Review

    enquiry = get_object_or_404(Enquiry.objects.select_related("listing", "listing__island"), reference=ref)
    if token != Review.token_for(enquiry):
        raise Http404
    existing = getattr(enquiry, "review", None)
    if existing:
        return render(request, "directory/review_done.html", {"e": enquiry, "review": existing, "already": True})
    form = ReviewForm(request.POST or None, initial={"name": enquiry.guest_name.split()[0] if enquiry.guest_name else "",
                                                     "country": enquiry.guest_country,
                                                     "visited": enquiry.check_in.strftime("%B %Y") if enquiry.check_in else ""})
    if request.method == "POST" and form.is_valid():
        review = form.save(commit=False)
        review.listing, review.enquiry = enquiry.listing, enquiry
        review.save()
        return render(request, "directory/review_done.html", {"e": enquiry, "review": review})
    return render(request, "directory/review_form.html", {"e": enquiry, "form": form})


def review_link(request, enquiry):
    from .models import Review

    return request.build_absolute_uri(reverse("directory:review_create", args=[enquiry.reference, Review.token_for(enquiry)]))


@login_required
def review_reply(request, pk):
    from .forms import HostReplyForm
    from .models import Review

    qs = Review.objects.all() if request.user.is_staff else Review.objects.filter(listing__owner=request.user)
    review = get_object_or_404(qs.select_related("listing"), pk=pk)
    form = HostReplyForm(request.POST or None, initial={"reply": review.host_reply})
    if request.method == "POST" and form.is_valid():
        review.host_reply = form.cleaned_data["reply"]
        review.host_replied_at = timezone.now()
        review.save(update_fields=["host_reply", "host_replied_at"])
        messages.success(request, "Reply saved. It shows under the review on your listing.")
        return redirect("directory:listing_insights", pk=review.listing_id)
    return render(request, "dashboard/review_reply.html", {"review": review, "form": form})


@login_required
def listing_insights(request, pk):
    """How a listing is doing: views, visitors, requests, sends, replies and reviews."""
    from datetime import timedelta

    from django.db.models import Sum
    from django.db.models.functions import TruncDate

    from analytics.models import AnonymousPageview, Event
    from analytics.utils import country_name

    listing = _own_listing(request, pk)
    try:
        days = int(request.GET.get("days", 30))
    except ValueError:
        days = 30
    days = days if days in (7, 30, 90) else 30
    since = timezone.now() - timedelta(days=days)
    path = listing.get_absolute_url()
    views = Event.objects.filter(type="pageview", path=path, ts__gte=since)
    anon = AnonymousPageview.objects.filter(path=path, date__gte=since.date()).aggregate(n=Sum("views"))["n"] or 0
    n_views = views.count() + anon
    visitors = views.values("visitor").distinct().count()
    reqs = listing.enquiries.filter(created_at__gte=since)
    n_req = reqs.count()
    sent = reqs.exclude(sent_via="").count()
    replied = reqs.exclude(status=Enquiry.STATUS_NEW).count()
    by_day = dict(views.annotate(d=TruncDate("ts")).values("d").annotate(n=Count("id")).values_list("d", "n"))
    req_day = dict(reqs.annotate(d=TruncDate("created_at")).values("d").annotate(n=Count("id")).values_list("d", "n"))
    day_list = [(since + timedelta(days=i + 1)).date() for i in range(days)]
    peak = max([by_day.get(d, 0) for d in day_list] + [1])
    bars = [{"d": d, "n": by_day.get(d, 0), "r": req_day.get(d, 0), "h": round(100 * by_day.get(d, 0) / peak)} for d in day_list]
    from collections import Counter

    countries = Counter(views.values_list("visitor__country", flat=True))
    sources = Counter(views.values_list("visit__source", flat=True))
    pct = lambda a, b: round(100 * a / b) if b else 0  # noqa: E731
    reviews = listing.reviews.all()
    return render(request, "dashboard/listing_insights.html", {
        "listing": listing, "days": days, "bars": bars,
        "kpis": [("Page views", n_views, f"{visitors} people (who allowed analytics)"),
                 ("Booking requests", n_req, f"{pct(n_req, visitors)}% of visitors sent one" if visitors else "in this period"),
                 ("Sent to you", f"{pct(sent, n_req)}%", f"{sent} guests pressed WhatsApp, email…"),
                 ("You replied", f"{pct(replied, n_req)}%", listing.response_label or "Mark requests as replied in your dashboard")],
        "countries": [(country_name(c), n) for c, n in countries.most_common(6) if c],
        "sources": [(s or "Direct", n) for s, n in sources.most_common(6)],
        "reviews": reviews, "pending_reviews": reviews.filter(status="pending").count(),
    })


def cron_photos(request):
    """Called daily by Vercel Cron (Authorization: Bearer CRON_SECRET) to link missing Wikimedia photos."""
    import io

    from django.core.management import call_command
    from django.http import HttpResponseForbidden, JsonResponse

    if not settings.CRON_SECRET or request.headers.get("Authorization") != f"Bearer {settings.CRON_SECRET}":
        return HttpResponseForbidden("Forbidden")
    out = io.StringIO()
    call_command("fetch_island_photos", max_seconds=40, stdout=out, stderr=out)
    from analytics.views import purge

    purge()  # analytics older than about 13 months
    return JsonResponse({"log": out.getvalue().splitlines()[-30:]})


# ---------------------------------------------------------------- guides, saved lists, compare
GUIDE_TOPICS = {
    "planning": ("calendar", "Seasons, budgets and itineraries for your trip"),
    "islands": ("map", "How to pick the right island for you"),
    "rules": ("scroll-text", "Dress code, alcohol, prayer times and customs"),
    "transport": ("ship", "Speedboats, ferries and flights between islands"),
    "activities": ("fish", "Whale sharks, mantas, diving, surf and sandbanks"),
    "money": ("banknote", "Cash, cards, SIM cards, Wi-Fi and taxes"),
}


def guide_list(request):
    base = Guide.objects.filter(is_published=True, published_at__lte=timezone.now()).prefetch_related("islands")
    cat, q, isl = request.GET.get("category", ""), request.GET.get("q", "").strip()[:80], request.GET.get("island", "")
    cats = dict(Guide.CATEGORY_CHOICES)
    counts = dict(base.values_list("category").annotate(n=Count("id")).values_list("category", "n"))
    topics = [{"key": k, "label": v, "icon": GUIDE_TOPICS[k][0], "blurb": GUIDE_TOPICS[k][1], "n": counts.get(k, 0)}
              for k, v in Guide.CATEGORY_CHOICES if counts.get(k)]
    qs = base
    if cat in cats:
        qs = qs.filter(category=cat)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(summary__icontains=q) | Q(body__icontains=q) | Q(islands__name__icontains=q)).distinct()
    island = Island.objects.filter(slug=isl, is_published=True).first() if isl else None
    if island:
        qs = qs.filter(islands=island)
    filtered = bool(cat in cats or q or island)
    guides = list(qs)
    essentials, sections, rest = [], [], []
    if not filtered:
        essentials = list(base.filter(is_featured=True)[:3])
        essentials += [g for g in guides if g not in essentials][: 3 - len(essentials)]
        shown = {g.pk for g in essentials}
        for t in topics:
            items = [g for g in guides if g.category == t["key"] and g.pk not in shown]
            if len(items) >= 2:
                sections.append({**t, "guides": items[:3]})
                shown.update(g.pk for g in items[:3])
        rest = [g for g in guides if g.pk not in shown]
    guide_islands = list(_islands().filter(guides__is_published=True).annotate(n_guides=Count("guides", distinct=True)).order_by("-n_guides", "name")[:12])
    lead = essentials[0] if essentials else (guides[0] if guides else None)
    hero_photo, hero_credit = PageBanner.for_page("guides", lead.photo_url if lead else "")
    return render(request, "directory/guide_list.html", {
        "guides": guides, "essentials": essentials, "sections": sections, "rest": rest, "topics": topics, "cat": cat, "q": q,
        "island": island, "filtered": filtered, "cat_label": cats.get(cat, ""), "cat_icon": GUIDE_TOPICS.get(cat, ("book-open",))[0],
        "guide_islands": guide_islands, "total": base.count(), "hero_photo": hero_photo, "hero_credit": hero_credit,
    })


def guide_detail(request, slug):
    guide = get_object_or_404(Guide.objects.prefetch_related("islands__atoll"), slug=slug, is_published=True)
    islands = _islands().filter(pk__in=[i.pk for i in guide.islands.all()])
    more = Guide.objects.filter(is_published=True).exclude(pk=guide.pk).order_by("-published_at")
    more = list(more.filter(category=guide.category)[:3]) or list(more[:3])
    if len(more) < 3:
        more += list(Guide.objects.filter(is_published=True).exclude(pk__in=[guide.pk] + [m.pk for m in more])[: 3 - len(more)])
    url = request.build_absolute_uri(guide.get_absolute_url())
    ld = [{
        "@context": "https://schema.org", "@type": "Article", "headline": guide.title, "description": guide.summary,
        "datePublished": guide.published_at.isoformat(), "dateModified": guide.updated_at.isoformat(),
        "author": {"@type": "Organization", "name": guide.author}, "mainEntityOfPage": url,
        "publisher": {"@type": "Organization", "name": settings.SITE_NAME},
        **({"image": [request.build_absolute_uri(guide.photo_url)]} if guide.photo_url else {}),
    }]
    if guide.faq_list:
        ld.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in guide.faq_list]})
    return render(request, "directory/guide_detail.html", {"guide": guide, "islands": islands, "more": more, "ld": ld,
                                                           "segments": guide_segments(guide)})


def guide_segments(guide):
    """Blocks grouped for the page: the sidebar sits beside the first text part, questions go after the last."""
    from .guide_blocks import resolve
    if not guide.blocks:
        return []
    segs = resolve(guide.blocks, guide)
    if not segs or segs[-1].get("bleed"):
        segs.append({"blocks": []})
    first = next(s for s in segs if "blocks" in s)
    first["aside"] = True
    segs[-1]["last"] = True
    return segs


def _slugs(value, limit=24):
    return [s for s in dict.fromkeys(x.strip() for x in (value or "").split(",")) if s][:limit]


def saved(request):
    """A visitor's saved islands and listings. The list lives in the browser and is passed in the URL, so it can be shared."""
    i_slugs, l_slugs = _slugs(request.GET.get("i")), _slugs(request.GET.get("l"))
    islands = sorted(_islands().filter(slug__in=i_slugs), key=lambda x: i_slugs.index(x.slug))
    listings = sorted(_live_listings().filter(slug__in=l_slugs), key=lambda x: l_slugs.index(x.slug))
    share_url = request.build_absolute_uri()
    return render(request, "directory/saved.html", {
        "islands": islands, "listings": listings, "has_query": "i" in request.GET or "l" in request.GET,
        "share_url": share_url, "compare_slugs": ",".join(i.slug for i in islands[:4]),
    })


def island_compare(request):
    slugs = _slugs(request.GET.get("i"), 4)
    if request.GET.get("add"):
        slugs = _slugs(",".join(slugs + [request.GET["add"]]), 4)
        return redirect(reverse("directory:island_compare") + "?" + urlencode({"i": ",".join(slugs)}))
    islands = sorted(_islands().filter(slug__in=slugs).prefetch_related("activities"), key=lambda x: slugs.index(x.slug))
    acts = {}
    for i in islands:
        for a in i.activities.all():
            acts.setdefault(a.pk, [a, set()])[1].add(i.pk)
    for i in islands:
        i.remove_qs = ",".join(x.slug for x in islands if x.pk != i.pk)
    activity_rows = sorted(acts.values(), key=lambda r: (-len(r[1]), r[0].name))
    def yes_no(v, i=None):
        return "yes" if v else ("no" if i is None or i.details_verified else "unknown")
    rows = [
        ("Atoll", [i.atoll.name for i in islands], None),
        ("Getting there", [i.transfer_time or "–" for i in islands], None),
        ("Distance from the airport", [f"{i.distance_from_airport_km} km" if i.distance_from_airport_km else "–" for i in islands], None),
        ("Population", [f"{i.population:,}" if i.population else "–" for i in islands], None),
        ("Bikini beach", [yes_no(i.has_bikini_beach, i) for i in islands], "flag"),
        ("ATM", [yes_no(i.has_atm, i) for i in islands], "flag"),
        ("Health care", [i.healthcare_label if (i.details_verified or i.has_hospital or i.has_full_hospital) else "Not confirmed" for i in islands], None),
        ("Pharmacy", [yes_no(i.has_pharmacy, i) for i in islands], "flag"),
        ("Mobile data", [i.mobile_data_label for i in islands], None),
        ("Places to stay", [i.stay_count or "–" for i in islands], None),
        ("Experiences", [i.service_count or "–" for i in islands], None),
        ("Places to eat", [i.food_count or "–" for i in islands], None),
        ("Best time to visit", [i.best_time_to_visit or "–" for i in islands], None),
    ]
    others = _islands().exclude(slug__in=slugs).order_by("name") if len(islands) < 4 else []
    return render(request, "directory/island_compare.html", {
        "islands": islands, "rows": rows, "activity_rows": activity_rows, "others": others,
        "slugs": ",".join(i.slug for i in islands),
    })


# ---------------------------------------------------------------- clean, search-friendly addresses
def _preset(request, **params):
    """Run a list view as if these filters were in the query string (the visitor can still change them)."""
    q = request.GET.copy()
    for k, v in params.items():
        q.setdefault(k, v)
    request.GET = q
    return request


def island_stays(request, slug):
    get_object_or_404(Island, slug=slug, is_published=True)
    return stay_list(_preset(request, island=slug))


def island_things_to_do(request, slug):
    get_object_or_404(Island, slug=slug, is_published=True)
    return service_list(_preset(request, island=slug))


def activity_detail(request, slug):
    get_object_or_404(ActivityType, slug=slug)
    return service_list(_preset(request, activity=slug))


def island_getting_there(request, slug):
    island = get_object_or_404(_islands(), slug=slug)
    routes = list(island.routes.filter(is_active=True).filter(Q(operator__isnull=True) | Q(operator__status=APPROVED)).select_related("operator"))
    operators = _live_listings().filter(island=island, kind__in=Listing.TRANSPORT_KINDS)
    paragraphs = [p.strip() for p in island.getting_there.split("\n\n") if p.strip()]
    answer = f"{island.name} is about {island.transfer_time.lstrip('≈')} from Velana International Airport." if island.transfer_time else ""
    if island.getting_there:
        answer = (answer + " " + island.getting_there.split("\n")[0]).strip()
    faqs = []
    if answer:
        faqs.append((f"How do I get to {island.name} from Malé airport?", answer))
    if island.nearest_airport:
        faqs.append((f"What is the nearest airport to {island.name}?",
                     f"{island.nearest_airport}{f', about {island.nearest_airport_km} km away' if island.nearest_airport_km else ''}."))
    if routes:
        faqs.append((f"Is there a public ferry or speedboat to {island.name}?",
                     " ".join(f"{r.get_mode_display()}: {r.duration}{f' ({r.schedule})' if r.schedule else ''}." for r in routes[:4])))
    ld = []
    if faqs:
        ld.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]})
    nearby = _islands().filter(atoll=island.atoll).exclude(pk=island.pk)[:4]
    return render(request, "directory/island_getting_there.html", {
        "island": island, "routes": routes, "operators": operators, "paragraphs": paragraphs, "faqs": faqs,
        "ld": ld, "nearby": nearby,
    })


# ---------------------------------------------------------------- site-wide search
def _search_all(q, limit=6):
    words = [w for w in q.split() if len(w) > 1][:5] or [q]

    def match(fields):
        cond = Q()
        for w in words:
            part = Q()
            for f in fields:
                part |= Q(**{f + "__icontains": w})
            cond &= part
        return cond

    live = _live_listings()
    islands = list(_islands().filter(match(["name", "atoll__name", "atoll__official_name", "tagline", "famous_for", "activities__name"])).distinct()[:limit])
    acts = list(ActivityType.objects.filter(match(["name", "description"]))[:limit])
    stays = list(live.filter(kind__in=Listing.STAY_KINDS).filter(match(["name", "island__name", "short_description", "description"])).distinct()[:limit])
    exps = list(live.filter(kind__in=Listing.EXPERIENCE_KINDS).filter(match(["name", "island__name", "short_description", "activity_types__name"])).distinct()[:limit])
    food = list(live.filter(kind__in=Listing.FOOD_KINDS).filter(match(["name", "island__name", "short_description", "cuisine"])).distinct()[:limit])
    shops = list(live.filter(kind__in=Listing.SHOP_KINDS).filter(match(["name", "island__name", "short_description"])).distinct()[:limit])
    transport = list(live.filter(kind__in=Listing.TRANSPORT_KINDS).filter(match(["name", "island__name", "short_description"])).distinct()[:limit])
    guides = list(Guide.objects.filter(is_published=True).filter(match(["title", "summary", "body"]))[:limit])
    return {"islands": islands, "activities": acts, "stays": stays, "experiences": exps, "food": food, "shops": shops,
            "transport": transport, "guides": guides}


def search(request):
    """Search everything: islands, activities, stays, experiences, food, transport and guides."""
    q = request.GET.get("q", "").strip()[:80]
    section = request.GET.get("section", "")
    if q:
        exact = Island.objects.filter(is_published=True, name__iexact=q).first()
        if exact:
            anchor = f"#{section}" if section in ("stays", "experiences", "transport", "food", "guide") else ""
            return redirect(exact.get_absolute_url() + anchor)
    results = _search_all(q, 12) if q else {}
    total = sum(len(v) for v in results.values())
    popular = _islands().filter(is_featured=True)[:8] if not total else []
    acts = ActivityType.objects.filter(islands__is_published=True).distinct().order_by("name")[:12] if not total else []
    return render(request, "directory/search.html", {"q": q, "r": results, "total": total, "popular": popular, "popular_acts": acts})


def search_suggest(request):
    """Type-ahead suggestions for search boxes (JSON)."""
    from django.http import JsonResponse
    q = request.GET.get("q", "").strip()[:60]
    if len(q) < 2:
        return JsonResponse({"items": []})
    r = _search_all(q, 4)
    items = []
    for i in r["islands"]:
        items.append({"t": "Island", "label": i.name, "sub": f"{i.atoll.name} · {i.tagline}"[:70], "url": i.get_absolute_url(), "icon": "map-pin"})
    for a in r["activities"]:
        items.append({"t": "Activity", "label": a.name, "sub": "Where to do it and who runs trips", "url": reverse("directory:activity_detail", args=[a.slug]), "icon": a.icon or "waves"})
    for key, label in (("stays", "Stay"), ("experiences", "Experience"), ("food", "Food"), ("shops", "Shop"), ("transport", "Transport")):
        for l in r[key][:3]:
            items.append({"t": label, "label": l.name, "sub": f"{l.get_kind_display()} · {l.island.name}", "url": l.get_absolute_url(), "icon": l.kind_icon})
    for g in r["guides"][:3]:
        items.append({"t": "Guide", "label": g.title, "sub": g.get_category_display(), "url": g.get_absolute_url(), "icon": "book-open"})
    return JsonResponse({"items": items[:10], "all": reverse("directory:search") + "?" + urlencode({"q": q})})


# ---------------------------------------------------------------- the public helps update island guides
def island_contribute(request, slug):
    from .forms import IslandContributionForm
    from .models import ContributionPhoto, IslandContribution
    from PIL import Image

    island = get_object_or_404(_islands(), slug=slug)
    form = IslandContributionForm(request.POST or None, initial={"photo_consent": True})
    current = {k: getattr(island, k) for k, _ in IslandContribution.FACILITIES}
    photo_errors = []
    if request.method == "POST":
        files = request.FILES.getlist("photos")[:8]
        good = []
        for f in files:
            if f.size > 15 * 1024 * 1024:
                photo_errors.append(f"{f.name} is larger than 15 MB.")
                continue
            try:
                img = Image.open(f)
                img.verify()
                f.seek(0)
                good.append(f)
            except Exception:
                photo_errors.append(f"{f.name} isn't a photo we can read.")
        facilities = {k: request.POST.get("fac_" + k) for k, _ in IslandContribution.FACILITIES
                      if request.POST.get("fac_" + k) in ("yes", "no")}
        anything = facilities or good or any(request.POST.get(k, "").strip() for k in
                                             ("transfer_time", "getting_there", "famous_for", "tips", "corrections"))
        if good and not request.POST.get("photo_consent"):
            photo_errors.append("Please confirm the photos are yours to share.")
        if form.is_valid() and anything and not photo_errors:
            c = form.save(commit=False)
            c.island, c.facilities = island, facilities
            c.save()
            for f in good:
                ContributionPhoto.objects.create(contribution=c, image=f)
            request.session["contributed"] = island.slug
            return redirect("directory:island_contribute_thanks", slug=island.slug)
        if not anything:
            form.add_error(None, "Add at least one answer, a tip or a photo before sending.")
    helpers = IslandContribution.objects.filter(island=island, status="applied", show_name=True).values_list("name", flat=True)
    return render(request, "directory/island_contribute.html", {
        "island": island, "form": form, "photo_errors": photo_errors,
        "facilities": [(k, label, current[k], request.POST.get("fac_" + k, "")) for k, label in IslandContribution.FACILITIES],
        "helpers": list(dict.fromkeys(helpers))[:12],
    })


def island_contribute_thanks(request, slug):
    island = get_object_or_404(_islands(), slug=slug)
    nearby = _islands().filter(atoll=island.atoll, details_verified=False).exclude(pk=island.pk)[:6]
    return render(request, "directory/island_contribute_thanks.html", {"island": island, "nearby": nearby})


def island_helpers(island):
    from .models import IslandContribution
    names = IslandContribution.objects.filter(island=island, status="applied", show_name=True).values_list("name", flat=True)
    return list(dict.fromkeys(names))[:8]
