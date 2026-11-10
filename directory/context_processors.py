from django.conf import settings
from django.core.cache import cache


def _popular_islands():
    """Islands linked from every page's footer (helps visitors and search engines find them)."""
    data = cache.get("footer_islands")
    if data is None:
        from django.db.models import Count, Q

        from .models import Island, Listing
        qs = (Island.objects.filter(is_published=True)
              .annotate(n=Count("listings", filter=Q(listings__status=Listing.STATUS_APPROVED)))
              .order_by("-is_featured", "-n", "-population")[:10])
        data = [(i.name, i.get_absolute_url()) for i in qs]
        cache.set("footer_islands", data, 600)
    return data


def site(request):
    page = request.GET.get("page", "")
    canonical = f"{request.scheme}://{request.get_host()}{request.path}"
    if page.isdigit() and int(page) > 1:
        canonical += f"?page={int(page)}"
    ctx = {
        "SITE_NAME": settings.SITE_NAME, "SHOW_PRICES": settings.SHOW_PRICES,
        "CONTACT_EMAIL": getattr(settings, "CONTACT_EMAIL", ""),
        "CANONICAL_URL": canonical,
        "GOOGLE_SITE_VERIFICATION": getattr(settings, "GOOGLE_SITE_VERIFICATION", ""),
        "BING_SITE_VERIFICATION": getattr(settings, "BING_SITE_VERIFICATION", ""),
        "GA_MEASUREMENT_ID": "" if request.path.startswith(("/admin/", "/dashboard/", "/accounts/"))
        else __import__("re").sub(r"[^A-Za-z0-9-]", "", getattr(settings, "GA_MEASUREMENT_ID", "")),
    }
    try:
        ctx["FOOTER_ISLANDS"] = _popular_islands()
    except Exception:
        ctx["FOOTER_ISLANDS"] = []
    if request.user.is_authenticated:
        from .models import Enquiry

        ctx["new_enquiry_count"] = Enquiry.objects.filter(listing__owner=request.user, status=Enquiry.STATUS_NEW).count()
    return ctx
