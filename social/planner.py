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
            if data.get("format") == "story":
                data.setdefault("post_type", "story")
            if data["template"] == "experience":
                data["platforms"] = "instagram,facebook,tiktok"
            created.append(SocialPost.objects.create(publish_at=when, status=SocialPost.STATUS_DRAFT, link=LINK, **data))
    return created


# ---------------------------------------------------------------------------------------------------------------
# Monthly plan: an Instagram grid that alternates photo and colour tiles, a weekly Reel and three Stories a week.
#
#   Mon 18:00  Feed    photo   Island spotlight
#   Tue 12:00  Story           This or that (poll sticker)
#   Tue 19:00  Feed    light   Travel tip / Getting there / When to go
#   Wed 18:00  Reel    photo   Experience or "a day on" an island (cover in story format)
#   Thu 12:00  Story           Travel tip (question sticker)
#   Thu 18:00  Feed    dark    Top list carousel / Did you know / Our story
#   Fri 17:00  Feed    photo   Host spotlight / Stay card / This or that
#   Sat 11:00  Feed    warm    Dhivehi word / Guest quote
#   Sun 10:00  Story           Island of the week (link sticker)
#
# Six grid tiles a week in the order photo, colour, photo, colour, photo, colour: with three columns this always
# gives a checkerboard, so no two photos or two solid colours ever sit side by side.

WORDS = [
    ("Kandu", "ކަނޑު", "A channel through the reef: the way boats come into an atoll, and the gap in our logo."),
    ("Finolhu", "ފިނޮޅު", "A sandbank that comes and goes with the tide. Ask your host about a sandbank picnic."),
    ("Dhoni", "ދޯނި", "The Maldivian boat, traditionally built from coconut palm wood. It still carries almost everything."),
    ("Atholhu", "އަތޮޅު", "A ring of islands around a lagoon. The world borrowed it as 'atoll'."),
    ("Faru", "ފަރު", "A reef. The faru protects the island, feeds it and is where you'll snorkel."),
    ("Raajje", "ރާއްޖެ", "The realm: Maldivians call their country Dhivehi Raajje."),
]

SEASONS = ("The Maldives, month by month", "month",
           "Dec – Apr | Dry season: calm seas, clear water\nMay – Nov | Wet season: surf, quieter islands, lower prices\n"
           "Jun – Nov | Manta rays gather at Hanifaru Bay\nAll year | Whale sharks in South Ari",
           "When to go? December to April is the dry season, with calm seas and the clearest water. May to November brings "
           "surf, fewer visitors and lower prices, and from June the mantas gather at Hanifaru Bay in Baa. Whale sharks stay "
           "in South Ari all year. Save this for planning.")

STORY = ("An atoll, a channel and a cowrie", "cowrie",
         "The ring is an atoll: atholhu, the one Dhivehi word the world borrowed.\nThe gap is the kandu, the channel boats sail through.\n"
         "The cowrie was once money across Asia and Africa. Now it points out to you.",
         "Why a cowrie in a ring? The ring is an atoll, from atholhu, the one Dhivehi word the world borrowed. The gap is the kandu, "
         "the channel boats sail through. And for centuries Maldivian cowries were money across Asia and Africa. Our cowrie points "
         "out through the kandu: the islands open to you, with your money going straight to local hosts.")


def word_post(word):
    latin, thaana, meaning = word
    return dict(title=f"Dhivehi word: {latin}", pillar="culture", template="word", format="portrait",
                eyebrow="Dhivehi word of the week", headline=latin, body=meaning, attribution=thaana,
                caption=f"{latin} ({thaana}). {meaning} Save this one for your trip, and try it on your host.",
                hashtags=_tags("Dhivehi", "Maldives Culture"))


def season_post():
    headline, accent, body, caption = SEASONS
    return dict(title="When to go", pillar="practical", template="season", format="portrait", eyebrow="When to go",
                headline=headline, accent_word=accent, body=body, attribution="Plan with the island guides",
                caption=caption, hashtags=_tags("Maldives Travel", "Whale Sharks", "Manta Rays"))


def brand_post():
    headline, accent, body, caption = STORY
    return dict(title="Our story", pillar="culture", template="brand", format="portrait", eyebrow="Why the cowrie",
                headline=headline, accent_word=accent, body=body, attribution="Local to you.", caption=caption,
                hashtags=_tags("Maldives History", "Cowrie"))


def toplist_post(islands):
    names = [i.name for i in islands[:5]]
    return dict(title="Top five islands", pillar="islands", template="toplist", format="portrait", post_type="carousel",
                island=islands[0] if islands else None, eyebrow="Save this list", headline="Five islands for your first trip",
                accent_word="first", body="\n".join(names), attribution="Swipe for each island",
                caption="Five local islands for a first trip: " + ", ".join(names) + ". Swipe for one reason to go to each, "
                        "then open the island guides to message the hosts.",
                hashtags=_tags(*names[:3]),
                script="Carousel: slide 1 is this cover. Add one slide per island (download the Island spotlight design for each) "
                       "and finish with a slide that says 'Message a local: link in bio'.")


