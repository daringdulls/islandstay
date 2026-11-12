import re

from django import forms
from django.db.models import F
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from .models import AdEnquiry, AffiliateOffer, Click, Placement

BOTS = re.compile(r"bot|crawl|spider|slurp|preview|facebookexternalhit|whatsapp|curl|wget|python|headless", re.I)


def is_bot(request):
    return bool(BOTS.search(request.headers.get("User-Agent", "")))


def _safe(url):
    if not url or not url.lower().startswith(("https://", "http://")):
        raise Http404
    return url


def _log(request, **kw):
    if is_bot(request):
        return False
    page = request.GET.get("from", "")[:300]
    Click.objects.create(page=page if page.startswith("/") else "", island=request.GET.get("island", "")[:80], **kw)
    return True


@never_cache
def go_sponsor(request, pk):
    p = get_object_or_404(Placement, pk=pk)
    target = _safe(p.link)
    if _log(request, placement=p):
        Placement.objects.filter(pk=p.pk).update(clicks=F("clicks") + 1)
    resp = HttpResponseRedirect(target)
    resp["X-Robots-Tag"] = "noindex, nofollow"
    return resp


@never_cache
def go_affiliate(request, slug):
    o = get_object_or_404(AffiliateOffer, slug=slug, is_active=True)
    target = _safe(o.url)
    if _log(request, offer=o):
        AffiliateOffer.objects.filter(pk=o.pk).update(clicks=F("clicks") + 1)
    resp = HttpResponseRedirect(target)
    resp["X-Robots-Tag"] = "noindex, nofollow"
    return resp


class AdEnquiryForm(forms.ModelForm):
    website = forms.CharField(required=False, widget=forms.HiddenInput)  # honeypot: people leave it empty

    class Meta:
        model = AdEnquiry
        fields = ["name", "company", "email", "phone", "interest", "message"]
        widgets = {"message": forms.Textarea(attrs={"rows": 4, "placeholder": "What would you like to promote, and when?"})}


def advertise(request):
    from directory.models import Atoll, Guide, Island, Listing

    form = AdEnquiryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if not form.cleaned_data.get("website"):
            form.save()
        request.session["ad_enquiry"] = True
        return redirect("partners:advertise_thanks")
    since = timezone.now() - timezone.timedelta(days=30)
    try:
        from analytics.models import Visit
        visits = Visit.objects.filter(started_at__gte=since).count()
    except Exception:
        visits = 0
    stats = {
        "islands": Island.objects.filter(is_published=True).count(),
        "atolls": Atoll.objects.filter(islands__is_published=True).distinct().count(),
        "guides": Guide.objects.filter(is_published=True).count(),
        "listings": Listing.objects.filter(status=Listing.STATUS_APPROVED).count(),
        "visits": visits if visits >= 1000 else None,
    }
    return render(request, "partners/advertise.html", {"form": form, "stats": stats})


def advertise_thanks(request):
    if not request.session.pop("ad_enquiry", False):
        return redirect("partners:advertise")
    return render(request, "partners/advertise_thanks.html")
