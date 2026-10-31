"""Seed atolls, activity types, amenities, local islands and (optionally) demo listings.

    python manage.py seed_maldives            # reference data + islands
    python manage.py seed_maldives --demo     # also create a demo owner, demo listings and enquiries

Island facts are a starting point written for travellers; transfer times are approximate.
Review and refine them in the admin before launch.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Profile
from directory import geo
from directory.models import ActivityType, Amenity, Atoll, Enquiry, Island, Listing, RoomType, TransportRoute

ATOLLS = [
    # (common name, administrative name, code, region, description)
    ("Haa Alif", "Haa Alif", "HA", "north", "The northernmost atoll, home to Ihavandhoo and historic Utheemu, birthplace of national hero Sultan Mohamed Thakurufaanu."),
    ("Haa Dhaalu", "Haa Dhaalu", "HDh", "north", "Gateway to the far north via Hanimaadhoo airport, with long untouched beaches and a slower pace of life."),
    ("Shaviyani", "Shaviyani", "Sh", "north", "Quiet northern atoll with traditional fishing communities."),
    ("Noonu", "Noonu", "N", "north", "Northern atoll known for luxury resorts and unspoilt reefs."),
    ("Raa", "Raa", "R", "north", "Large atoll famed for boat-building heritage and rich fishing grounds."),
    ("Baa", "Baa", "B", "north", "A UNESCO Biosphere Reserve and home of Hanifaru Bay, the world's largest manta ray feeding aggregation."),
    ("Lhaviyani", "Lhaviyani", "Lh", "north", "Known for shipwreck dives such as the Kuda Giri and a lively local island scene."),
    ("North Malé", "Kaafu", "K", "central", "The capital's atoll: the capital Malé, the airport, and easy-to-reach local islands famous for surf breaks."),
    ("South Malé", "Kaafu", "K", "central", "Closest guest-house islands to the airport, including Maafushi — where local island tourism began in 2010."),
    ("North Ari", "Alif Alif", "AA", "central", "Hammerhead and manta dives, picture-perfect sandbanks and laid-back local islands."),
    ("South Ari", "Alif Dhaal", "ADh", "central", "The year-round whale shark capital of the Maldives, along the South Ari Marine Protected Area."),
    ("Vaavu", "Vaavu", "V", "central", "Sparsely populated atoll with legendary channel dives and nurse-shark-filled lagoons."),
    ("Meemu", "Meemu", "M", "central", "Untouched reefs and quiet villages, a short domestic flight from Malé."),
    ("Faafu", "Faafu", "F", "central", "A small atoll with just a handful of inhabited islands and peaceful lagoons."),
    ("Dhaalu", "Dhaalu", "Dh", "central", "Traditional crafts — lacquerware and jewellery — and beautiful reefs."),
    ("Thaa", "Thaa", "Th", "south", "Remote atoll with some of the country's best uncrowded surf."),
    ("Laamu", "Laamu", "L", "south", "Home to Gan (Laamu), the largest island in the Maldives, and ancient Buddhist ruins."),
    ("Huvadhoo North", "Gaafu Alif", "GA", "south", "Part of Huvadhoo, one of the largest natural atolls in the world. Pristine and remote."),
    ("Huvadhoo South", "Gaafu Dhaalu", "GDh", "south", "Southern half of Huvadhoo with long surf breaks and quiet villages."),
    ("Fuvahmulah", "Gnaviyani", "Gn", "south", "A single-island atoll with freshwater lakes, pebble beaches and world-famous tiger shark dives."),
    ("Addu", "Seenu", "S", "south", "The southernmost atoll, with islands linked by causeways, WWII history and the British Loyalty wreck."),
]

ACTIVITIES = [
    ("Snorkeling", "fish", "House reefs and boat snorkeling trips"),
    ("Scuba diving", "anchor", "Fun dives, PADI courses and channel dives"),
    ("Sandbank picnic", "sun", "Half-day trips to a sandbank in the middle of the lagoon"),
    ("Dolphin cruise", "waves", "Sunset boat rides to spot spinner dolphins"),
    ("Sunset & night fishing", "sunset", "Traditional handline fishing, often with a BBQ of your catch"),
    ("Whale shark excursion", "fish-symbol", "Snorkel with whale sharks along the South Ari MPA"),
    ("Manta ray snorkeling", "waves", "Swim with manta rays at cleaning and feeding stations"),
    ("Nurse sharks & stingrays", "fish", "Watch nurse sharks and rays in shallow water"),
    ("Turtle snorkeling", "turtle", "Snorkel with green and hawksbill turtles"),
    ("Surfing", "waves", "Reef breaks for all levels, best March–October"),
    ("Kayaking & SUP", "sailboat", "Paddle around the lagoon or through mangroves"),
    ("Resort day trip", "tree-palm", "Enjoy a resort's facilities for the day"),
    ("Island hopping", "compass", "Visit neighbouring local and uninhabited islands"),
    ("Local culture & village walk", "landmark", "Mosques, Bodu Beru drumming and island life"),
    ("Hammerhead dive", "anchor", "Early-morning dives to see scalloped hammerheads"),
    ("Tiger shark dive", "anchor", "Advanced dives with tiger sharks"),
    ("Big game fishing", "ship-wheel", "Deep-sea trolling for tuna, wahoo and sailfish"),
    ("Water sports", "life-buoy", "Jet ski, banana boat, parasailing and tubing"),
    ("Spa & wellness", "flower-2", "Massage, yoga and wellness"),
    ("Freediving", "droplets", "Courses and guided freediving sessions"),
    ("Wreck diving", "ship", "Dive historic shipwrecks"),
    ("Bioluminescence", "sparkles", "Spot glowing plankton on the shore at night (seasonal)"),
]

# Wikimedia Commons searches used by fetch_island_photos to illustrate each experience.
PHOTO_SEARCH = {
    "Snorkeling": "snorkeling coral reef Maldives",
    "Scuba diving": "scuba diver Maldives reef",
    "Sandbank picnic": "sandbank Maldives",
    "Dolphin cruise": "spinner dolphins Maldives",
    "Sunset & night fishing": "dhoni sunset Maldives",
    "Whale shark excursion": "whale shark Maldives",
    "Manta ray snorkeling": "manta ray Maldives",
    "Nurse sharks & stingrays": "nurse shark Maldives",
    "Turtle snorkeling": "green sea turtle Maldives",
    "Surfing": "surfing Maldives",
    "Kayaking & SUP": "kayak lagoon Maldives",
    "Resort day trip": "water villa Maldives",
    "Island hopping": "dhoni boat Maldives",
    "Local culture & village walk": "Hukuru Miskiy Male",
    "Hammerhead dive": "scalloped hammerhead shark",
    "Tiger shark dive": "tiger shark Fuvahmulah",
    "Big game fishing": "yellowfin tuna fishing Maldives",
    "Water sports": "jet ski Maldives",
    "Spa & wellness": "spa Maldives",
    "Freediving": "freediving Maldives",
    "Wreck diving": "shipwreck Maldives diving",
    "Bioluminescence": "bioluminescent plankton Maldives",
}

AMENITIES = [
    ("Free WiFi", "wifi"), ("Air conditioning", "snowflake"), ("Breakfast included", "egg-fried"), ("Restaurant", "utensils"),
    ("Airport transfer arranged", "plane-landing"), ("Hot water", "shower-head"), ("Sea view", "sunset"), ("Beach access", "umbrella"),
    ("Rooftop terrace", "sun"), ("Excursion desk", "map"), ("Snorkel gear", "fish"), ("Laundry", "shirt"),
    ("Family rooms", "users"), ("Bicycle rental", "bike"), ("Dive centre on site", "anchor"), ("Halal food", "soup"),
    ("Swimming pool", "droplets"), ("24h reception", "concierge-bell"), ("Private bathroom", "bath"), ("Kayak / SUP", "sailboat"),
]

STD_RULES = [
    "Dress modestly in the village: cover shoulders and knees (men and women).",
    "Bikinis and swimwear only on the designated bikini beach, on excursions and on resort day trips.",
    "Alcohol and pork are not permitted on local islands — don't bring them in your luggage.",
    "Public displays of affection are frowned upon; be respectful near mosques and during prayer times.",
    "Flying drones requires a permit from the Maldives Civil Aviation Authority.",
    "Don't touch or stand on coral, and never take shells, sand or coral off the island.",
]
STD_EXPECT = [
    "A quiet village pace — most places are within a few minutes' walk.",
    "Cash (USD or MVR) is widely used; larger guest houses and shops accept cards.",
    "Friday is the weekly day of rest: shops close around midday prayers and ferries run less.",
    "Guest houses usually arrange excursions and transfers for you.",
]
STD_ACCESS = [
    "Roads are mostly flat, compacted sand; there are few paved paths or kerbs.",
    "Wheelchair access is limited — ask your host about step-free rooms before booking.",
    "Boarding speedboats and ferries involves steps from the jetty; crews will help.",
    "No taxis on most small islands: buggies or bicycles may be available on request.",
]

ISLANDS = [
    dict(name="Malé", atoll="North Malé", island_type="capital", color="#1f4e79",
         tagline="The compact, colourful capital of the Maldives",
         overview="One of the most densely populated cities in the world, Malé packs mosques, markets, cafés and government buildings into barely two square kilometres. Most travellers pass through, but half a day here is the best way to see everyday Maldivian life.",
         famous_for="Hukuru Miskiy — the 17th-century coral stone Old Friday Mosque\nThe bustling local fish and produce markets\nSultan Park and the National Museum\nArtificial Beach and the lively waterfront",
         expect="A busy, urban island with scooters everywhere — not a beach destination\nGreat budget base for an early ferry or flight\nModest dress throughout the city\nNo alcohol outside the airport-island hotels",
         getting_there="Connected to Velana International Airport by the Sinamalé Bridge (Hulhulé) — about 15 minutes by taxi or bus.",
         best="All year", transfers="road,ferry", km=2, time="≈15 min by taxi from the airport",
         pop=210000, bikini=False, atm=True, hosp=True, activities=["Local culture & village walk", "Island hopping", "Big game fishing"]),
    dict(name="Hulhumalé", atoll="North Malé", island_type="capital", color="#2e7d9a",
         tagline="Modern reclaimed city island next to the airport",
         overview="Hulhumalé is a planned city built on reclaimed land a few minutes from the airport. Wide streets, a long public beach and plenty of cafés make it a popular first or last night in the Maldives.",
         famous_for="Long public beach with a beachfront promenade of cafés\nMinutes from Velana International Airport\nCentral Park and its relaxed, modern feel",
         expect="Perfect for transit nights before or after a flight\nModest dress on the public beach — there is no bikini beach\nPlenty of supermarkets, ATMs and restaurants",
         getting_there="10 minutes by taxi or public bus from Velana International Airport.",
         best="All year", transfers="road", km=6, time="≈10 min by road", pop=60000,
         bikini=False, atm=True, hosp=True, activities=["Snorkeling", "Water sports", "Dolphin cruise", "Resort day trip"]),
    dict(name="Maafushi", atoll="South Malé", featured=True, color="#0e7c86",
         tagline="Where Maldives guest-house tourism began",
         overview="Maafushi opened the country's first guest houses in 2010 and is now the most developed local island for independent travellers, with dozens of guest houses, a bikini beach and every kind of excursion on offer.",
         famous_for="The first local island to welcome guest-house tourism (2010)\nBikini beach with turquoise water\nHuge choice of excursions: sandbanks, dolphins, resort day trips\nFloating bars on boats moored offshore",
         expect=None, getting_there="Shared speedboats from Malé/airport several times a day (≈30–45 min), or the cheaper public ferry from Malé (≈1.5 hrs, not on Fridays).",
         best="December–April for dry, sunny weather; good value May–November",
         transfers="speedboat,ferry", km=27, time="≈30–45 min by speedboat", pop=3000, bikini=True, atm=True, hosp=True,
         activities=["Snorkeling", "Scuba diving", "Sandbank picnic", "Dolphin cruise", "Sunset & night fishing", "Turtle snorkeling",
                     "Resort day trip", "Water sports", "Island hopping", "Nurse sharks & stingrays"]),
    dict(name="Guraidhoo", atoll="South Malé", color="#13856f",
         tagline="Surf, reefs and a friendly village vibe",
         overview="A short hop from Maafushi, Guraidhoo is quieter but well connected, with good surf nearby, a calm lagoon and easy access to resort day trips.",
         famous_for="Nearby reef breaks for surfers\nA bikini beach on a calm lagoon\nEasy resort day trips",
         expect=None, getting_there="Shared speedboat from the airport (≈40 min) or public ferry from Malé.",
         best="March–October for surf, December–April for sunshine", transfers="speedboat,ferry", km=30, time="≈40 min by speedboat",
         pop=1800, bikini=True, atm=False, hosp=True, activities=["Surfing", "Snorkeling", "Scuba diving", "Resort day trip", "Sandbank picnic"]),
    dict(name="Gulhi", atoll="South Malé", color="#2a9d8f",
         tagline="A tiny, peaceful island close to the airport",
         overview="Gulhi is small enough to walk around in minutes, with a sweet bikini beach and a relaxed atmosphere — a calm alternative to busier Maafushi next door.",
         famous_for="Quiet, small-island feel\nPretty bikini beach\nTraditional boatyard",
         expect=None, getting_there="Shared speedboat from the airport (≈35 min) or public ferry from Malé.",
         best="December–April", transfers="speedboat,ferry", km=24, time="≈35 min by speedboat", pop=1000, bikini=True,
         activities=["Snorkeling", "Sandbank picnic", "Sunset & night fishing", "Resort day trip", "Kayaking & SUP"]),
    dict(name="Huraa", atoll="North Malé", featured=True, color="#228b7a",
         tagline="Mangroves, turtles and surf breaks",
         overview="Huraa has a protected inner mangrove lagoon and easy access to some of North Malé Atoll's famous surf breaks, plus regular turtle and dolphin trips.",
         famous_for="Mangrove lagoon in the island's centre\nSea turtle snorkeling\nAccess to North Malé surf breaks",
         expect=None, getting_there="Shared speedboat from the airport (≈30–40 min).",
         best="March–October for surf; December–April for calm seas", transfers="speedboat,ferry", km=18, time="≈30–40 min by speedboat",
         pop=1000, bikini=True, activities=["Surfing", "Turtle snorkeling", "Kayaking & SUP", "Dolphin cruise", "Snorkeling", "Scuba diving"]),
    dict(name="Thulusdhoo", atoll="North Malé", color="#156b8a",
         tagline="Surf capital of North Malé Atoll",
         overview="Thulusdhoo is the administrative capital of Kaafu Atoll and a magnet for surfers thanks to the famous 'Cokes' and 'Chickens' breaks right off the island.",
         famous_for="'Cokes' and 'Chickens' world-class surf breaks\nCoca-Cola bottling plant using desalinated seawater\nLaid-back surf-town atmosphere",
         expect=None, getting_there="Shared speedboat from the airport (≈30 min) or public ferry from Malé.",
         best="March–October (surf season)", transfers="speedboat,ferry", km=27, time="≈30 min by speedboat", pop=1500,
         bikini=True, atm=True, hosp=True, activities=["Surfing", "Snorkeling", "Sandbank picnic", "Dolphin cruise"]),
    dict(name="Himmafushi", atoll="North Malé", color="#1d6f8f",
         tagline="Jailbreaks surf and handicraft shops",
         overview="Close to the airport, Himmafushi is known for the 'Jailbreaks' surf break and its row of souvenir and handicraft shops.",
         famous_for="'Jailbreaks' surf break\nSouvenir and handicraft shops\nShort transfer time from the airport",
         expect=None, getting_there="Speedboat from the airport (≈20 min) or ferry from Malé.",
         best="March–October", transfers="speedboat,ferry", km=13, time="≈20 min by speedboat", pop=1100,
         activities=["Surfing", "Snorkeling", "Island hopping"]),
    dict(name="Dhiffushi", atoll="North Malé", color="#24869a",
         tagline="Long white beaches on the edge of the atoll",
         overview="One of the larger islands of North Malé Atoll, Dhiffushi has a long sandy beach, surf at 'Kates' and a strong community feel.",
         famous_for="Long white-sand beaches\n'Kates' surf break\nSnorkeling and sandbank trips",
         expect=None, getting_there="Speedboat from the airport (≈45 min) or ferry from Malé.",
         best="December–April", transfers="speedboat,ferry", km=37, time="≈45 min by speedboat", pop=1100, bikini=True,
         activities=["Surfing", "Snorkeling", "Sandbank picnic", "Sunset & night fishing"]),
    dict(name="Fulidhoo", atoll="Vaavu", featured=True, color="#0b6e99",
         tagline="Nurse sharks at the jetty and Bodu Beru drums at night",
         overview="Tiny, charming Fulidhoo is a traveller favourite: nurse sharks and stingrays gather by the harbour, the beaches are lovely and the islanders are renowned Bodu Beru drummers.",
         famous_for="Nurse sharks and stingrays in the harbour\nBodu Beru traditional drumming performances\nAccess to famous Vaavu channel dives",
         expect=None, getting_there="Shared speedboat from the airport (≈1 hr) or public ferry from Malé (≈3.5 hrs, a few days a week).",
         best="December–April", transfers="speedboat,ferry", km=50, time="≈1 hr by speedboat", pop=300, bikini=True,
         activities=["Nurse sharks & stingrays", "Snorkeling", "Scuba diving", "Local culture & village walk", "Sandbank picnic", "Dolphin cruise"]),
    dict(name="Rasdhoo", atoll="North Ari", featured=True, color="#105e8b",
         tagline="Dawn hammerhead dives on the atoll edge",
         overview="Rasdhoo sits on its own little atoll at the north-east corner of Ari. It is a diver's island, famous for early-morning hammerhead dives, plus a big bikini beach and easy reef snorkeling.",
         famous_for="Hammerhead shark dives at Rasdhoo Madivaru\nManta rays and reef sharks\nBikini beach facing the lagoon",
         expect=None, getting_there="Shared speedboat from the airport (≈1 hr–1 hr 15 min).",
         best="December–April for visibility", transfers="speedboat,ferry", km=58, time="≈1 hr by speedboat", pop=1100, bikini=True, hosp=True,
         activities=["Hammerhead dive", "Scuba diving", "Snorkeling", "Manta ray snorkeling", "Sandbank picnic", "Turtle snorkeling"]),
    dict(name="Ukulhas", atoll="North Ari", featured=True, color="#0f7c9a",
         tagline="Eco-island with one of the longest bikini beaches",
         overview="Ukulhas is known as one of the cleanest local islands, with a strong waste-management programme and a long, beautiful bikini beach. Manta trips and sandbanks are close by.",
         famous_for="Award-winning cleanliness and recycling programme\nLong white bikini beach\nManta ray and turtle trips nearby",
         expect=None, getting_there="Shared speedboat from the airport (≈1 hr 15 min).",
         best="December–April", transfers="speedboat", km=72, time="≈1 hr 15 min by speedboat", pop=1000, bikini=True,
         activities=["Manta ray snorkeling", "Snorkeling", "Scuba diving", "Turtle snorkeling", "Sandbank picnic", "Bioluminescence"]),
    dict(name="Mathiveri", atoll="North Ari", color="#1b7f8c",
         tagline="Sandbanks, mantas and a quiet bikini beach",
         overview="A small island in North Ari, Mathiveri is surrounded by sandbanks and reefs and is a relaxed base for manta and turtle trips.",
         famous_for="Nearby sandbanks\nManta ray points\nPeaceful bikini beach",
         expect=None, getting_there="Shared speedboat from the airport (≈1 hr 30 min).",
         best="December–April", transfers="speedboat", km=80, time="≈1 hr 30 min by speedboat", pop=800, bikini=True,
         activities=["Manta ray snorkeling", "Sandbank picnic", "Snorkeling", "Scuba diving"]),
    dict(name="Thoddoo", atoll="North Ari", featured=True, color="#3a8f4f",
         tagline="The fruit basket of the Maldives",
         overview="Thoddoo is an agricultural island famous for its watermelons, papayas and bananas — you'll see farms right next to the guest houses. It also has ancient Buddhist ruins and a sweeping bikini beach.",
         famous_for="Farms growing watermelon, papaya and bananas\nAncient Buddhist temple ruins\nOne of the country's best house reefs off the bikini beach",
         expect=None, getting_there="Shared speedboat from the airport (≈1 hr 15 min).",
         best="December–April; watermelon season is the dry season", transfers="speedboat,ferry", km=67, time="≈1 hr 15 min by speedboat",
         pop=1500, bikini=True, atm=True, hosp=True,
         activities=["Snorkeling", "Turtle snorkeling", "Local culture & village walk", "Scuba diving", "Bioluminescence", "Kayaking & SUP"]),
    dict(name="Dhigurah", atoll="South Ari", featured=True, color="#0a7ea4",
         tagline="Whale sharks and a 3 km sandbank tail",
         overview="Long, thin Dhigurah sits right on the South Ari Marine Protected Area, the best place in the country to swim with whale sharks year-round. Its sandbank tail stretches out into the lagoon.",
         famous_for="Year-round whale shark sightings in the South Ari MPA\nThe long sandbank tail at the island's tip\nPalm-lined jungle paths",
         expect=None, getting_there="Shared speedboat from the airport (≈1 hr 30 min) or domestic flight to Maamigili plus a short boat.",
         best="All year for whale sharks; mantas December–April", transfers="speedboat,domestic_flight", km=95, time="≈1 hr 30 min by speedboat",
         pop=600, bikini=True,
         activities=["Whale shark excursion", "Manta ray snorkeling", "Snorkeling", "Scuba diving", "Sandbank picnic", "Turtle snorkeling"]),
    dict(name="Dhangethi", atoll="South Ari", color="#1b6c9b", featured=True,
         tagline="Whale shark trips from a friendly fishing island",
         overview="Dhangethi is a traditional fishing community on the southern rim of Ari Atoll, a short boat ride from the South Ari Marine Protected Area where whale sharks are seen year-round. Guest houses, a bikini beach, local cafés and a handful of dive and excursion operators make it an easy, authentic base.",
         famous_for="Whale shark excursions in the South Ari MPA\nTraditional fishing community and boat-building\nMantas and turtles nearby\nClose to Maamigili domestic airport",
         airport="Maamigili (VAM)", airport_km=12,
         facilities="Several mosques and a football ground\nLocal cafés and small grocery shops\nDive centre and excursion operators",
         routes=[
             dict(mode="speedboat", origin="Velana International Airport (MLE)", duration="1 hr 30 min",
                  schedule="Shared speedboats several times a day; times vary by operator", price_note="per person one way",
                  notes="Ask your guest house to book — they coordinate with your flight time."),
             dict(mode="flight", origin="Velana International Airport (MLE)", via="Maamigili (VAM), then ≈20 min speedboat",
                  duration="≈25 min flight + 20 min boat", schedule="Daily domestic flights", price_note="per person one way",
                  notes="Good option for late arrivals or rough seas."),
             dict(mode="ferry", origin="Malé ferry terminal", operator_name="Public ferry (MTCC / RTL)",
                  duration="Several hours, multi-stop", schedule="A few days a week; no Friday service. Check the current timetable.",
                  price_note="low cost, pay locally in MVR", notes="Cheapest but slowest way to reach South Ari."),
         ],
         expect=None, getting_there="Shared speedboat from the airport (≈1 hr 30 min).",
         best="All year", transfers="speedboat,domestic_flight", km=90, time="≈1 hr 30 min by speedboat", pop=1200, bikini=True,
         activities=["Whale shark excursion", "Scuba diving", "Snorkeling", "Sunset & night fishing"]),
    dict(name="Fenfushi", atoll="South Ari", color="#2c7a7b",
         tagline="Coral stone mosque and whale shark waters",
         overview="Fenfushi sits on the southern rim of Ari Atoll near the whale shark area. Its historic coral stone mosque is one of the finest examples of traditional Maldivian architecture.",
         famous_for="Historic coral stone mosque\nClose to the whale shark area\nTraditional craftsmanship",
         expect=None, getting_there="Domestic flight to Maamigili plus a short boat, or speedboat from the airport (≈1 hr 45 min).",
         best="All year", transfers="speedboat,domestic_flight", km=100, time="≈1 hr 45 min by speedboat", pop=800,
         activities=["Whale shark excursion", "Local culture & village walk", "Snorkeling", "Scuba diving"]),
    dict(name="Omadhoo", atoll="South Ari", color="#3b8ea5",
         tagline="Slow island life in South Ari",
         overview="A small, quiet island ideal for travellers who want calm beaches and authentic local life, with mantas and whale sharks within reach.",
         famous_for="Quiet bikini beach\nManta and whale shark trips\nAuthentic village life",
         expect=None, getting_there="Shared speedboat from the airport (≈1 hr 30 min).",
         best="December–April", transfers="speedboat", km=85, time="≈1 hr 30 min by speedboat", pop=700, bikini=True,
         activities=["Whale shark excursion", "Manta ray snorkeling", "Snorkeling", "Sandbank picnic"]),
    dict(name="Dharavandhoo", atoll="Baa", featured=True, color="#155e75",
         tagline="Gateway to Hanifaru Bay's manta gatherings",
         overview="Dharavandhoo is the closest local island to Hanifaru Bay, a protected area in the Baa Atoll UNESCO Biosphere Reserve where hundreds of manta rays gather to feed during the south-west monsoon. The island also has a domestic airport.",
         famous_for="Hanifaru Bay manta ray and whale shark feeding aggregations\nBaa Atoll UNESCO Biosphere Reserve\nDomestic airport on the island",
         expect=None, getting_there="Domestic flight from Malé to Dharavandhoo (≈35 min) or seaplane / speedboat.",
         best="May–November for the Hanifaru manta season", transfers="domestic_flight,speedboat", km=120, time="≈35 min by domestic flight",
         pop=1000, bikini=True, activities=["Manta ray snorkeling", "Scuba diving", "Snorkeling", "Sandbank picnic", "Dolphin cruise"]),
    dict(name="Hanimaadhoo", atoll="Haa Dhaalu", color="#3f7d5c",
         tagline="Unspoilt northern beaches with its own airport",
         overview="Hanimaadhoo has an airport and some of the longest, emptiest beaches in the country — a great base to explore the remote north.",
         famous_for="Long, empty natural beaches\nAirport with flights from Malé\nGateway to historic Utheemu",
         expect=None, getting_there="Domestic flight from Malé (≈1 hr).",
         best="December–April", transfers="domestic_flight", km=280, time="≈1 hr by domestic flight", pop=2000, bikini=True, atm=True, hosp=True,
         activities=["Snorkeling", "Local culture & village walk", "Sunset & night fishing", "Island hopping"]),
    dict(name="Fuvahmulah", atoll="Fuvahmulah", featured=True, color="#1e3a5f",
         tagline="Tiger sharks, freshwater lakes and pebble beaches",
         overview="Fuvahmulah is a one-island atoll in the equatorial channel. With no lagoon around it, big ocean life comes close: it is one of the few places in the world to dive with tiger sharks almost every day. On land you'll find freshwater lakes, wetlands and the white-pebble Thoondu beach.",
         famous_for="Tiger shark dives, plus thresher and hammerhead sightings\nThoondu beach with its white pebbles\nFreshwater lakes and wetlands — rare in the Maldives\nLush fruit gardens and a unique local dialect",
         expect="Big swells: the ocean is right at the shore, so beach swimming is limited\nDiving is advanced — check your experience level with the dive centre\nRent a scooter or bicycle to explore the large island\nModest dress in villages; no alcohol",
         getting_there="Domestic flight from Malé (≈1 hr 20 min) to Fuvahmulah airport.",
         best="All year for tiger sharks; December–April for calmer seas", transfers="domestic_flight", km=490, time="≈1 hr 20 min by domestic flight",
         pop=10000, bikini=False, atm=True, hosp=True,
         activities=["Tiger shark dive", "Scuba diving", "Freediving", "Local culture & village walk"]),
    dict(name="Hithadhoo", atoll="Addu", color="#335c81",
         tagline="Addu City: causeways, wetlands and WWII history",
         overview="Hithadhoo is the largest island of Addu City, linked by road to Maradhoo, Feydhoo and Gan. Explore by bike, visit the Eedhigali Kilhi wetland and dive the British Loyalty wreck.",
         famous_for="Islands linked by causeways — cycle between them\nEedhigali Kilhi protected wetland\nBritish Loyalty WWII shipwreck dive\nFormer RAF Gan base history",
         expect="A city island — more cars and shops than most local islands\nCycling is the best way to get around\nModest dress; no alcohol outside resorts",
         getting_there="Domestic or international flights to Gan airport (≈1 hr 15 min from Malé), then a short drive.",
         best="All year; December–April driest", transfers="domestic_flight,road", km=540, time="≈1 hr 15 min by domestic flight",
         pop=20000, bikini=False, atm=True, hosp=True,
         activities=["Wreck diving", "Scuba diving", "Manta ray snorkeling", "Local culture & village walk", "Kayaking & SUP"]),
]


CENSUS = "https://census.gov.mv/2022/wp-content/uploads/2023/07/P5.pdf"


def wp(title):
    return f"https://en.wikipedia.org/wiki/{title}"


# Facts gathered from Wikipedia, the 2022 Maldives census (via citypopulation.de) and island council sites.
# pop = 2022 census residents (including foreign residents); area in km²; km = distance from Malé.
FACTS = {
    "Malé": dict(pop=211908, area=8.30, wiki="Malé", note="Malé City recorded 211,908 residents in the 2022 census, about two in five of everyone living in the Maldives."),
    "Hulhumalé": dict(pop=53193, area=4.0, wiki="Hulhumalé", note="Hulhumalé had 53,193 residents in 2022 and is the fastest-growing part of the capital region."),
    "Maafushi": dict(pop=4471, area=0.416, km=26, wiki="Maafushi_(Kaafu_Atoll)", note="With 4,471 residents in the 2022 census, Maafushi is one of the most densely built local islands, about 26 km south of Malé."),
    "Guraidhoo": dict(pop=1743, km=31, wiki="Guraidhoo_(Kaafu_Atoll)", note="Guraidhoo lies about 31 km south of Malé and had 1,743 residents in 2022."),
    "Gulhi": dict(pop=976, wiki="Gulhi", note="Gulhi, a near neighbour of Maafushi in South Malé Atoll, had 976 residents in the 2022 census."),
    "Huraa": dict(pop=1654, km=20, wiki="Huraa_(Kaafu_Atoll)", note="Huraa sits about 20 km north-east of Malé. The mangrove swamp at its northern end is a protected nature reserve."),
    "Thulusdhoo": dict(pop=1801, wiki="Thulusdhoo", note="The island's Coca-Cola plant, run by the Male' Aerated Water Company for more than 30 years, is widely described as the only one in the world that bottles with desalinated seawater."),
    "Himmafushi": dict(pop=2012, wiki="Himmafushi", note="The 2022 census counted 2,012 people on Himmafushi; the total includes residents of the island's correctional and rehabilitation facilities."),
    "Dhiffushi": dict(pop=1270, km=37, wiki="Dhiffushi_(Kaafu_Atoll)", note="Dhiffushi is about 37 km north-east of Malé on the eastern rim of North Malé Atoll, with 1,270 residents in 2022."),
    "Fulidhoo": dict(pop=400, area=0.113, km=56, wiki="Fulidhoo", note="Just 11 hectares in size and home to 400 people (2022), Fulidhoo lies about 56 km south of Malé in Vaavu, the least populated atoll in the country."),
    "Rasdhoo": dict(pop=1282, km=58, wiki="Rasdhoo", note="Rasdhoo is the only inhabited island on its own small natural atoll, about 58 km west of Malé, with 1,282 residents in 2022."),
    "Ukulhas": dict(pop=1284, area=1.0, wiki="Ukulhas", note="Ukulhas opened a waste management centre in November 2011 and is often cited as the first island in the Maldives to manage its waste systematically; a UNDP study uses it as a case study."),
    "Mathiveri": dict(pop=878, km=85, wiki="Mathiveri", note="Mathiveri is about 85 km west of Malé and had 878 residents in the 2022 census."),
    "Thoddoo": dict(pop=1924, area=1.726, wiki="Thoddoo", note="Thoddoo is the largest watermelon producer in the Maldives, with much of the harvest timed for Ramadan. Archaeologists have found Buddhist remains here from the centuries before the country converted to Islam."),
    "Dhigurah": dict(pop=761, wiki="Dhigurah_(Alif_Dhaalu_Atoll)", note="About 3.2 km long and less than 300 m wide, Dhigurah is the home base of the Maldives Whale Shark Research Programme. It had 761 residents in 2022."),
    "Dhangethi": dict(pop=936, area=0.245, km=88, wiki="Dhangethi", note="Dhangethi measures roughly 925 m by 350 m and is the third most populous island of Alif Dhaal Atoll, with 936 residents in the 2022 census."),
    "Fenfushi": dict(pop=1000, wiki="Fenfushi_(Alif_Dhaal_Atoll)", note="Fenfushi had 1,000 residents in the 2022 census."),
    "Omadhoo": dict(pop=913, km=74, wiki="Omadhoo_(Alif_Dhaalu_Atoll)", note="Omadhoo lies about 74 km south-west of Malé and is linked to the capital by ferry and scheduled speedboats. Population 913 (2022)."),
    "Dharavandhoo": dict(pop=997, wiki="Dharavandhoo", note="Dharavandhoo Airport (DRV) opened on 17 October 2012, a few minutes by boat from Hanifaru Bay, where up to a hundred manta rays can gather to feed."),
    "Hanimaadhoo": dict(pop=2664, wiki="Hanimaadhoo", note="Hanimaadhoo International Airport (HAQ) opened for domestic flights in 1986 and gained international status in 2012; its runway is 2,465 m long. The island had 2,664 residents in 2022."),
    "Fuvahmulah": dict(pop=9177, area=4.94, wiki="Fuvahmulah", note="Fuvahmulah covers about 4.9 km² — large for the Maldives — and had roughly 9,200 usual residents in the 2022 census."),
    "Hithadhoo": dict(pop=13759, wiki="Hithadhoo_(Addu)", note="With 13,759 residents in the 2022 census, Hithadhoo is the most populous administrative island in the Maldives after Malé."),
}


def default_routes(d):
    """Indicative routes derived from an island's transfer types. Refine them in the admin."""
    routes, t = [], d["transfers"]
    dur = d["time"].replace("≈", "").split(" by ")[0].strip()
    if "speedboat" in t:
        routes.append(dict(mode="speedboat", origin="Velana International Airport (MLE)", duration=dur,
                           schedule="Several departures daily; times vary by operator", price_note="per person one way",
                           notes="Book through your guest house — they will meet you at the airport."))
    if "ferry" in t:
        routes.append(dict(mode="ferry", origin="Malé ferry terminal", operator_name="Public ferry (MTCC / RTL)",
                           duration="Longer than speedboat", schedule="Usually Saturday–Thursday; no Friday service. Check the current timetable.",
                           price_note="low cost, pay locally in MVR", notes="Cheapest option, but slow and not timed for flights."))
    if "domestic_flight" in t:
        routes.append(dict(mode="flight", origin="Velana International Airport (MLE)", via=d.get("airport", ""),
                           duration=dur if "flight" in d["time"] else "Short domestic flight",
                           schedule="Daily flights; times vary by season", price_note="per person one way"))
    if "road" in t and "ferry" not in t and "speedboat" not in t:
        routes.append(dict(mode="private", origin="Airport / nearby islands", duration=dur, operator_name="Taxi or bus",
                           schedule="Any time", notes="Connected by road."))
    return routes