def route_post(island):
    route = island.routes.filter(is_active=True).order_by("order").first()
    steps = ["Arrive | Velana International Airport (MLE)"]
    if route:
        steps.append(f"{route.get_mode_display()} | {route.duration}")
    elif island.transfer_time:
        steps.append(f"Transfer | {island.transfer_time}")
    steps.append(f"Jetty | Your host meets you on {island.name}")
    how = route.get_mode_display().lower() if route else (island.transfer_time or "a transfer")
    return dict(title=f"Getting to {island.name}", pillar="practical", template="route", format="portrait", island=island,
                eyebrow="Getting there", headline=f"Malé to {island.name}", accent_word=island.name, body="\n".join(steps),
                attribution="Transfer times in the island guide",
                caption=f"How to get to {island.name}: land at Velana airport, then {how}. Your host can book the transfer "
                        f"and meet you at the jetty. Times and prices are in the {island.name} guide.",
                hashtags=_tags(island.name, "Maldives Ferry"))


def stay_post(listing):
    price = f" From ${listing.price_from:.0f} / {listing.price_unit}." if listing.price_from else ""
    return dict(title=f"Stay: {listing.name}", pillar="hosts", template="stay", format="portrait", listing=listing,
                island=listing.island, eyebrow=f"Stay · {listing.island.name}, {listing.island.atoll.name}",
                headline=listing.name, body=listing.short_description, attribution="Send a request",
                caption=f"{listing.name} on {listing.island.name}. {listing.short_description}{price} "
                        "Message the host on Island Stay: no booking fees.",
                hashtags=_tags(listing.island.name, "Guest House"))


def compare_post(a, b, fmt="portrait", story=False):
    data = dict(title=f"{a.name} or {b.name}", pillar="islands", template="compare", format=fmt, island=a, island_b=b,
                eyebrow="This or that", headline="Which island would you pick?", accent_word="island",
                attribution="Vote in the poll" if story else "Tell us in the comments",
                caption=f"{a.name} or {b.name}? {a.tagline or ''} {b.tagline or ''} Tell us which one, and why.".replace("  ", " "),
                hashtags=_tags(a.name, b.name))
    if story:
        data.update(post_type="story", platforms="instagram,facebook",
                    script=f"Add a poll sticker over the 'or': {a.name} / {b.name}. Share the results the next day.")
    return data


def quote_post(review):
    return dict(title=f"Review: {review.listing.name}", pillar="hosts", template="quote", format="portrait",
                listing=review.listing, island=review.listing.island, eyebrow="From a guest", headline=review.title or "Guest review",
                body=review.text[:180], attribution=f"{review.name}, {review.listing.island.name}",
                caption=f"From a guest at {review.listing.name} on {review.listing.island.name}: “{review.text[:220]}”",
                hashtags=_tags(review.listing.island.name, "Guest House"))


def hostcall_post(island):
    return dict(title="List with us", pillar="news", template="hostcall", format="portrait", island=island,
                eyebrow="For island hosts", headline="Run a guest house? List it free", accent_word="free",
                body="Guests message you directly\nNo booking fees for you or your guests\nYour island, your photos, your prices",
                attribution="islandstaymv.com/list-your-business", platforms="instagram,facebook",
                caption="Do you run a guest house, dive centre, café or boat on a local island? List it on Island Stay for free. "
                        "Guests message you directly and you agree the details yourselves.",
                hashtags=_tags("Maldives Guest House", "Local Business"))


def experience_reel(activity, islands):
    data = experience_post(activity, islands)
    where = islands[0].name if islands else "a local island"
    data.update(post_type="reel", format="story", platforms="instagram,facebook,tiktok",
                script=f"Length: 15–20 s, vertical. Use a trending sound or boduberu drums.\n"
                       f"0–2 s  Hook on screen: \"{activity.name} from {where}, no resort needed\"\n"
                       f"2–6 s  The boat leaving the jetty\n"
                       f"6–13 s  The best moment of the {activity.name.lower()} (one long shot, no fast cuts)\n"
                       f"13–17 s  Back on the island: food, the guest house, the beach\n"
                       f"17–20 s  End card: this cover design, 'Message a local. Link in bio.'\n"
                       f"Cover: this design. Add captions on screen; most people watch muted.")
    return data


def island_reel(island):
    data = island_post(island, fmt="story", story=True)
    data.update(title=f"A day on {island.name}", post_type="reel", eyebrow=f"A day on {island.name} · {island.atoll.name}",
                headline=f"A day on {island.name}", platforms="instagram,facebook,tiktok",
                script=f"Length: 20–30 s, vertical, 6 clips of 3–4 s. Gentle local music.\n"
                       f"0–2 s  Hook on screen: \"24 hours on {island.name}\"\n"
                       f"Clip 1  Sunrise on the jetty\nClip 2  Breakfast at the guest house\nClip 3  Snorkel or sandbank trip\n"
                       f"Clip 4  The village: the mosque, the school, kids on bikes (ask before filming people)\n"
                       f"Clip 5  Sunset on the bikini beach\nClip 6  Dinner, then this cover as the end card\n"
                       f"On screen at the end: 'Stay where the island lives. Link in bio.'")
    return data


