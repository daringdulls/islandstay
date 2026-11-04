"""Starter travel guides. They are ordinary Guide rows, so the team can edit or unpublish them in the back office."""
from django.db import migrations

GUIDES = [
    {
        "slug": "local-island-rules",
        "title": "Local island rules: what visitors need to know",
        "category": "rules",
        "featured": True,
        "summary": "Dress code, bikini beaches, alcohol, Friday prayers and Ramadan. The few local customs that make a stay on an inhabited island easy for everyone.",
        "islands": ["maafushi", "ukulhas", "dhigurah"],
        "body": """Local islands are home to Maldivian families, not resorts. Life follows Islamic customs and the law of the country, and most of it is easy to fit into. Here is what makes the biggest difference to your stay.

## Dress code in the village

In the village, the harbour, shops and cafés, cover your shoulders and knees. A light T-shirt and shorts to the knee or a skirt or loose trousers are fine for everyone. Swimwear is for the beach, so bring something to throw on when you walk back.

## Bikini beaches

Many islands have a bikini beach: a stretch of sand set aside for visitors, usually screened from the village. There you can wear normal swimwear and sunbathe. Each island guide on Island Stay shows whether the island has one. Outside it, swim in shorts and a T-shirt.

- Check the island guide for "Bikini beach" before you book
- Respect the signs at each end of the beach
- Take your rubbish with you

## Alcohol

Alcohol is not sold or allowed on local islands, and you cannot bring it into the country. Many guests take a day trip to a resort or a "floating bar" boat if they want a drink. Fresh juices and mocktails are everywhere on the islands.

## Friday prayers and opening hours

Friday is the main day of prayer. Many shops and cafés close for a few hours around midday on Friday, and some businesses also pause briefly at prayer times during the week. Plan excursions and shopping around that.

## Ramadan

During Ramadan, locals fast from dawn to sunset. Guest houses still serve meals to guests, but eat and drink discreetly in public during the day. Evenings are lively, with food and family gatherings after sunset.

## Photos and drones

Ask before photographing people, especially women and children. Flying a drone needs permission, so ask your host first.

## Respect and friendliness

A smile and a greeting go a long way. Public displays of affection are best kept private. Islanders are welcoming, and your host is the best person to ask if you are unsure about anything.""",
        "faqs": """Q: Can I wear a bikini on a local island?
A: Yes, on the island's bikini beach if it has one. In the village and on other beaches, cover shoulders and knees.
Q: Is alcohol available on local islands?
A: No. Alcohol is not sold on local islands. Visitors who want a drink often take a day trip to a resort or a floating bar boat.
Q: Are shops open on Friday?
A: Many close for a few hours around midday on Friday for prayers, then open again in the afternoon.""",
    },
    {
        "slug": "airport-to-local-island",
        "title": "From Velana Airport to your local island",
        "category": "transport",
        "featured": True,
        "summary": "Speedboats, public ferries, domestic flights and seaplanes: how transfers work, how long they take and how to plan your arrival day.",
        "islands": ["maafushi", "thulusdhoo", "dhigurah", "fuvahmulah"],
        "body": """Almost every trip starts at Velana International Airport (MLE) on Hulhulé, next to Malé. From there you reach a local island by boat or by a short flight. Your guest house can arrange the whole transfer, and it is usually the easiest option.

## Speedboat

Shared speedboats leave from the jetty right outside arrivals. Islands in North and South Malé Atoll are often 20 to 60 minutes away, and islands in Ari Atoll around 1 to 2 hours. Boats run on a schedule, so tell your host your flight time and they will book you onto the right one.

## Public ferry

Government ferries connect Malé with many islands. They are much cheaper but slower, run on fixed days and times, and leave from the ferry terminals in Malé rather than the airport. They are good if you are not in a hurry and arrive in daylight.

## Domestic flight

For islands further north or south, such as Fuvahmulah, Hanimaadhoo or Addu, take a domestic flight from Velana. Some islands also link to a nearby domestic airport by a short boat ride. Book early in high season.

## Seaplane

Seaplanes mostly serve resorts and fly only in daylight. They are rarely the best choice for local islands.

## Planning your arrival day

- Late arrivals may miss the last speedboat. Your host can suggest a night in Hulhumalé, next to the airport.
- Bad weather can delay boats. Leave a buffer before your international flight home.
- Have small notes in US dollars or rufiyaa for porters and the ferry.

Every island guide on Island Stay lists the usual transfer time, and the [transport page](/transport/) shows the routes and operators we know about.""",
        "faqs": """Q: How do I get from the airport to a local island?
A: By shared speedboat from the airport jetty, by public ferry from Malé, or by domestic flight for distant atolls. Guest houses usually arrange the transfer for you.
Q: What if my flight lands late at night?
A: Speedboats stop running in the evening. Many travellers stay a night in Hulhumalé, ten minutes from the airport, and continue the next morning.""",
    },
    {
        "slug": "choose-your-first-local-island",
        "title": "How to choose your first local island",
        "category": "islands",
        "featured": False,
        "summary": "Close to Malé or further out, busy or quiet, whale sharks, mantas or surf. A simple way to match an island to the trip you want.",
        "islands": ["maafushi", "dhigurah", "thulusdhoo", "fulidhoo", "dharavandhoo", "ukulhas"],
        "body": """There are dozens of inhabited islands with guest houses, and they feel quite different from one another. Start with three questions.

## 1. How long do you have?

On a short trip, pick an island close to the airport so you do not lose half a day to transfers. Islands in North and South Malé Atoll are usually under an hour away by speedboat. With a week or more, Ari Atoll and beyond open up.

## 2. Lively or quiet?

[Maafushi](/islands/maafushi/) is where guest-house tourism began. It has many places to stay, cafés and excursions. Smaller islands like [Fulidhoo](/islands/fulidhoo/) or [Ukulhas](/islands/ukulhas/) are quieter, with fewer visitors and slower days.

## 3. What do you want to see?

- **Whale sharks:** South Ari, for example [Dhigurah](/islands/dhigurah/), Dhangethi or Fenfushi
- **Manta rays:** Baa Atoll near Hanifaru Bay, for example [Dharavandhoo](/islands/dharavandhoo/), in season
- **Surf:** [Thulusdhoo](/islands/thulusdhoo/), Himmafushi or Huraa in North Malé Atoll
- **Nurse sharks and sandbanks:** Fulidhoo and many islands in Vaavu and Ari

## Check the practical things

Each island guide shows the bikini beach, ATM, health care and mobile data. If you need an ATM or a pharmacy nearby, check before you book.

Not sure yet? [Compare islands side by side](/islands/compare/) or browse [all island guides](/islands/).""",
        "faqs": """Q: Which local island is best for a first visit?
A: For a short first trip, an island close to the airport with plenty of guest houses, such as Maafushi, is easiest. For whale sharks, look at South Ari islands like Dhigurah.
Q: Can I visit more than one island?
A: Yes. Many travellers split their stay between two islands, using speedboats or ferries between them.""",
    },
    {
        "slug": "when-to-visit-the-maldives",
        "title": "When to go: seasons, whale sharks, mantas and surf",
        "category": "planning",
        "featured": False,
        "summary": "The dry and wet monsoons, and the months that matter for whale sharks, manta rays and surf on the local islands.",
        "islands": ["dhigurah", "dharavandhoo", "thulusdhoo", "fuvahmulah"],
        "body": """The Maldives is warm all year, with sea temperatures around the high 20s °C. What changes is the wind, the rain and what you are likely to see in the water.

## The two monsoons

- **Northeast monsoon (roughly December to April):** the drier season, with more sunshine and calmer seas. This is the busiest time for travel.
- **Southwest monsoon (roughly May to November):** more wind and showers, often in short bursts, with sunny spells between. Prices and crowds are usually lower.

## Whale sharks

In South Ari Atoll, whale sharks can be seen year round, and many trips run from islands such as [Dhigurah](/islands/dhigurah/). Sightings are never guaranteed, so go with a local operator who knows the area.

## Manta rays

Manta rays gather in Baa Atoll around Hanifaru Bay mainly during the southwest monsoon, when plankton is rich. [Dharavandhoo](/islands/dharavandhoo/) is the nearest local island. Mantas are seen at cleaning stations in other atolls at other times of year.

## Surf

The main surf season runs through the middle of the year, during the southwest monsoon. North Malé Atoll islands like [Thulusdhoo](/islands/thulusdhoo/) are close to well-known breaks.

## Diving with tiger sharks

[Fuvahmulah](/islands/fuvahmulah/) in the far south is known for tiger shark dives throughout the year, with conditions depending on the weather.

## Festivals and Ramadan

Ramadan moves about 11 days earlier each year. Islands are quieter during the day and lively at night. Eid celebrations after Ramadan are a lovely time to be on a local island.""",
        "faqs": """Q: What is the best month to visit the Maldives?
A: December to April is drier and calmer. May to November has more rain but fewer visitors, and is the season for mantas in Baa Atoll and for surf.
Q: Can I see whale sharks all year?
A: In South Ari Atoll whale sharks can be seen year round, though sightings are never guaranteed.""",
    },
    {
        "slug": "money-sim-wifi-local-islands",
        "title": "Money, SIM cards and Wi-Fi on local islands",
        "category": "money",
        "featured": False,
        "summary": "Rufiyaa or dollars, cards or cash, ATMs, taxes on your bill, and getting online with a local SIM.",
        "islands": ["maafushi", "male", "hulhumale"],
        "body": """A few practical things make life on a local island much smoother.

## Currency

The local currency is the Maldivian rufiyaa (MVR). US dollars are widely accepted by guest houses and excursion operators, and prices for visitors are often quoted in dollars. Small cafés and shops may prefer rufiyaa.

## Cards and cash

Many guest houses take cards, sometimes with a small fee. Cafés, shops and boat crews often want cash. Bring some US dollars in small, clean notes and change some into rufiyaa.

## ATMs

Not every island has an ATM. Each Island Stay island guide shows whether there is one. If yours does not, take out cash at the airport or in Malé before you travel.

## Taxes on your bill

Bills in tourist businesses usually include a goods and services tax, and guest houses add a Green Tax per person per night. Ask your host what is included in the price.

## SIM cards and mobile data

The two mobile networks are Dhiraagu and Ooredoo. Both sell tourist SIM cards at the airport. Coverage is good on inhabited islands, mostly 4G, and some islands now have 5G. The island guides show which.

## Wi-Fi

Most guest houses have Wi-Fi, but speed varies. If you work online, a local SIM with a data bundle is a reliable backup.""",
        "faqs": """Q: Should I bring US dollars or rufiyaa?
A: Bring some US dollars in small notes. They are widely accepted, and you can change some into rufiyaa for small cafés and shops.
Q: Do local islands have ATMs?
A: Some do and some do not. Check the island guide on Island Stay before you travel.""",
    },
]


def seed(apps, schema_editor):
    Guide = apps.get_model("directory", "Guide")
    Island = apps.get_model("directory", "Island")
    for g in GUIDES:
        if Guide.objects.filter(slug=g["slug"]).exists():
            continue
        obj = Guide.objects.create(
            slug=g["slug"], title=g["title"], category=g["category"], summary=g["summary"],
            body=g["body"], faqs=g["faqs"], is_featured=g["featured"],
        )
        obj.islands.set(Island.objects.filter(slug__in=g["islands"]))


class Migration(migrations.Migration):
    dependencies = [("directory", "0018_guides")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
