"""Builds a weekly social media plan from the directory: island spotlights, experiences, hosts, tips and facts.

Weekly rhythm (Maldives time):
  Mon 18:00  Island spotlight      portrait  Instagram + Facebook
  Tue 19:00  Travel tip            story     Instagram + Facebook stories
  Wed 18:00  Experience            portrait  Instagram + Facebook + TikTok cover
  Thu 18:00  Did you know          square    Instagram + Facebook + X
  Fri 17:00  Host spotlight        portrait  Instagram + Facebook (a tip if no host is approved yet)
  Sun 10:00  Island of the week    story     Instagram + Facebook stories
"""
import datetime as dt
import itertools

from django.db.models import Count, Max, Q
from django.utils import timezone

from directory.models import ActivityType, Island, Listing

from .models import SocialPost

LINK = "Link in bio"
BASE_TAGS = ["#IslandStay", "#Maldives", "#LocalIslands"]

# Checked, widely published facts. Headline, accent word, design text, caption.
FACTS = [
    ("The world borrowed one Dhivehi word: atoll", "atoll",
     "Atoll comes from atholhu, the Dhivehi word for a ring of islands around a lagoon.",
     "Atoll comes from atholhu, the Dhivehi word for a ring of coral islands around a lagoon. It is the one Dhivehi word every language borrowed, and it is the ring in our logo."),
    ("Cowries were once money", "money",
     "For centuries the Maldives supplied the cowrie shells used as currency across Asia and Africa.",
     "For centuries the Maldives supplied the cowrie shells traded as money across Asia and Africa. Our cowrie points out through the channel: island money going straight to local hosts again."),
    ("1,192 islands in 26 atolls", "1,192",
     "Only a small share are inhabited. Island Stay covers the local ones, where Maldivians live and work.",
     "1,192 coral islands in 26 natural atolls. Most are uninhabited sandbanks and reefs; the local islands are where Maldivians live, fish and run guest houses. That's where we send you."),
    ("A kandu is the way in", "kandu",
     "Kandu: the channel through the reef where boats, and big fish, come and go.",
     "Kandu means channel, the gap in the reef where dhonis sail in and out with the tide. Kandus are also where divers see sharks and mantas feeding in the current."),
    ("A finolhu is a sandbank", "finolhu",
     "Finolhu: a sandbank that comes and goes with the tide. Many guest houses run picnic trips to one.",
     "Finolhu means sandbank. Ask your host about a sandbank picnic: a short dhoni ride, a strip of white sand, lunch and snorkelling, back for sunset."),
    ("The dhoni carries everything", "dhoni",
     "The dhoni is the Maldivian boat, traditionally built from coconut palm wood.",
     "The dhoni is the Maldivian workboat, traditionally built from coconut palm timber. Today dhonis carry fishermen, ferry passengers, dive groups and your luggage from the jetty."),
    ("Guest houses opened the islands", "islands",
     "Since 2009, local islands can host guests, so visitors can stay where Maldivians live.",
     "Since 2009 local islands have been allowed to host tourists. That change made guest houses, local dive centres and island cafés possible, and it is why Island Stay exists."),
]

# Practical advice. Headline, accent word, three or four points, caption.
TIPS = [
    ("What to wear on a local island", "wear",
     "Cover shoulders and knees in the village\nSwimwear is for the bikini beach\nLight, loose cotton works best\nPack a sarong for the boat ride",
     "Local islands are home to Maldivian families, so the village has a dress code: shoulders and knees covered. On the bikini beach, swimwear is fine. Each island guide shows whether there's a bikini beach."),
    ("Ferry days", "Ferry",
     "Most public ferries don't run on Fridays\nCheck times the day before\nSpeedboats cost more but save hours\nAsk your host to book the transfer",
     "Public ferries are the cheapest way between islands, but most don't run on Fridays. Plan transfers around the weekend, or ask your host to arrange a speedboat."),
    ("Cash on the islands", "Cash",
     "Not every island has an ATM\nCarry some US dollars or rufiyaa\nCards work at most guest houses\nSmall notes help at cafés and shops",
     "Not every local island has an ATM. Carry some cash in US dollars or Maldivian rufiyaa for cafés, shops and tips. Island guides list where you'll find an ATM."),
    ("No alcohol on local islands", "alcohol",
     "Local islands are alcohol-free\nResorts and safari boats serve it\nDon't bring it through customs\nTry fresh juice and kurumba instead",
     "Local islands are alcohol-free, and alcohol can't be brought into the country. Resorts and safari boats can serve it, and many guest houses run day trips to a resort."),
    ("Look after the reef", "reef",
     "Don't touch or stand on coral\nUse reef-safe sunscreen\nKeep your distance from turtles\nTake your rubbish home",
     "The reef is the islands' living. Don't touch or stand on coral, give turtles and sharks space, and use reef-safe sunscreen. Local guides will show you how."),
    ("Flying a drone?", "drone",
     "You need a permit from the aviation authority\nAsk before filming people\nNo flying near airports or resorts\nYour host can advise",
     "Drones need a permit from the Maldives Civil Aviation Authority. Ask people before filming them, and keep away from airports and resorts."),
]


