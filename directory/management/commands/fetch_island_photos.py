"""Find freely licensed photos on Wikimedia Commons for islands and experience types.

    python manage.py fetch_island_photos              # fill in anything that has no photo yet
    python manage.py fetch_island_photos --force      # look again for everything
    python manage.py fetch_island_photos --island maafushi

Photos are stored as links to Wikimedia's servers (with author, licence and source page), not as files,
so they survive restarts on hosts without a permanent disk. For each island it sets:
  * a cover photo: the Wikipedia article's lead image, or the best Commons search result;
  * a gallery of up to 6 Commons photos whose file names mention the island.
Each experience type gets one photo from a Commons search (ActivityType.photo_search).
Needs outbound access to en.wikipedia.org and commons.wikimedia.org.
"""
import json
import re
import unicodedata
import urllib.parse
import urllib.request
from html import unescape

from django.core.management.base import BaseCommand

from directory.management.commands.seed_maldives import PHOTO_SEARCH
from directory.models import ActivityType, Island, IslandPhoto

USER_AGENT = "IslandStayMaldives/1.0 (local island guide; contact: admin@islandstay.mv)"
SKIP_WORDS = ("map", "location", "flag", "emblem", "logo", "locator", "seal", "coat_of_arms", "diagram", "chart")
WIDTH = 1920
GALLERY_SIZE = 6


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def strip_html(value):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", "", value or ""))).strip()


def plain(text):
    """Lower-case ASCII, so 'Malé' matches 'Male' in file names."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def usable(title, mime):
    name = title.lower()
    return mime in ("image/jpeg", "image/png", "image/webp") and not any(w in name for w in SKIP_WORDS)


def parse_info(page):
    info = (page.get("imageinfo") or [None])[0]
    if not info:
        return None
    meta = info.get("extmetadata", {})
    return {
        "title": page.get("title", ""),
        "url": info.get("thumburl") or info.get("url"),
        "mime": info.get("mime", ""),
        "width": info.get("width", 0),
        "page": info.get("descriptionurl", ""),
        "caption": strip_html(meta.get("ImageDescription", {}).get("value", ""))[:200],
        "author": strip_html(meta.get("Artist", {}).get("value", ""))[:200] or "Wikimedia Commons contributor",
        "license": strip_html(meta.get("LicenseShortName", {}).get("value", ""))[:60],
    }


IMAGEINFO = f"prop=imageinfo&iiprop=url|extmetadata|mime|size&iiurlwidth={WIDTH}"


def lead_image(title):
    """The Wikipedia article's lead image, with Commons metadata."""
    data = get_json(
        "https://en.wikipedia.org/w/api.php?action=query&format=json&prop=pageimages&piprop=name&redirects=1&titles="
        + urllib.parse.quote(title)
    )
    name = next((p.get("pageimage") for p in data.get("query", {}).get("pages", {}).values() if p.get("pageimage")), None)
    if not name:
        return None
    data = get_json(f"https://commons.wikimedia.org/w/api.php?action=query&format=json&{IMAGEINFO}&titles="
                    + urllib.parse.quote("File:" + name))
    for page in data.get("query", {}).get("pages", {}).values():
        info = parse_info(page)
        if info and usable(info["title"], info["mime"]):
            return info
    return None


def search(query, limit=20):
    """Commons file search, best match first."""
    data = get_json(
        "https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search&gsrnamespace=6"
        f"&gsrlimit={limit}&{IMAGEINFO}&gsrsearch=" + urllib.parse.quote(query + " filetype:bitmap")
    )
    pages = sorted(data.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
    results = []
    for page in pages:
        info = parse_info(page)
        if info and usable(info["title"], info["mime"]) and info["width"] >= 800:
            results.append(info)
    return results


class Command(BaseCommand):
    help = "Link freely licensed Wikimedia Commons photos to islands and experience types."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Look again even where a photo is already set")
        parser.add_argument("--island", help="Only this island (slug); skips experience types")
        parser.add_argument("--max-seconds", type=float, default=0,
                            help="Stop starting new work after this many seconds (for time-limited cron runs)")

    def handle(self, *args, **opts):
        islands = Island.objects.filter(is_published=True)
        if opts["island"]:
            islands = islands.filter(slug=opts["island"])
        found = 0
        import time

        started = time.monotonic()

        def out_of_time():
            return opts["max_seconds"] and time.monotonic() - started > opts["max_seconds"]

        for island in islands:
            if out_of_time():
                self.stdout.write("Time limit reached; the rest will be done on the next run.")
                break
            try:
                found += self.island_photos(island, opts["force"])
            except Exception as exc:  # network errors, unexpected responses
                self.stderr.write(f"  {island.name}: failed ({exc})")
        if not opts["island"]:
            for activity in ActivityType.objects.all():
                if activity.image_url and not opts["force"]:
                    continue
                if out_of_time():
                    break
                try:
                    query = activity.photo_search or PHOTO_SEARCH.get(activity.name, f"{activity.name} Maldives")
                    results = search(query, limit=10)
                except Exception as exc:
                    self.stderr.write(f"  {activity.name}: failed ({exc})")
                    continue
                if results:
                    r = results[0]
                    activity.image_url, activity.image_credit = r["url"], r["author"]
                    activity.image_license, activity.image_source_url = r["license"], r["page"]
                    activity.save()
                    found += 1
                    self.stdout.write(f"  {activity.name}: {r['title']}")
        self.stdout.write(self.style.SUCCESS(f"Linked {found} photo(s)."))

    def island_photos(self, island, force):
        needs_cover = force or not (island.cover_image or island.cover_image_url)
        needs_gallery = force or not island.photos.exists()
        if not (needs_cover or needs_gallery):
            return 0
        name = plain(island.name)
        candidates = [r for r in search(f"{island.name} Maldives") if name in plain(r["title"]) or name in plain(r["caption"])]
        added = 0
        if needs_cover:
            cover = lead_image(island.wikipedia_title) if island.wikipedia_title else None
            cover = cover or (candidates[0] if candidates else None)
            if cover:
                island.cover_image_url, island.cover_credit = cover["url"], cover["author"]
                island.cover_license, island.cover_source_url = cover["license"], cover["page"]
                island.save()
                added += 1
                self.stdout.write(f"  {island.name}: cover {cover['title']} ({cover['license']})")
            else:
                self.stdout.write(f"  {island.name}: no cover photo found")
        if needs_gallery:
            for i, r in enumerate(c for c in candidates if c["url"] != island.cover_image_url):
                if i >= GALLERY_SIZE:
                    break
                _, created = IslandPhoto.objects.get_or_create(island=island, image_url=r["url"], defaults=dict(
                    caption=r["caption"], credit=r["author"], license=r["license"], source_url=r["page"], order=i))
                added += created
        return added
