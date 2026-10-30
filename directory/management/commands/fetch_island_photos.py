"""Download a freely licensed cover photo for each island from Wikipedia / Wikimedia Commons.

    python manage.py fetch_island_photos              # islands without a cover photo
    python manage.py fetch_island_photos --force      # replace existing photos too
    python manage.py fetch_island_photos --island maafushi

Uses the island's `wikipedia_title` to find the article's lead image, then reads the author and
license from Commons so the photo can be credited on the site. Maps, flags and SVG diagrams are skipped.
Needs outbound access to en.wikipedia.org, commons.wikimedia.org and upload.wikimedia.org.
"""
import json
import re
import urllib.parse
import urllib.request
from html import unescape

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from directory.models import Island

USER_AGENT = "IslandStayMaldives/1.0 (island guide; contact: admin@islandstay.mv)"
SKIP_WORDS = ("map", "location", "flag", "emblem", "logo", "locator", "seal")


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def get_bytes(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def strip_html(value):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", "", value or ""))).strip()


def lead_image_file(title):
    """Return the Commons file name of an article's lead image, or None."""
    data = get_json(
        "https://en.wikipedia.org/w/api.php?action=query&format=json&prop=pageimages&piprop=name&redirects=1&titles="
        + urllib.parse.quote(title)
    )
    for page in data.get("query", {}).get("pages", {}).values():
        if page.get("pageimage"):
            return page["pageimage"]
    return None


def commons_info(filename):
    data = get_json(
        "https://commons.wikimedia.org/w/api.php?action=query&format=json&prop=imageinfo"
        "&iiprop=url|extmetadata|mime&iiurlwidth=1800&titles=" + urllib.parse.quote("File:" + filename)
    )
    for page in data.get("query", {}).get("pages", {}).values():
        info = (page.get("imageinfo") or [None])[0]
        if not info:
            continue
        meta = info.get("extmetadata", {})
        return {
            "url": info.get("thumburl") or info.get("url"),
            "mime": info.get("mime", ""),
            "page": info.get("descriptionurl", ""),
            "author": strip_html(meta.get("Artist", {}).get("value", ""))[:200],
            "license": strip_html(meta.get("LicenseShortName", {}).get("value", ""))[:60],
        }
    return None


class Command(BaseCommand):
    help = "Fetch freely licensed island cover photos from Wikimedia Commons."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Replace photos that already exist")
        parser.add_argument("--island", help="Only this island (slug)")

    def handle(self, *args, **opts):
        islands = Island.objects.exclude(wikipedia_title="")
        if opts["island"]:
            islands = islands.filter(slug=opts["island"])
        if not opts["force"]:
            islands = islands.filter(cover_image="")
        done = 0
        for island in islands:
            try:
                filename = lead_image_file(island.wikipedia_title)
                if not filename or filename.lower().endswith(".svg") or any(w in filename.lower() for w in SKIP_WORDS):
                    self.stdout.write(f"  {island.name}: no suitable lead photo ({filename or 'none'})")
                    continue
                info = commons_info(filename)
                if not info or not info["mime"].startswith("image/") or info["mime"] == "image/svg+xml":
                    self.stdout.write(f"  {island.name}: Commons has no usable image for {filename}")
                    continue
                content = get_bytes(info["url"])
            except Exception as exc:  # network errors, missing pages, bad JSON
                self.stderr.write(f"  {island.name}: failed ({exc})")
                continue
            ext = ".png" if info["mime"] == "image/png" else ".jpg"
            if island.cover_image:
                island.cover_image.delete(save=False)
            island.cover_image.save(f"{island.slug}{ext}", ContentFile(content), save=False)
            island.cover_credit = info["author"] or "Wikimedia Commons contributor"
            island.cover_license = info["license"]
            island.cover_source_url = info["page"]
            island.save()
            done += 1
            self.stdout.write(self.style.SUCCESS(f"  {island.name}: {filename} ({island.cover_license})"))
        self.stdout.write(f"Saved {done} photo(s).")