DEMO_LISTINGS = [
    # (island, kind, name, short, price, unit, featured, extras)
    ("Maafushi", "guesthouse", "Coral Breeze Inn", "Bright rooms two minutes from the bikini beach, with daily excursions.", 75, "night", True,
     {"room_count": 12, "max_guests": 3, "distance_to_beach_m": 150, "amenities": ["Free WiFi", "Air conditioning", "Breakfast included", "Excursion desk", "Hot water", "Airport transfer arranged"]}),
    ("Maafushi", "hotel", "Lagoon View Hotel", "Four-storey island hotel with rooftop terrace and lagoon views.", 110, "night", False,
     {"room_count": 28, "max_guests": 4, "distance_to_beach_m": 50, "star_rating": 3, "amenities": ["Free WiFi", "Air conditioning", "Restaurant", "Rooftop terrace", "Sea view", "24h reception"]}),
    ("Maafushi", "activity", "Blue Horizon Excursions", "Sandbank picnics, dolphin cruises and resort day trips from Maafushi.", 35, "person", True,
     {"activities": ["Sandbank picnic", "Dolphin cruise", "Resort day trip", "Snorkeling"]}),
    ("Thoddoo", "guesthouse", "Papaya Garden Retreat", "Family-run guest house beside the farms, bikes included.", 65, "night", True,
     {"room_count": 6, "max_guests": 3, "distance_to_beach_m": 300, "amenities": ["Free WiFi", "Air conditioning", "Breakfast included", "Bicycle rental", "Family rooms"]}),
    ("Dhigurah", "guesthouse", "Whale Tail Lodge", "Steps from the sandbank tail; whale shark trips every morning.", 90, "night", True,
     {"room_count": 8, "max_guests": 3, "distance_to_beach_m": 40, "amenities": ["Free WiFi", "Air conditioning", "Breakfast included", "Beach access", "Snorkel gear"]}),
    ("Dhigurah", "dive", "South Ari Divers", "PADI dive centre specialising in whale shark and manta dives.", 70, "dive", False,
     {"activities": ["Whale shark excursion", "Scuba diving", "Manta ray snorkeling"]}),
    ("Fulidhoo", "guesthouse", "Bodu Beru Beach House", "Cosy six-room house on the beach, nurse sharks by the jetty.", 85, "night", False,
     {"room_count": 6, "max_guests": 2, "distance_to_beach_m": 10, "amenities": ["Free WiFi", "Air conditioning", "Breakfast included", "Sea view", "Kayak / SUP"]}),
    ("Rasdhoo", "dive", "Madivaru Dive Point", "Dawn hammerhead dives and courses for all levels.", 65, "dive", True,
     {"activities": ["Hammerhead dive", "Scuba diving", "Snorkeling"]}),
    ("Ukulhas", "guesthouse", "Clean Island Suites", "Modern suites facing Ukulhas' long bikini beach.", 95, "night", False,
     {"room_count": 10, "max_guests": 3, "distance_to_beach_m": 20, "amenities": ["Free WiFi", "Air conditioning", "Breakfast included", "Sea view", "Restaurant"]}),
    ("Fuvahmulah", "dive", "Tiger Reef Diving", "Daily tiger shark dives with experienced local guides.", 120, "dive", True,
     {"activities": ["Tiger shark dive", "Scuba diving", "Freediving"]}),
    ("Huraa", "transfer", "North Malé Speedboat Transfers", "Scheduled and private speedboat transfers to/from the airport.", 40, "person", False,
     {"activities": ["Island hopping"]}),
    ("Dhangethi", "guesthouse", "Ari Reef View Guest House", "Sea-facing rooms by the bikini beach, whale shark trips arranged daily.", 70, "night", True,
     {"room_count": 8, "max_guests": 3, "distance_to_beach_m": 60, "amenities": ["Free WiFi", "Air conditioning", "Breakfast included", "Excursion desk", "Airport transfer arranged"]}),
    ("Dhangethi", "activity", "Dhangethi Whale Shark Trips", "Small-group whale shark and manta snorkeling tours with local guides.", 60, "person", True,
     {"activities": ["Whale shark excursion", "Manta ray snorkeling", "Sandbank picnic", "Sunset & night fishing"]}),
    ("Dhangethi", "restaurant", "Fathuhu Café", "Seafront café serving Maldivian breakfast, fresh tuna and grills.", 8, "person", True,
     {"cuisine": "Maldivian, seafood, grills", "opening_hours": "Daily 7:00–23:00 (Friday from 14:00)", "breakfast": True, "delivery": True}),
    ("Dhangethi", "transfer", "South Ari Speed Link", "Shared and private speedboats between Malé airport, Maamigili and South Ari islands.", 65, "person", False,
     {"routes": [dict(mode="speedboat", origin="Velana International Airport (MLE)", duration="1 hr 30 min", schedule="Daily 10:00, 15:30 and 21:30 from the airport", price_from=65, price_note="per person one way"),
                 dict(mode="private", origin="Maamigili airport (VAM)", duration="20 min", schedule="Meets every domestic flight", price_from=25, price_note="per person one way")]}),
    ("Maafushi", "restaurant", "Ocean Grill Maafushi", "Beachfront grill with fresh catch of the day and Asian dishes.", 12, "person", False,
     {"cuisine": "Seafood, Asian, international", "opening_hours": "Daily 11:00–23:00"}),
    ("Thoddoo", "restaurant", "Watermelon Juice Corner", "Fresh juices from Thoddoo farms, short eats and Maldivian curries.", 5, "person", False,
     {"cuisine": "Maldivian, juices, short eats", "opening_hours": "Daily 8:00–22:00", "breakfast": True}),
    ("Thulusdhoo", "guesthouse", "Cokes Surf Camp", "Surf camp with boat trips to Cokes, Chickens and beyond.", 80, "night", False,
     {"room_count": 9, "max_guests": 2, "distance_to_beach_m": 100, "amenities": ["Free WiFi", "Air conditioning", "Breakfast included", "Excursion desk"], "activities": ["Surfing"]}),
]