def as_story(data, script):
    data.update(post_type="story", format="story", platforms="instagram,facebook", script=script)
    return data


def generate_month(year, month):
    """Draft a full month for Instagram: 6 grid tiles and 3 stories a week. Returns the posts created."""
    first = dt.date(year, month, 1)
    days = [first + dt.timedelta(n) for n in range(31) if (first + dt.timedelta(n)).month == month]
    islands = list(_least_used(Island.objects.filter(is_published=True).select_related("atoll"), "island")
                   .order_by("n_posts", "-is_featured", "last_post", "name"))
    islands.sort(key=lambda i: (i.n_posts, not i.photo_url, not i.is_featured))
    if not islands:
        return []
    activities = list(_least_used(ActivityType.objects.all(), "activity"))
    hosts = list(_least_used(Listing.objects.filter(status=Listing.STATUS_APPROVED).select_related("island", "island__atoll"), "listing")
                 .order_by("n_posts", "-is_verified", "-is_featured", "last_post"))
    stays = [h for h in hosts if h.is_stay]
    from directory.models import Review
    used_reviews = set(SocialPost.objects.filter(template="quote").values_list("listing_id", "body"))
    reviews = [r for r in Review.objects.filter(status="published", rating__gte=4).select_related("listing", "listing__island")
               if (r.listing_id, r.text[:180]) not in used_reviews]
    used_words = set(SocialPost.objects.filter(template="word").values_list("headline", flat=True))
    words = itertools.cycle([w for w in WORDS if w[0] not in used_words] + [w for w in WORDS if w[0] in used_words])
    used_facts = set(SocialPost.objects.filter(template="fact").values_list("headline", flat=True))
    facts = itertools.cycle([f for f in FACTS if f[0] not in used_facts] + [f for f in FACTS if f[0] in used_facts])
    used_tips = set(SocialPost.objects.filter(template="tip").values_list("headline", flat=True))
    tips = itertools.cycle([t for t in TIPS if t[0] not in used_tips] + [t for t in TIPS if t[0] in used_tips])
    has_story = SocialPost.objects.filter(template="brand").exists()
    isl = itertools.cycle(islands)
    host_iter, stay_iter, review_iter = iter(hosts), iter(stays), iter(reviews)

    def pair():
        a = next(isl)
        same = [i for i in islands if i.atoll_id == a.atoll_id and i.pk != a.pk]
        return a, (same[0] if same else next(isl))

    plan = []
    for day in days:
        w, wd = (day.day - 1) // 7, day.weekday()
        if wd == 0:
            plan.append((_at(day, 18), island_post(next(isl))))
        elif wd == 1:
            a, b = pair()
            plan.append((_at(day, 12), compare_post(a, b, fmt="story", story=True)))
            light = [lambda: tip_post(next(tips), fmt="portrait"), lambda: route_post(next(isl)),
                     lambda: island_rules_tip(next(isl)) or tip_post(next(tips), fmt="portrait"), season_post]
            data = light[w % 4]()
            data["format"] = "portrait"
            plan.append((_at(day, 19), data))
        elif wd == 2:
            if w % 2 == 0 and activities:
                act = activities[(w // 2) % len(activities)]
                act_islands = list(Island.objects.filter(is_published=True, activities=act).order_by("-is_featured", "name"))
                plan.append((_at(day, 18), experience_reel(act, act_islands)))
            else:
                plan.append((_at(day, 18), island_reel(next(isl))))
        elif wd == 3:
            tip = tip_post(next(tips), fmt="story")
            plan.append((_at(day, 12), as_story(tip, "Add a question sticker: 'Ask us anything about local islands'. "
                                                     "Answer the best questions in next week's stories.")))
            if w == 0:
                data = toplist_post(islands[:5])
            elif w == 2 and not has_story:
                data = brand_post()
            else:
                data = fact_post(next(facts))
                data.update(format="portrait")
            plan.append((_at(day, 18), data))
        elif wd == 4:
            choice = w % 4
            data = None
            if choice in (0, 3):
                h = next(host_iter, None)
                data = host_post(h) if h else None
            elif choice == 1:
                h = next(stay_iter, None)
                data = stay_post(h) if h else None
            if data is None and choice == 3:
                data = hostcall_post(next(isl))
            if data is None:
                data = compare_post(*pair())
            plan.append((_at(day, 17), data))
        elif wd == 5:
            r = next(review_iter, None) if w % 2 else None
            plan.append((_at(day, 11), quote_post(r) if r else word_post(next(words))))
        elif wd == 6:
            data = island_post(next(isl), fmt="story", story=True)
            plan.append((_at(day, 10), as_story(data, "Add a link sticker to the island guide and a 'Message a local' text.")))

    created = []
    for when, data in plan:
        data.setdefault("platforms", "instagram,facebook")
        data.setdefault("post_type", "feed")
        created.append(SocialPost.objects.create(publish_at=when, status=SocialPost.STATUS_DRAFT, link=LINK, **data))
    return created
