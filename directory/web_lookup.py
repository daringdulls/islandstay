"""Free web lookup for the back office (no API key): Wikipedia, Wikidata, OpenStreetMap and the business's own site.

Returns the same shape as ai_assist.research(): {"fields": {...}, "sources": [...], "notes": str}.
Every value is a suggestion the editor reviews before applying.
"""
import html
import json
import logging
import math
import re
import urllib.parse
import urllib.request

log = logging.getLogger(__name__)
UA = "IslandStayBot/1.0 (https://github.com/daringdulls/islandstay; back-office lookup)"
VELANA = (4.1918, 73.5291)
# Approximate airport positions, used only to suggest the nearest one.
AIRPORTS = [
    ("Velana International (MLE)", 4.1918, 73.5291), ("Maamigili (VAM)", 3.4706, 72.8356),
    ("Dharavandhoo (DRV)", 5.1561, 73.1302), ("Hanimaadhoo (HAQ)", 6.7442, 73.1705),
    ("Ifuru (IFU)", 5.7083, 73.0250), ("Kadhdhoo (KDO)", 1.8592, 73.5219),
    ("Kaadedhdhoo (KDM)", 0.4881, 72.9969), ("Kooddoo (GKK)", 0.7324, 73.4336),
    ("Gan International (GAN)", -0.6934, 73.1556), ("Fuvahmulah (FVM)", -0.3094, 73.4350),
    ("Thimarafushi (TMF)", 2.2111, 73.1533), ("Kulhudhuffushi (HDK)", 6.6306, 73.0697),
]


class LookupError_(Exception):
    pass


def _get(url, data=None, timeout=20, accept="application/json"):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read(2_000_000)
        charset = r.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, "replace")


def _json(url, **kw):
    return json.loads(_get(url, **kw))


def _km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


# ------------------------------------------------------------------ islands
def _wikipedia(name, context):
    q = f"{name} {context} Maldives island".strip()
    hits = _json("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "query", "list": "search", "srsearch": q, "srlimit": 5, "format": "json"}))["query"]["search"]
    title = next((h["title"] for h in hits if name.lower() in h["title"].lower()), hits[0]["title"] if hits else None)
    if not title:
        return None
    pages = _json("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "prop": "extracts|coordinates|pageprops", "exintro": 1, "explaintext": 1,
        "redirects": 1, "titles": title, "format": "json"}))["query"]["pages"]
    page = next(iter(pages.values()))
    if "missing" in page:
        return None
    coords = (page.get("coordinates") or [{}])[0]
    return {"title": page.get("title", title), "extract": page.get("extract", ""),
            "lat": coords.get("lat"), "lon": coords.get("lon"),
            "qid": (page.get("pageprops") or {}).get("wikibase_item")}


def _claim_amount(claims, prop):
    """Latest numeric value of a Wikidata property, with its year if given."""
    best = None
    for c in claims.get(prop, []):
        snak = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if not isinstance(snak, dict) or "amount" not in snak:
            continue
        year = None
        for q in c.get("qualifiers", {}).get("P585", []):
            t = q.get("datavalue", {}).get("value", {}).get("time", "")
            year = int(t[1:5]) if t[1:5].isdigit() else None
        cand = (year or 0, float(snak["amount"]), snak.get("unit", ""), year)
        if best is None or cand[0] > best[0]:
            best = cand
    return best


