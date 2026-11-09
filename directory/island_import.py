"""Add every inhabited island of the Maldives from directory/data/inhabited_islands.json.

The data comes from Wikipedia ("List of islands of the Maldives" and each island's article, CC BY-SA) and
Wikidata (coordinates). New islands are marked "facilities not confirmed" so pages never claim an island has
no ATM or hospital when we simply don't know yet. Existing islands only get empty fields filled in.

Written to work with Django's historical models, so a data migration can call it.
"""
import json
import math
import unicodedata
from pathlib import Path

from django.utils.text import slugify

DATA = Path(__file__).resolve().parent / "data" / "inhabited_islands.json"
AIRPORT = (4.1918, 73.5290)  # Velana International Airport
SOUTH_MALE = {"maafushi", "guraidhoo", "gulhi"}


def _norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return "".join(c for c in s if c.isalnum())


def _sound(s):
    """Spelling-insensitive key: Maduvvari and Maduvvaree both become 'maduvari'."""
    s = _norm(s)
    for x, y in (("ee", "i"), ("oo", "u"), ("aa", "a"), ("ey", "e"), ("ei", "e")):
        s = s.replace(x, y)
    return "".join(c for i, c in enumerate(s) if i == 0 or c != s[i - 1])


def similar(a, b):
    """Same island spelled differently, e.g. Maduvvari / Maduvvaree, Hulhumale / Hulhumalé."""
    return _norm(a) == _norm(b) or _sound(a) == _sound(b)


def _km(lat, lon):
    la1, lo1, la2, lo2 = map(math.radians, (AIRPORT[0], AIRPORT[1], lat, lon))
    a = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return round(6371 * 2 * math.asin(math.sqrt(a)))


def _tagline(rec, atoll_name):
    if rec.get("capital"):
        return f"Capital island of {atoll_name}"[:140]
    if rec.get("population"):
        return f"Island community of {rec['population']:,} people in {atoll_name}"[:140]
    return f"Inhabited local island in {atoll_name}"[:140]


def import_islands(Island, Atoll, data=None, log=print):
    data = data if data is not None else json.loads(DATA.read_text(encoding="utf-8"))
    atolls = list(Atoll.objects.all())
    by_official = {}
    for a in atolls:
        by_official.setdefault(_norm(a.official_name or a.name), []).append(a)
    existing = list(Island.objects.all())
    slugs = {i.slug for i in existing}
    created = updated = skipped = 0
    for rec in data:
        candidates = by_official.get(_norm(rec["atoll"]), [])
        if not candidates:
            skipped += 1
            continue
        if len(candidates) > 1:  # Kaafu is split into North and South Malé on the site
            want = "south" if _norm(rec["name"]) in SOUTH_MALE else "north"
            atoll = next((a for a in candidates if want in _norm(a.name)), candidates[0])
        else:
            atoll = candidates[0]
        same = [i for i in existing if (i.wikipedia_title and i.wikipedia_title == rec["wikipedia"])
                or (similar(i.name, rec["name"]) and i.atoll_id in {a.pk for a in candidates})]
        if same:
            isl = same[0]
            changed = []
            for field, value in (("population", rec.get("population")), ("area_km2", rec.get("area_km2")),
                                 ("latitude", rec.get("lat")), ("longitude", rec.get("lon")),
                                 ("overview", rec.get("overview")), ("wikipedia_title", rec.get("wikipedia"))):
                if value and not getattr(isl, field):
                    setattr(isl, field, value)
                    changed.append(field)
            if rec.get("lat") and not isl.distance_from_airport_km:
                isl.distance_from_airport_km = _km(rec["lat"], rec["lon"])
                changed.append("distance_from_airport_km")
            if changed:
                isl.save(update_fields=changed)
                updated += 1
            continue
        base = slugify(rec["name"])[:50] or "island"
        slug = base if base not in slugs else f"{base}-{slugify(atoll.official_name or atoll.name)}"[:50]
        n = 2
        while slug in slugs:
            slug, n = f"{base}-{n}", n + 1
        slugs.add(slug)
        wiki = "https://en.wikipedia.org/wiki/" + rec["wikipedia"].replace(" ", "_") if rec.get("wikipedia") else ""
        isl = Island(
            atoll=atoll, name=rec["name"], slug=slug, island_type="capital" if _norm(rec["name"]) == "male" else "local",
            tagline=_tagline(rec, atoll.name), overview=rec.get("overview") or "",
            population=rec.get("population"), population_year=2022, area_km2=rec.get("area_km2"),
            latitude=rec.get("lat"), longitude=rec.get("lon"),
            distance_from_airport_km=_km(rec["lat"], rec["lon"]) if rec.get("lat") else None,
            wikipedia_title=rec.get("wikipedia") or "", sources=wiki,
            details_verified=False, is_published=True, has_4g=True,
        )
        isl.save()
        existing.append(isl)
        created += 1
    log(f"Islands: {created} added, {updated} existing ones filled in, {skipped} skipped.")
    return created, updated


def remove_spelling_duplicates(Island, log=print):
    """Delete islands the import added that duplicate an existing island under another spelling,
    when nothing (listings, photos, guides, routes) is attached to the imported copy."""
    removed = 0
    islands = list(Island.objects.all())
    for imp in [i for i in islands if not i.details_verified]:
        twins = [o for o in islands if o.pk != imp.pk and o.atoll_id == imp.atoll_id and o.details_verified and similar(o.name, imp.name)]
        if not twins:
            continue
        if imp.listings.exists() or imp.photos.exists() or imp.guides.exists() or imp.routes.exists() or imp.cover_image:
            continue
        twin = twins[0]
        for f in ("population", "latitude", "longitude", "area_km2", "wikipedia_title", "overview"):
            if not getattr(twin, f) and getattr(imp, f):
                setattr(twin, f, getattr(imp, f))
        twin.save()
        imp.delete()
        removed += 1
    log(f"Removed {removed} duplicate island(s).")
    return removed