def _tags(*extra):
    tags = list(BASE_TAGS)
    for e in extra:
        if e:
            tag = "#" + "".join(ch for ch in e.title() if ch.isalnum())
            if tag not in tags:
                tags.append(tag)
    return " ".join(tags)


def _least_used(qs, field):
    """Order so items never or least recently posted about come first."""
    return qs.annotate(last_post=Max(f"social_posts__publish_at"), n_posts=Count("social_posts")).order_by("n_posts", "last_post", "?")


def island_post(island, fmt="portrait", story=False):
    facts = island.famous_for_list[:2]
    lines = [island.tagline + "." if island.tagline and not island.tagline.endswith(".") else island.tagline]
    if facts:
        lines.append("Known for: " + ", ".join(f[0].lower() + f[1:] for f in facts) + ".")
    if island.transfer_time:
        lines.append(f"Getting there: {island.transfer_time} from Malé.")
    lines.append(f"The {island.name} guide covers local rules, facilities and the guest houses you can message directly.")
    return dict(
        title=f"{island.name} {'story' if story else 'spotlight'}", pillar="islands", template="island", format=fmt,
        island=island, eyebrow=f"{'Island of the week' if story else 'Island spotlight'} · {island.atoll.name}",
        headline=f"Stay on {island.name}", accent_word=island.name, body=island.tagline,
        attribution="Read the island guide", caption=" ".join(l for l in lines if l),
        hashtags=_tags(island.name, island.atoll.name + " Atoll"),
        photo_credit=island.cover_credit,
    )


def experience_post(activity, islands):
    names = [i.name for i in islands[:3]]
    n = len(islands)
    where = (f"{n} island{'s' if n != 1 else ''} on Island Stay" + (f", including {', '.join(names[:-1])} and {names[-1]}" if len(names) > 1 else (f": {names[0]}" if names else "")))
    return dict(
        title=f"{activity.name} experience", pillar="experiences", template="experience", format="portrait",
        activity=activity, island=islands[0] if islands else None, eyebrow="Experience",
        headline=activity.name, accent_word=activity.name.split()[0], body=activity.description,
        attribution=f"{n} island{'s' if n != 1 else ''} to choose from",
        caption=f"{activity.description} Find it on {where}. Each guide lists the local operators you can message directly.",
        hashtags=_tags(activity.name, *names[:2]),
    )


def host_post(listing):
    first = (listing.contact_name or listing.name).split()[0]
    return dict(
        title=f"Host: {listing.name}", pillar="hosts", template="host", format="portrait",
        listing=listing, island=listing.island, eyebrow=f"{'Verified host' if listing.is_verified else 'Local host'} · {listing.island.name}",
        headline=f"Stay with {first} on {listing.island.name}", accent_word=listing.island.name,
        body=listing.short_description, attribution=listing.name,
        caption=f"Meet {listing.name} on {listing.island.name}. {listing.short_description} Send {first} a request through Island Stay: no booking fees, you agree the details directly.",
        hashtags=_tags(listing.island.name, "Guest House" if listing.is_stay else "", listing.island.atoll.name + " Atoll"),
    )