def _wikidata(qid):
    ent = _json(f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json")["entities"][qid]
    claims = ent.get("claims", {})
    out = {}
    pop = _claim_amount(claims, "P1082")
    if pop:
        out["population"] = str(int(pop[1]))
        if pop[3]:
            out["population_year"] = str(pop[3])
    area = _claim_amount(claims, "P2046")
    if area:
        value, unit = area[1], area[2]
        if unit.endswith("Q35852"):  # hectare
            value /= 100
        elif unit.endswith("Q25343"):  # square metre
            value /= 1_000_000
        out["area_km2"] = f"{value:.3f}".rstrip("0").rstrip(".")
    coord = claims.get("P625", [{}])[0].get("mainsnak", {}).get("datavalue", {}).get("value")
    if isinstance(coord, dict):
        out["lat"], out["lon"] = coord.get("latitude"), coord.get("longitude")
    return out


def _osm_facilities(lat, lon, radius=1500):
    query = f"""[out:json][timeout:20];
(
  node(around:{radius},{lat},{lon})[amenity~"^(atm|bank|pharmacy|police|hospital|clinic|doctors|place_of_worship)$"];
  way(around:{radius},{lat},{lon})[amenity~"^(hospital|clinic|police|place_of_worship)$"];
  node(around:{radius},{lat},{lon})[shop~"^(supermarket|convenience|general)$"];
  node(around:{radius},{lat},{lon})[tourism~"^(guest_house|hotel|hostel)$"];
  way(around:{radius},{lat},{lon})[tourism~"^(guest_house|hotel)$"];
  node(around:{radius},{lat},{lon})[amenity~"^(restaurant|cafe)$"];
  node(around:{radius},{lat},{lon})[sport=scuba_diving];
);
out tags center 200;"""
    data = _json("https://overpass-api.de/api/interpreter", data=urllib.parse.urlencode({"data": query}).encode(), timeout=25)
    tags = [e.get("tags", {}) for e in data.get("elements", [])]
    amen = [t.get("amenity", "") for t in tags]
    has = lambda *k: "yes" if any(a in k for a in amen) else "unknown"  # noqa: E731
    stays = sorted({t["name"] for t in tags if t.get("tourism") in ("guest_house", "hotel", "hostel") and t.get("name")})
    food = sorted({t["name"] for t in tags if t.get("amenity") in ("restaurant", "cafe") and t.get("name")})
    dive = sorted({t["name"] for t in tags if t.get("sport") == "scuba_diving" and t.get("name")})
    mosques = sum(1 for t in tags if t.get("amenity") == "place_of_worship")
    return {
        "has_atm": "yes" if any(a in ("atm",) or (a == "bank" and t.get("atm") == "yes") for a, t in zip(amen, tags)) else "unknown",
        "has_pharmacy": has("pharmacy"), "has_police": has("police"),
        "has_hospital": has("clinic", "doctors", "hospital"), "has_full_hospital": has("hospital"),
        "has_supermarket": "yes" if any(t.get("shop") for t in tags) else "unknown",
        "mosques": mosques, "stays": stays, "food": food, "dive": dive,
    }


def lookup_island(name, context=""):
    fields, sources, notes = {}, [], []
    wiki = None
    try:
        wiki = _wikipedia(name, context)
    except Exception as exc:
        log.warning("Wikipedia lookup failed: %s", exc)
        notes.append("Wikipedia could not be reached.")
    lat = lon = None
    if wiki:
        sources.append("https://en.wikipedia.org/wiki/" + urllib.parse.quote(wiki["title"].replace(" ", "_")))
        fields["wikipedia_title"] = wiki["title"]
        paras = [p.strip() for p in wiki["extract"].split("\n") if p.strip()]
        if paras:
            fields["overview"] = "\n\n".join(paras[:3])
            first = re.split(r"(?<=[.!?])\s", paras[0])[0]
            if len(first) <= 140:
                fields["tagline"] = first
        lat, lon = wiki["lat"], wiki["lon"]
        if wiki["qid"]:
            try:
                wd = _wikidata(wiki["qid"])
                sources.append(f"https://www.wikidata.org/wiki/{wiki['qid']}")
                lat, lon = lat or wd.pop("lat", None), lon or wd.pop("lon", None)
                wd.pop("lat", None), wd.pop("lon", None)
                fields.update(wd)
            except Exception as exc:
                log.warning("Wikidata lookup failed: %s", exc)
    else:
        notes.append(f"No Wikipedia article found for “{name}”. Check the spelling, or fill the details by hand.")
    if lat is not None and lon is not None:
        fields["latitude"], fields["longitude"] = f"{lat:.6f}", f"{lon:.6f}"
        km = _km((lat, lon), VELANA)
        fields["distance_from_airport_km"] = str(round(km))
        name_, alat, alon = min(AIRPORTS, key=lambda a: _km((lat, lon), (a[1], a[2])))
        fields["nearest_airport"] = name_
        fields["nearest_airport_km"] = str(round(_km((lat, lon), (alat, alon))))
        if km < 60:
            fields["transfer_types"] = "speedboat, ferry"
        elif name_.startswith("Velana"):
            fields["transfer_types"] = "speedboat, ferry"
        else:
            fields["transfer_types"] = "domestic_flight, speedboat"
        try:
            osm = _osm_facilities(lat, lon)
            if osm["dive"]:
                fields["facilities_notes"] = "Dive centre: " + ", ".join(osm["dive"][:3])
            sources.append(f"https://www.openstreetmap.org/#map=16/{lat:.5f}/{lon:.5f}")
            for k in ("has_atm", "has_pharmacy", "has_police", "has_hospital", "has_full_hospital", "has_supermarket"):
                fields[k] = osm[k]
            extra = []
            if osm["mosques"]:
                extra.append(f"{osm['mosques']} mosque{'s' if osm['mosques'] != 1 else ''}")
            if osm["dive"]:
                extra.append("Dive centre: " + ", ".join(osm["dive"][:3]))
            if extra:
                fields["facilities_notes"] = "\n".join(extra)
            found = []
            if osm["stays"]:
                found.append(f"Guest houses on the map: {', '.join(osm['stays'][:8])}")
            if osm["food"]:
                found.append(f"Cafés and restaurants: {', '.join(osm['food'][:8])}")
            if found:
                notes.append(". ".join(found) + ". You could invite them to list.")
        except Exception as exc:
            log.warning("OpenStreetMap lookup failed: %s", exc)
            notes.append("OpenStreetMap could not be reached, so facilities weren't checked.")
        notes.append("Distances are straight-line estimates; transfer time, local rules and bikini beach aren't "
                     "available from these sources, so add them yourself.")
    text = (wiki["extract"] if wiki else "").lower()
    if re.search(r"\b(regional|atoll|city|general)? ?hospital\b", text) and "health centre" not in text.split("hospital")[0][-40:]:
        fields["has_full_hospital"] = "yes"
        fields["has_hospital"] = "yes"
    elif re.search(r"health (centre|center|post)|clinic", text):
        fields.setdefault("has_hospital", "yes")
    if wiki or lat is not None:
        # Dhiraagu and Ooredoo provide 4G on inhabited islands; marked as a suggestion to confirm.
        fields["has_4g"] = "yes"
        if "5g" in text:
            fields["has_5g"] = "yes"
        notes.append("Mobile data: Dhiraagu and Ooredoo cover inhabited islands with 4G, and 5G on some islands; "
                     "check their coverage maps to confirm 5G.")
    signals = [fields.get("overview", ""), fields.get("facilities_notes", "")]
    if wiki:
        signals.append(wiki["extract"])
    acts = suggest_activities(*signals)
    if acts:
        fields["activities"] = "\n".join(acts)
    return {"fields": fields, "sources": sources, "notes": " ".join(notes)}


# ------------------------------------------------------------------ businesses
def _nominatim(name, context):
    q = f"{name}, {context}, Maldives" if context else f"{name}, Maldives"
    rows = _json("https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": q, "format": "jsonv2", "addressdetails": 1, "extratags": 1, "limit": 3, "countrycodes": "mv"}))
    if not rows and context:
        rows = _json("https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
            {"q": f"{name}, Maldives", "format": "jsonv2", "addressdetails": 1, "extratags": 1, "limit": 3, "countrycodes": "mv"}))
    return rows[0] if rows else None


