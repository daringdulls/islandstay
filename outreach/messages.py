"""The starting set of message templates (Island Stay speaking as 'we') and filling them in for a lead."""
import datetime as dt

from django.utils import timezone

FIRST_DM = (
    "Hello <name>,\n\n"
    "We're Island Stay (islandstaymv.com), a guide to the Maldives' local islands. Travellers use it to find places to stay and "
    "things to do, and contact businesses directly.\n\n"
    "We would like to invite <business> to be listed on our <island> page. Listing is free, with no commission: guest requests "
    "come straight to you.\n\n"
    "If you're interested, reply to this message and our team will set up your page for you, or you can add it yourself at "
    "islandstaymv.com/list-your-business.\n\n"
    "Kind regards,\nIsland Stay team")
FOLLOW_UP_1 = (
    "Hello <name>,\n\n"
    "We're following up on our invitation to list <business> on Island Stay. <X> travellers viewed <island> on our site in the last 30 days.\n\n"
    "Listing is free and only takes a few minutes: send us a few photos and your prices, and we'll prepare the page for you to review. "
    "You can also add it yourself at islandstaymv.com/list-your-business.\n\n"
    "Kind regards,\nIsland Stay team")
FOLLOW_UP_2 = (
    "Hello <name>,\n\n"
    "A final note from Island Stay: the first 50 businesses to list receive a featured place on their island page for three months, "
    "and a few places remain.\n\n"
    "If now isn't the right time, we completely understand. We wish you a great season.\n\n"
    "Kind regards,\nIsland Stay team")

DEFAULT_MESSAGES = [
    ("First DM", "Day 1", "messaged", FIRST_DM),
    ("Follow-up 1", "3 days after the first DM", "followup1", FOLLOW_UP_1),
    ("Follow-up 2 (last)", "7 days after follow-up 1", "followup2", FOLLOW_UP_2),
    ("Reply: 'How much?'", "When they ask about cost", "",
     "It's free: no sign-up fee and no commission. Guests send you a request through Island Stay and you agree everything with them directly, "
     "by WhatsApp or email."),
    ("Reply: 'Why not Booking.com?'", "When they compare", "",
     "Keep using them! Island Stay is an extra place to be found, made for travellers looking for local islands. Requests come straight to you "
     "and there's no commission to pay."),
    ("We set it up", "When they say they're busy", "",
     "No problem: send us 5 photos, your room prices and your WhatsApp number, and our team will build your page. You check it before it goes live."),
    ("Welcome (listed)", "After they're live", "listed",
     "Welcome to Island Stay! Your page is live: <link>. This week we'll post a free spotlight about <business> on @islandstaymv and tag you, "
     "so please share it in your Story. Booking requests will come to <WhatsApp / email>."),
    ("Referral ask", "1-2 weeks after listing", "",
     "How are things going? If you know another business on <island> that should be on Island Stay, tell them about us: you'll both get a featured week."),
    ("Group post", "Facebook groups (if promotion is allowed)", "",
     "For guest house owners, dive centres and excursion operators on local islands: Island Stay is a free guide where travellers find you and "
     "message you directly. No commission. Comment or message us and we'll set up your page for you. islandstaymv.com/list-your-business"),
    ("Comment reply", "When someone comments on a host post", "",
     "Thank you! If you run a business on <island>, we'd love to add you, free. We've sent you a message."),
    ("Ad text", "'List free' ad", "",
     "Run a guest house, dive centre or excursion on a local island? List it free on Island Stay. Travellers message you directly. "
     "No commission. We'll set it up for you."),
    ("Bio line", "Instagram and Facebook profile", "", "Local island stays and guides across the Maldives. Hosts: list free ↓"),
]


def island_views(island, days=30):
    """Page views of an island's pages (its guide, stays, getting there) in the last `days` days."""
    if island is None:
        return 0
    from django.db.models import Sum

    from analytics.models import AnonymousPageview, Event

    since = timezone.now() - dt.timedelta(days=days)
    prefix = f"/islands/{island.slug}/"
    n = Event.objects.filter(type="pageview", ts__gte=since, path__startswith=prefix).count()
    n += AnonymousPageview.objects.filter(date__gte=since.date(), path__startswith=prefix).aggregate(s=Sum("views"))["s"] or 0
    return n


def fill(text, lead, views=None, site="https://www.islandstaymv.com"):
    island = lead.island
    out = text.replace("<name>", (lead.contact_name.split()[0] if lead.contact_name.strip() else f"{lead.business} team"))
    out = out.replace("<business>", lead.business or "<business>")
    if island:
        out = out.replace("<island>", island.name)
    if views is not None:
        if views < 20:
            # Small numbers don't impress: drop the sentence that mentions them.
            import re
            out = re.sub(r" ?[^.!?\n]*<X>[^.!?\n]*[.!?]", "", out)
        out = out.replace("<X>", str(views))
    if lead.listing_id:
        out = out.replace("<link>", site + lead.listing.get_absolute_url())
    return out
