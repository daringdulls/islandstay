"""{% sponsored "island" island %} shows one live sponsored card; {% before_you_go "islands" island %} the affiliate box."""
import random
import urllib.parse

from django import template
from django.db.models import F, Q
from django.utils import timezone

register = template.Library()


def _track(url, request, island):
    params = {}
    if request is not None:
        params["from"] = request.path
    if island is not None:
        params["island"] = island.slug
    return url + ("?" + urllib.parse.urlencode(params) if params else "")


@register.inclusion_tag("partners/_sponsored.html", takes_context=True)
def sponsored(context, where, island=None):
    from partners.models import Placement
    from partners.views import is_bot

    request = context.get("request")
    today = timezone.localdate()
    qs = Placement.objects.filter(where=where, is_active=True, starts__lte=today, ends__gte=today).select_related("sponsor")
    if where == Placement.WHERE_ISLAND:
        qs = qs.filter(Q(islands=island) | Q(islands__isnull=True)) if island is not None else qs.filter(islands__isnull=True)
    live = list(qs.distinct())
    if not live:
        return {"p": None}
    p = random.choice(live)  # share the slot between sponsors
    if request is not None and not is_bot(request):
        Placement.objects.filter(pk=p.pk).update(views=F("views") + 1)
    return {"p": p, "href": _track(p.get_click_url(), request, island)}


@register.inclusion_tag("partners/_before_you_go.html", takes_context=True)
def before_you_go(context, where, island=None, limit=4):
    from partners.models import AffiliateOffer

    offers = list(AffiliateOffer.objects.filter(is_active=True, where__in=["all", where])[:limit])
    request = context.get("request")
    return {"offers": [(o, _track(o.get_click_url(), request, island)) for o in offers], "island": island}
