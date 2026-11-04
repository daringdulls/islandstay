"""Starter outlines for the guide editor. Editable in the back office under Guide templates."""
from django.db import migrations

TEMPLATES = [
    {
        "name": "Island guide: things to do", "icon": "map", "category": "islands",
        "description": "A full guide to one island. Good for Google searches like “things to do in Maafushi”.",
        "title": "Things to do on [Island]: a local island guide",
        "summary": "What to see and do on [Island] in [Atoll]: beaches, reefs, trips and island life, with tips from local hosts.",
        "body": """[Island] is a [small / busy / quiet] local island in [Atoll], about [time] from Velana Airport. [One or two sentences on what makes it special.]

## Why visit [Island]

[Two or three sentences: who will love it, and what it is known for.]

- [Highlight one]
- [Highlight two]
- [Highlight three]

## Beaches and the bikini beach

[Describe the bikini beach: where it is, how long, shade, swimming conditions.]

## Snorkelling and diving

[House reef, best snorkel spots, dive sites nearby, what you might see.]

## Excursions from [Island]

- **[Trip name]:** [What it is, how long it takes, when to go]
- **[Trip name]:** [What it is, how long it takes, when to go]
- **[Trip name]:** [What it is, how long it takes, when to go]

## Island life

[Village walk, mosque, school, football field, evening life, local food to try.]

## Where to stay

[Type of places: guest houses, small hotels. Link to the stays page:] [Where to stay on Island](/islands/[island-slug]/where-to-stay/)

## Getting there

[Speedboat and ferry times.] Full details: [How to get to Island](/islands/[island-slug]/getting-there/)

## Good to know

- [ATM or not]
- [Health centre or hospital]
- [Mobile data]
- [Local rules worth knowing]""",
        "faqs": """Q: Is [Island] good for a first visit to the Maldives?
A: [Answer in one or two sentences.]
Q: Does [Island] have a bikini beach?
A: [Yes / No, and where it is.]
Q: How many days do I need on [Island]?
A: [Answer.]""",
    },
    {
        "name": "Getting there", "icon": "directions_boat", "category": "transport",
        "description": "How to reach one island or area. Answers “how to get to …” searches.",
        "title": "How to get to [Island] from Malé airport",
        "summary": "Speedboat, ferry and flight options to [Island], with travel times, schedules and tips for your arrival day.",
        "body": """[Island] is about [distance] km from Velana International Airport. Most visitors arrive by [speedboat / domestic flight] in about [time].

## By speedboat

[Who runs it, where it leaves from, how long it takes, how often, how to book.]

## By public ferry

[Days, times, where it leaves from in Malé, how long it takes. Say if there is no ferry.]

## By domestic flight

[Only if relevant: nearest airport and the boat transfer from there.]

## Arriving late at night

[What to do if you land after the last boat.]

## Tips

- [Tip one]
- [Tip two]
- [Tip three]""",
        "faqs": """Q: How long does it take to get to [Island] from the airport?
A: [Answer.]
Q: Is there a public ferry to [Island]?
A: [Answer.]""",
    },
    {
        "name": "Activity guide", "icon": "scuba_diving", "category": "activities",
        "description": "One activity across the islands: whale sharks, mantas, surf, diving…",
        "title": "[Activity] in the Maldives: where to go and what to expect",
        "summary": "Where to go for [activity] from the local islands, the best season, what a trip costs and how to choose a good operator.",
        "body": """[One or two sentences: why the Maldives is great for this activity.]

## Where to go

- **[Island or atoll]:** [Why it is good here]
- **[Island or atoll]:** [Why it is good here]
- **[Island or atoll]:** [Why it is good here]

## Best time of year

[Season, conditions, months to avoid.]

## What a trip is like

[How long, what happens, what to bring, who it suits.]

## Choosing an operator

- [Licensed and insured]
- [Group size]
- [Respect for marine life: distance, no touching]

## Respect the wildlife

[Short code of conduct.]

Find operators: [Activity on the local islands](/experiences/[activity-slug]/)""",
        "faqs": """Q: When is the best time for [activity] in the Maldives?
A: [Answer.]
Q: Can beginners do [activity]?
A: [Answer.]""",
    },
    {
        "name": "Island comparison", "icon": "compare", "category": "islands",
        "description": "Two or three islands side by side. Answers “Maafushi or Dhigurah?” searches.",
        "title": "[Island A] or [Island B]: which local island suits you?",
        "summary": "[Island A] and [Island B] compared: getting there, beaches, things to do, places to stay and who each island suits best.",
        "body": """Both [Island A] and [Island B] are popular local islands, but they suit different trips. Here is how they compare.

## At a glance

- **Getting there:** [Island A: time] · [Island B: time]
- **Feel:** [Island A: busy / quiet] · [Island B: busy / quiet]
- **Best for:** [Island A: who] · [Island B: who]

## Beaches

[Compare the bikini beaches and swimming.]

## Things to do

[Compare excursions and marine life.]

## Places to stay and eat

[Compare choice and style.]

## Our pick

- Choose **[Island A]** if [reason].
- Choose **[Island B]** if [reason].

See them side by side: [Compare the islands](/islands/compare/?i=[island-a-slug],[island-b-slug])""",
        "faqs": """Q: Which is better, [Island A] or [Island B]?
A: [Answer: it depends on…]
Q: Can I visit both on one trip?
A: [Answer.]""",
    },
    {
        "name": "Month or season guide", "icon": "calendar_month", "category": "planning",
        "description": "Weather and what's on in a month or season. Answers “Maldives in March” searches.",
        "title": "The Maldives in [Month]: weather, marine life and what's on",
        "summary": "What the weather is like in [Month], what you can see in the water, events and holidays, and the best islands to visit.",
        "body": """[Month] falls in the [dry northeast / wet southwest] monsoon. [One sentence on what to expect.]

## Weather

[Sun, rain, wind, sea conditions, temperature.]

## In the water

[Visibility, whale sharks, mantas, turtles, surf.]

## Holidays and events

[Ramadan, Eid, Independence Day, school holidays, anything that changes opening hours.]

## Best islands in [Month]

- **[Island]:** [Why]
- **[Island]:** [Why]

## Packing tips

- [Tip]
- [Tip]""",
        "faqs": """Q: Is [Month] a good time to visit the Maldives?
A: [Answer.]
Q: Does it rain a lot in [Month]?
A: [Answer.]""",
    },
    {
        "name": "Practical tips", "icon": "tips_and_updates", "category": "money",
        "description": "Answers one practical question: money, SIM cards, visas, packing, safety…",
        "title": "[Topic]: what visitors need to know",
        "summary": "Clear, practical answers about [topic] for visitors staying on the local islands of the Maldives.",
        "body": """[Short intro: why this matters for a trip to a local island.]

## The short answer

[Two or three sentences that answer the main question.]

## [Detail one]

[Explain.]

## [Detail two]

[Explain.]

## [Detail three]

[Explain.]

## Checklist

- [Thing to do or bring]
- [Thing to do or bring]
- [Thing to do or bring]""",
        "faqs": """Q: [Common question]
A: [Answer.]
Q: [Common question]
A: [Answer.]""",
    },
    {
        "name": "Top picks list", "icon": "format_list_numbered", "category": "activities",
        "description": "A list article, like “7 best islands for snorkelling”. Shares well on social media.",
        "title": "[Number] best [things] on the local islands",
        "summary": "Our pick of the [number] best [things] on the local islands of the Maldives, and how to visit each one.",
        "body": """[One or two sentences: how you chose the list.]

## 1. [Name]

[Why it made the list, where it is, how to visit.] [Read more](/islands/[slug]/)

## 2. [Name]

[Why it made the list, where it is, how to visit.]

## 3. [Name]

[Why it made the list, where it is, how to visit.]

## 4. [Name]

[Why it made the list, where it is, how to visit.]

## 5. [Name]

[Why it made the list, where it is, how to visit.]

## How to plan your trip

[One paragraph with links to stays and transport.]""",
        "faqs": "",
    },
    {
        "name": "Itinerary", "icon": "route", "category": "planning",
        "description": "A day-by-day plan for one island or a two-island trip.",
        "title": "[Number] days on [Island]: a simple itinerary",
        "summary": "A day-by-day plan for [number] days on [Island]: what to do each day, when to book trips and where to eat.",
        "body": """[Who this itinerary is for, and when to go.]

## Day 1: Arrival

[Transfer, check in, first swim, sunset spot, dinner.]

## Day 2: [Theme]

- **Morning:** [Activity]
- **Afternoon:** [Activity]
- **Evening:** [Activity]

## Day 3: [Theme]

- **Morning:** [Activity]
- **Afternoon:** [Activity]
- **Evening:** [Activity]

## Day 4: Departure

[Last swim, transfer timing, tips for the flight home.]

## Booking tips

- [Book this trip in advance]
- [Bring cash for this]""",
        "faqs": """Q: How many days do I need on [Island]?
A: [Answer.]""",
    },
]


def seed(apps, schema_editor):
    T = apps.get_model("directory", "GuideTemplate")
    for n, t in enumerate(TEMPLATES):
        if not T.objects.filter(name=t["name"]).exists():
            T.objects.create(order=n, **t)


class Migration(migrations.Migration):
    dependencies = [("directory", "0020_guide_templates")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