class Command(BaseCommand):
    help = "Seed Maldives atolls, islands, activities and amenities (add --demo for sample listings)."

    def add_arguments(self, parser):
        parser.add_argument("--demo", action="store_true", help="Also create a demo owner, listings and enquiries")
        parser.add_argument("--if-empty", action="store_true", help="Do nothing if islands already exist (safe on every deploy)")

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts["if_empty"] and Island.objects.exists():
            self.stdout.write("Islands already exist; skipping seed.")
            return
        for i, (name, official, code, region, desc) in enumerate(ATOLLS):
            Atoll.objects.update_or_create(name=name, defaults=dict(official_name=official, code=code, region=region, description=desc, order=i))
        for name, icon, desc in ACTIVITIES:
            ActivityType.objects.update_or_create(
                name=name, defaults=dict(icon=icon, description=desc, photo_search=PHOTO_SEARCH.get(name, f"{name} Maldives")))
        for name, icon in AMENITIES:
            Amenity.objects.update_or_create(name=name, defaults=dict(icon=icon))

        acts = {a.name: a for a in ActivityType.objects.all()}
        for d in ISLANDS:
            f = FACTS.get(d["name"], {})
            d = {**d, "pop": f.get("pop", d["pop"]), "km": f.get("km", d["km"])}
            if f.get("note"):
                d["overview"] = d["overview"] + "\n\n" + f["note"]
            expect = d["expect"] or "\n".join(STD_EXPECT)
            island, _ = Island.objects.update_or_create(
                name=d["name"], atoll=Atoll.objects.get(name=d["atoll"]),
                defaults=dict(
                    island_type=d.get("island_type", "local"), tagline=d["tagline"], overview=d["overview"],
                    famous_for=d["famous_for"], what_to_expect=expect, getting_there=d["getting_there"],
                    best_time_to_visit=d["best"], transfer_types=d["transfers"], distance_from_airport_km=d["km"],
                    transfer_time=d["time"], population=d["pop"], has_bikini_beach=d.get("bikini", False),
                    has_atm=d.get("atm", False), has_hospital=d.get("hosp", True), cover_color=d["color"],
                    has_pharmacy=d.get("hosp", True), has_police=d["pop"] >= 1000, has_supermarket=True, has_4g=True,
                    has_full_hospital=d["name"] in ("Malé", "Hulhumalé", "Fuvahmulah", "Hithadhoo"),
                    has_5g=d["name"] in ("Malé", "Hulhumalé"),
                    nearest_airport=d.get("airport", "Velana International (MLE)"),
                    nearest_airport_km=d.get("airport_km", d["km"]),
                    local_rules=d.get("rules", "\n".join(STD_RULES)), accessibility=d.get("access", "\n".join(STD_ACCESS)),
                    facilities_notes=d.get("facilities", ""),
                    is_featured=d.get("featured", False), is_published=True,
                    area_km2=f.get("area"), population_year=2022, wikipedia_title=f.get("wiki", ""),
                    sources="\n".join(u for u in [wp(f["wiki"]) if f.get("wiki") else "", CENSUS] if u),
                ),
            )
            island.activities.set([acts[a] for a in d["activities"]])
            if not island.routes.exists():
                for i, r in enumerate(d.get("routes") or default_routes(d)):
                    TransportRoute.objects.create(island=island, order=i, **r)
        geo.apply(Atoll, Island)
        self.stdout.write(self.style.SUCCESS(f"Seeded {Atoll.objects.count()} atolls, {Island.objects.count()} islands, {ActivityType.objects.count()} activity types."))

        if opts["demo"]:
            self._demo(acts)

    def _demo(self, acts):
        User = get_user_model()
        owner, created = User.objects.get_or_create(
            username="owner@demo.mv", defaults=dict(email="owner@demo.mv", first_name="Demo", last_name="Owner")
        )
        if created:
            owner.set_password("demo12345")
            owner.save()
            Profile.objects.create(user=owner, business_name="Demo Island Hospitality", phone="+9607000000")
        amen = {a.name: a for a in Amenity.objects.all()}
        for island_name, kind, name, short, price, unit, featured, extra in DEMO_LISTINGS:
            island = Island.objects.get(name=island_name)
            listing, _ = Listing.objects.update_or_create(
                name=name, island=island,
                defaults=dict(
                    owner=owner, kind=kind, short_description=short,
                    description=f"{short}\n\nThis is demo content for {name} on {island.name}. Replace it with a real description of your rooms, services, food and what makes your place special.",
                    price_from=price, price_unit=unit, currency="USD", status=Listing.STATUS_APPROVED,
                    is_featured=featured, is_verified=featured, contact_name="Demo Owner", contact_email="owner@demo.mv",
                    contact_phone="+960 700 0000", whatsapp="+9607000000",
                    room_count=extra.get("room_count"), max_guests=extra.get("max_guests"),
                    distance_to_beach_m=extra.get("distance_to_beach_m"), star_rating=extra.get("star_rating"),
                    check_in_time="14:00" if kind in Listing.STAY_KINDS else "", check_out_time="12:00" if kind in Listing.STAY_KINDS else "",
                ),
            )
            if kind == "restaurant":
                listing.cuisine = extra.get("cuisine", "")
                listing.opening_hours = extra.get("opening_hours", "")
                listing.serves_breakfast = extra.get("breakfast", False)
                listing.delivery = extra.get("delivery", False)
                listing.save()
            if featured and not listing.verified_at:
                listing.verified_at = timezone.now()
                listing.registration_number = "DEMO-0000"
                listing.save()
            for i, r in enumerate(extra.get("routes", [])):
                TransportRoute.objects.get_or_create(operator=listing, island=island, mode=r["mode"], origin=r["origin"], defaults={**r, "order": 10 + i})
            listing.amenities.set([amen[a] for a in extra.get("amenities", [])])
            listing.activity_types.set([acts[a] for a in extra.get("activities", [])])
            if kind in Listing.STAY_KINDS and not listing.rooms.exists():
                RoomType.objects.create(listing=listing, name="Deluxe Double", description="Queen bed, AC, private bathroom", max_guests=2, price_from=price)
                RoomType.objects.create(listing=listing, name="Family Room", description="Double + single bed", max_guests=3, price_from=price + 30)
        # One pending listing so the moderation queue isn't empty.
        Listing.objects.get_or_create(
            name="Sunset Sands Guest House", island=Island.objects.get(name="Gulhi"),
            defaults=dict(owner=owner, kind="guesthouse", short_description="New guest house awaiting approval.",
                          description="Awaiting review.", contact_name="Demo Owner", contact_email="owner@demo.mv"),
        )
        first = Listing.objects.get(name="Coral Breeze Inn")
        if not first.enquiries.exists():
            today = timezone.localdate()
            Enquiry.objects.create(listing=first, guest_name="Anna Schmidt", guest_email="anna@example.com", guest_country="Germany",
                                   check_in=today + timedelta(days=30), check_out=today + timedelta(days=36), adults=2,
                                   room_type="Deluxe Double", needs_transfer=True, preferred_contact="whatsapp", guest_phone="+491701234567",
                                   message="Hi! We'd love to stay 6 nights. Could you also arrange the speedboat from the airport? We land at 14:30.")
            Enquiry.objects.create(listing=first, guest_name="Kenji Tanaka", guest_email="kenji@example.com", guest_country="Japan",
                                   check_in=today + timedelta(days=60), check_out=today + timedelta(days=64), adults=2, children=1,
                                   room_type="Family Room", status="replied", message="Is the family room available for these dates? Do you offer a sandbank trip?")
        self.stdout.write(self.style.SUCCESS("Demo data created. Owner login: owner@demo.mv / demo12345"))
