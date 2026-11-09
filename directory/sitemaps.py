"""sitemap.xml: every public page Google should know about."""
from django.contrib.sitemaps import Sitemap
from django.db.models import Count, Q
from django.urls import reverse

from .models import ActivityType, Atoll, Guide, Island, Listing

APPROVED = Listing.STATUS_APPROVED


class StaticSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return ["home", "island_list", "stay_list", "service_list", "transport_list", "food_list", "shop_list", "guide_list",
                "atoll_list", "island_compare", "list_your_business", "how_it_works", "privacy", "cookies"]

    def location(self, item):
        return reverse("directory:" + item)

    def priority(self, item):
        return 1.0 if item == "home" else 0.8 if item in ("island_list", "stay_list", "service_list", "guide_list") else 0.4


class IslandSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.9

    def items(self):
        return Island.objects.filter(is_published=True).order_by("name")

    def lastmod(self, obj):
        return obj.updated_at


class IslandSubpageSitemap(Sitemap):
    """Where to stay / things to do / getting there pages, only where there is something to show."""
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        out = []
        qs = Island.objects.filter(is_published=True).annotate(
            stays=Count("listings", filter=Q(listings__status=APPROVED, listings__kind__in=Listing.STAY_KINDS), distinct=True),
            ops=Count("listings", filter=Q(listings__status=APPROVED, listings__kind__in=Listing.EXPERIENCE_KINDS), distinct=True),
            acts=Count("activities", distinct=True),
        ).order_by("name")
        for i in qs:
            out.append(("island_getting_there", i))
            if i.stays:
                out.append(("island_stays", i))
            if i.ops or i.acts:
                out.append(("island_things_to_do", i))
        return out

    def location(self, item):
        return reverse("directory:" + item[0], args=[item[1].slug])

    def lastmod(self, item):
        return item[1].updated_at


class ActivitySitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return ActivityType.objects.filter(Q(islands__is_published=True) | Q(listings__status=APPROVED)).distinct().order_by("name")

    def location(self, obj):
        return reverse("directory:activity_detail", args=[obj.slug])


class AtollSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.5

    def items(self):
        return Atoll.objects.filter(islands__is_published=True).distinct().order_by("order")


class ListingSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return Listing.objects.filter(status=APPROVED, island__is_published=True).order_by("pk")

    def lastmod(self, obj):
        return obj.updated_at


class GuideSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.8

    def items(self):
        return Guide.objects.filter(is_published=True)

    def lastmod(self, obj):
        return obj.updated_at


SITEMAPS = {"pages": StaticSitemap, "islands": IslandSitemap, "island-pages": IslandSubpageSitemap,
            "activities": ActivitySitemap, "atolls": AtollSitemap, "listings": ListingSitemap, "guides": GuideSitemap}