def tip_post(tip, fmt="story"):
    headline, accent, body, caption = tip
    return dict(title=f"Tip: {headline}", pillar="practical", template="tip", format=fmt, eyebrow="Travel tip",
                headline=headline, accent_word=accent, body=body, attribution="Save this for your trip", caption=caption,
                hashtags=_tags("Maldives Travel", "Travel Tips"))


def island_rules_tip(island):
    rules = island.local_rules_list[:4]
    if len(rules) < 3:
        return None
    return dict(title=f"Tip: before you visit {island.name}", pillar="practical", template="tip", format="story",
                island=island, eyebrow=f"Travel tip · {island.name}", headline=f"Before you visit {island.name}",
                accent_word=island.name, body="\n".join(r.rstrip(".") for r in rules), attribution="Full guide: link in bio",
                caption=f"Heading to {island.name}? A few local rules to know before you go. The island guide has the full list, plus facilities and transfers.",
                hashtags=_tags(island.name, "Travel Tips"))


def fact_post(fact):
    headline, accent, body, caption = fact
    return dict(title=f"Did you know: {headline}", pillar="culture", template="fact", format="square", eyebrow="Did you know",
                headline=headline, accent_word=accent, body=body, platforms="instagram,facebook,x", caption=caption,
                hashtags=_tags("Maldives History", "Dhivehi"))


def _at(day, hour):
    return timezone.make_aware(dt.datetime.combine(day, dt.time(hour, 0)))


def generate_plan(start=None, weeks=4):
    """Create draft posts for `weeks` weeks starting on the Monday on/after `start`. Returns the posts created."""
    start = start or timezone.localdate()
    monday = start + dt.timedelta(days=(7 - start.weekday()) % 7)

    islands = list(_least_used(Island.objects.filter(is_published=True).select_related("atoll"), "island")
                   .order_by("n_posts", "-is_featured", "last_post", "name"))
    islands.sort(key=lambda i: (i.n_posts, not i.photo_url, not i.is_featured))
    activities = list(_least_used(ActivityType.objects.all(), "activity"))
    hosts = list(_least_used(Listing.objects.filter(status=Listing.STATUS_APPROVED).select_related("island", "island__atoll"), "listing")
                 .order_by("n_posts", "-is_verified", "-is_featured", "last_post"))
    used_facts = set(SocialPost.objects.filter(template="fact").values_list("headline", flat=True))
    used_tips = set(SocialPost.objects.filter(template="tip").values_list("headline", flat=True))
    facts = itertools.cycle([f for f in FACTS if f[0] not in used_facts] + [f for f in FACTS if f[0] in used_facts])
    tips = itertools.cycle([t for t in TIPS if t[0] not in used_tips] + [t for t in TIPS if t[0] in used_tips])
    island_iter = itertools.cycle(islands) if islands else None
    host_iter = iter(hosts)

    created = []
    for w in range(weeks):
        mon = monday + dt.timedelta(weeks=w)
        plan = []
        if island_iter:
            spotlight = next(island_iter)
            plan.append((_at(mon, 18), island_post(spotlight)))
        rules = island_rules_tip(spotlight) if island_iter and w % 2 else None
        plan.append((_at(mon + dt.timedelta(1), 19), rules or tip_post(next(tips))))
        if activities:
            act = activities[w % len(activities)]
            act_islands = list(Island.objects.filter(is_published=True, activities=act).order_by("-is_featured", "name"))
            plan.append((_at(mon + dt.timedelta(2), 18), experience_post(act, act_islands)))
        plan.append((_at(mon + dt.timedelta(3), 18), fact_post(next(facts))))
        host = next(host_iter, None)
        plan.append((_at(mon + dt.timedelta(4), 17), host_post(host) if host else tip_post(next(tips), fmt="portrait")))
        if island_iter:
            plan.append((_at(mon + dt.timedelta(6), 10), island_post(next(island_iter), fmt="story", story=True)))
        for when, data in plan:
            data.setdefault("platforms", "instagram,facebook")
            if data["template"] == "experience":
                data["platforms"] = "instagram,facebook,tiktok"
            created.append(SocialPost.objects.create(publish_at=when, status=SocialPost.STATUS_DRAFT, link=LINK, **data))
    return created
