from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, F, Min, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import notifications
from django.utils import timezone

from .forms import (
    EnquiryForm, EnquiryUpdateForm, IslandSuggestionForm, ListingForm, PhotoUploadForm, RoomFormSet, RouteFormSet,
    VerificationForm,
)
from .models import ActivityType, Amenity, Atoll, Enquiry, Island, IslandPhoto, Listing, ListingPhoto, TransportRoute

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
    return render(request, "directory/home.html", {
        "needs": _plan_by_need(featured),
        "atoll_index": atoll_counts,
        "hero_island": featured[0] if featured else None,
        "portraits": featured[:3],
        "more_islands": featured[3:9],
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


def search(request):
    """Hero search: jump straight to an island if the name matches, otherwise show island results."""
    from urllib.parse import urlencode

    q = request.GET.get("q", "").strip()
    section = request.GET.get("section", "")
    if q:
        exact = Island.objects.filter(is_published=True, name__iexact=q).first()
        if exact:
            anchor = f"#{section}" if section in ("stays", "experiences", "transport", "food", "guide") else ""
            return redirect(exact.get_absolute_url() + anchor)
    return redirect("/islands/?" + urlencode({"q": q}))


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
    return render(request, "directory/island_list.html", {
        "page": page, "atolls": Atoll.objects.all(), "activities": ActivityType.objects.all(),
        "q": q, "atoll_sel": atoll, "activity_sel": activity, "sort": sort,
    })


def island_detail(request, slug):
    island = get_object_or_404(_islands().prefetch_related("activities", "photos"), slug=slug)
    listings = _live_listings().filter(island=island).prefetch_related("activity_types")
    kind = request.GET.get("kind", "")
    stays = listings.filter(kind__in=Listing.STAY_KINDS)
    if kind:
        stays = stays.filter(kind=kind)
    nearby = _islands().filter(atoll=island.atoll).exclude(pk=island.pk)[:4]
    return render(request, "directory/island_detail.html", {
        "island": island, "stays": stays, "kind": kind, "nearby": nearby,
        "services": listings.filter(kind__in=Listing.EXPERIENCE_KINDS),
        "food": listings.filter(kind__in=Listing.FOOD_KINDS),
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
    sort = request.GET.get("sort", "")
    if sort == "price" and settings.SHOW_PRICES:
        qs = qs.order_by("price_from")
    elif sort == "new":
        qs = qs.order_by("-created_at")
    return Paginator(qs.distinct(), 12).get_page(request.GET.get("page")), f, sort


def stay_list(request):
    page, f, sort = _filtered_listings(request, Listing.STAY_KINDS)
    return render(request, "directory/listing_list.html", {
        "page": page, "f": f, "sort": sort, "mode": "stays", "title": "Places to stay",
        "kind_choices": Listing.KIND_CHOICES[0][1], "atolls": Atoll.objects.all(),
        "islands": Island.objects.filter(is_published=True), "amenities": Amenity.objects.all(),
    })


def service_list(request):
    page, f, sort = _filtered_listings(request, Listing.EXPERIENCE_KINDS)
    return render(request, "directory/listing_list.html", {
        "page": page, "f": f, "sort": sort, "mode": "experiences", "title": "Experiences",
        "kind_choices": Listing.KIND_CHOICES[1][1], "atolls": Atoll.objects.all(),
        "islands": Island.objects.filter(is_published=True), "activities": ActivityType.objects.all(),
    })


def food_list(request):
    page, f, sort = _filtered_listings(request, Listing.FOOD_KINDS)
    return render(request, "directory/listing_list.html", {
        "page": page, "f": f, "sort": sort, "mode": "food", "title": "Food & restaurants",
        "kind_choices": [], "atolls": Atoll.objects.all(), "islands": Island.objects.filter(is_published=True),
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
    if mode:
        routes = routes.filter(mode=mode)
    return render(request, "directory/transport_list.html", {
        "routes": routes, "operators": operators, "island": island, "mode": mode,
        "modes": TransportRoute.MODE_CHOICES, "islands": Island.objects.filter(is_published=True),
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
    return render(request, "directory/listing_detail.html", {"listing": listing, "form": form, "is_owner": is_owner, "more": more})


def enquiry_sent(request, ref):
    if request.session.get("last_enquiry") != ref:
        raise Http404
    enquiry = get_object_or_404(Enquiry.objects.select_related("listing", "listing__island"), reference=ref)
    return render(request, "directory/enquiry_sent.html", {
        "e": enquiry, "l": enquiry.listing, "msg": enquiry.as_message(),
        "subject": f"Request from Island Stay: {enquiry.listing.name} ({enquiry.reference})",
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
    return render(request, "directory/list_your_business.html", {"islands_count": Island.objects.filter(is_published=True).count()})


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
    return render(request, "dashboard/enquiry_detail.html", {"e": enquiry, "form": form})


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