def _meta(page, *names):
    for n in names:
        m = re.search(r'<meta[^>]+(?:name|property)=["\']' + re.escape(n) + r'["\'][^>]*content=["\']([^"\']+)', page, re.I) or \
            re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:name|property)=["\']' + re.escape(n) + r'["\']', page, re.I)
        if m:
            return html.unescape(m.group(1)).strip()
    return ""


def _website(url):
    page = _get(url, accept="text/html,*/*", timeout=15)
    out = {"_text": ""}
    desc = _meta(page, "og:description", "description", "twitter:description")
    if desc:
        out["short_description"] = desc[:180]
    text = html.unescape(re.sub(r"(?s)<(script|style).*?</\1>|<[^>]+>", " ", page))
    text = re.sub(r"\s+", " ", text)
    out["_text"] = text[:20000]
    emails = [e for e in re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", page) if not e.lower().endswith((".png", ".jpg", ".webp", ".svg"))]
    if emails:
        out["contact_email"] = emails[0]
    phone = re.search(r"\+?960[\s-]?\d{3}[\s-]?\d{4}", text)
    if phone:
        out["contact_phone"] = phone.group(0)
    wa = re.search(r"wa\.me/(\d{7,15})", page)
    if wa:
        out["whatsapp"] = "+" + wa.group(1)
    fb = re.search(r"https?://(?:www\.)?facebook\.com/[A-Za-z0-9_.\-/]+", page)
    if fb and "sharer" not in fb.group(0):
        out["facebook"] = fb.group(0).rstrip("/")
    ig = re.search(r"https?://(?:www\.)?instagram\.com/[A-Za-z0-9_.]+", page)
    if ig:
        out["instagram"] = ig.group(0)
    checkin = re.search(r"check[- ]?in[^0-9]{0,20}(\d{1,2}[:.]\d{2}\s*(?:am|pm)?)", text, re.I)
    checkout = re.search(r"check[- ]?out[^0-9]{0,20}(\d{1,2}[:.]\d{2}\s*(?:am|pm)?)", text, re.I)
    if checkin:
        out["check_in_time"] = checkin.group(1)
    if checkout:
        out["check_out_time"] = checkout.group(1)
    rooms = re.search(r"(\d{1,3})\s+(?:guest\s+)?rooms\b", text, re.I)
    if rooms and 0 < int(rooms.group(1)) < 300:
        out["room_count"] = rooms.group(1)
    return out


def lookup_listing(name, context="", url=""):
    fields, sources, notes = {}, [], []
    place = None
    try:
        place = _nominatim(name, context)
    except Exception as exc:
        log.warning("Nominatim lookup failed: %s", exc)
        notes.append("OpenStreetMap could not be reached.")
    if place:
        tags, addr = place.get("extratags") or {}, place.get("address") or {}
        sources.append(f"https://www.openstreetmap.org/{place.get('osm_type', 'node')}/{place.get('osm_id', '')}")
        island = addr.get("island") or addr.get("village") or addr.get("town") or addr.get("city") or addr.get("hamlet")
        if island:
            fields["island_name"] = island
        street = ", ".join(x for x in (addr.get("house_number"), addr.get("road"), addr.get("suburb")) if x)
        if street:
            fields["address"] = street
        for src, dst in (("phone", "contact_phone"), ("contact:phone", "contact_phone"), ("email", "contact_email"),
                         ("contact:email", "contact_email"), ("website", "website"), ("contact:website", "website"),
                         ("contact:facebook", "facebook"), ("contact:instagram", "instagram"), ("opening_hours", "opening_hours"),
                         ("cuisine", "cuisine"), ("rooms", "room_count"), ("stars", "star_rating"), ("beds", "max_guests")):
            if tags.get(src) and not fields.get(dst):
                fields[dst] = tags[src].replace(";", ", ").replace("_", " ") if dst == "cuisine" else tags[src]
    else:
        notes.append(f"“{name}” isn't on OpenStreetMap yet.")
    site = url or fields.get("website", "")
    if site and not site.startswith("http"):
        site = "https://" + site
    if site and "facebook.com" not in site and "instagram.com" not in site:
        try:
            site_data = _website(site)
            site_text = site_data.pop("_text", "")
            for k, v in site_data.items():
                fields.setdefault(k, v)
            acts = suggest_activities(site_text, fields.get("short_description", ""))
            if acts:
                fields["activity_types"] = "\n".join(acts)
            sources.append(site)
            fields.setdefault("website", site)
        except Exception as exc:
            log.warning("Website read failed: %s", exc)
            notes.append(f"Couldn't read {site}.")
    elif site:
        key = "facebook" if "facebook.com" in site else "instagram"
        fields.setdefault(key, site)
    if not url and not fields.get("website"):
        notes.append("Paste the business's website link in the second box for more details.")
    notes.append("Descriptions, rooms and house rules usually need the owner's input; check every contact detail before publishing.")
    return {"fields": fields, "sources": sources, "notes": " ".join(notes)}


# ------------------------------------------------------------------ activities
ACTIVITY_KEYWORDS = {
    "scuba-diving": ["dive", "diving", "scuba", "dive centre", "dive center", "padi"],
    "snorkeling": ["snorkel", "house reef", "coral reef", "reef"],
    "manta-ray-snorkeling": ["manta"],
    "whale-shark-excursion": ["whale shark"],
    "turtle-snorkeling": ["turtle"],
    "hammerhead-dive": ["hammerhead"],
    "tiger-shark-dive": ["tiger shark"],
    "nurse-sharks-stingrays": ["nurse shark", "stingray"],
    "wreck-diving": ["wreck", "shipwreck"],
    "dolphin-cruise": ["dolphin"],
    "sandbank-picnic": ["sandbank", "sand bank", "finolhu", "picnic island"],
    "surfing": ["surf"],
    "big-game-fishing": ["big game", "game fishing", "tuna fishing"],
    "sunset-night-fishing": ["night fishing", "sunset fishing", "fishing trip"],
    "bioluminescence": ["bioluminescen", "glowing", "sea of stars"],
    "freediving": ["freediv", "free diving", "free-diving"],
    "kayaking-sup": ["kayak", "paddle", "stand-up", "sup "],
    "island-hopping": ["island hopping", "nearby islands", "excursion"],
    "resort-day-trip": ["resort day", "day pass", "nearby resort"],
    "local-culture-village-walk": ["village", "mosque", "traditional", "boat building", "handicraft", "culture"],
    "spa-wellness": ["spa", "massage", "wellness"],
    "water-sports": ["water sports", "jet ski", "parasail", "watersport"],
}


def suggest_activities(*texts):
    """Names of existing activity types that the given text mentions."""
    from .models import ActivityType

    blob = " ".join(t for t in texts if t).lower()
    if not blob:
        return []
    found = []
    for a in ActivityType.objects.order_by("name"):
        words = ACTIVITY_KEYWORDS.get(a.slug) or [a.name.lower().split()[0]]
        if any(w in blob for w in words):
            found.append(a.name)
    return found
