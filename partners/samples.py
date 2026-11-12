"""Sample sponsors, placements and affiliate offers, to see how everything looks. Samples never appear on the site.

Brand names are invented on purpose (no real companies). Links go to example.com.
"""
import datetime as dt


def create_samples(Sponsor, Placement, AffiliateOffer, Island, today=None):
    today = today or dt.date.today()
    if Placement.objects.filter(is_sample=True).exists() or AffiliateOffer.objects.filter(is_sample=True).exists():
        return 0
    photo = ""
    islands = Island.objects.filter(is_published=True).order_by("-is_featured", "name")
    full = islands.filter(cover_image_url__startswith="https://").first()  # a full link passes the form's URL check
    if full:
        photo = full.cover_image_url
    else:
        for island in islands.exclude(cover_image=""):
            try:
                path = island.cover_image.url
            except Exception:
                continue
            if path.startswith("/"):
                from django.conf import settings
                host = (getattr(settings, "CANONICAL_HOST", "") or "www.islandstaymv.com").removeprefix("www.")
                path = f"https://www.{host}{path}"
            photo = path
            break
    dive = Sponsor.objects.create(name="Sample: Blue Reef Divers", is_sample=True, website="https://example.com")
    mobile = Sponsor.objects.create(name="Sample: Atoll Mobile", is_sample=True, website="https://example.com")
    ferry = Sponsor.objects.create(name="Sample: Island Hop Transfers", is_sample=True, website="https://example.com")
    end = today + dt.timedelta(days=30)
    rows = [
        (dive, "island", "Dive the channels of South Ari", "Daily boat dives and PADI courses from local islands.", "See dive trips", ""),
        (mobile, "guide", "Stay connected from the moment you land", "Tourist SIM and eSIM with data on most inhabited islands.", "See plans", ""),
        (ferry, "islands", "Island hopping made simple", "Speedboat transfers from Velana airport to over 40 local islands.", "Book a transfer", photo),
        (ferry, "transport", "Fixed-price airport transfers", "Your driver and boat wait if your flight is late.", "Get a price", ""),
    ]
    for sponsor, where, headline, text, button, image_url in rows:
        Placement.objects.create(sponsor=sponsor, where=where, headline=headline, text=text, button=button, image_url=image_url,
                                 link="https://example.com/", starts=today, ends=end, is_sample=True, price=0)
    offers = [
        ("Sample: SafeTrip", "sample-insurance", "insurance", "Travel insurance that covers diving", "Medical cover for snorkelling and scuba."),
        ("Sample: Roam eSIM", "sample-esim", "esim", "Maldives eSIM, ready before you fly", "Install at home, connect when you land."),
        ("Sample: FlyCompare", "sample-flights", "flights", "Compare flights to Malé (MLE)", "Every airline in one search."),
        ("Sample: Malé Transfers", "sample-transfers", "transfers", "Airport pick-up to the ferry jetty", "Fixed price, meets your flight."),
        ("Sample: Island Tours", "sample-tours", "tours", "Sandbank picnics and snorkel trips", "Book with local operators."),
    ]
    for i, (name, slug, cat, title, blurb) in enumerate(offers):
        AffiliateOffer.objects.create(name=name, slug=slug, category=cat, title=title, blurb=blurb, url="https://example.com/",
                                      order=50 + i, is_sample=True)
    return len(rows) + len(offers)


def remove_samples(Sponsor, Placement, AffiliateOffer):
    n = Placement.objects.filter(is_sample=True).delete()[0] + AffiliateOffer.objects.filter(is_sample=True).delete()[0]
    Sponsor.objects.filter(is_sample=True).delete()
    return n
