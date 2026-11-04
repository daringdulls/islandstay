"""Content blocks for travel guides: cleaning what the editor sends, turning blocks into plain text
(for search, reading time and the table of contents) and preparing them for the page templates."""
import re
from urllib.parse import parse_qs, urlparse

from django.utils.text import slugify

TYPES = {
    "rich_text", "heading", "image", "hero_image", "gallery", "grid", "image_text", "quote", "video",
    "embed", "cta", "stay", "experience", "island", "related", "facts",
}
# Hosts an "Interactive embed" block may load in an iframe.
EMBED_HOSTS = {
    "www.google.com", "google.com", "maps.google.com", "www.openstreetmap.org", "embed.windy.com",
    "www.youtube.com", "www.youtube-nocookie.com", "player.vimeo.com", "www.instagram.com",
    "open.spotify.com", "docs.google.com", "calendar.google.com", "www.tiktok.com", "datawrapper.dwcdn.net",
    "my.matterport.com", "kuula.co", "momento360.com",
}


def _s(v, n=600):
    return str(v or "").strip()[:n]


def _url(v):
    v = _s(v, 1000)
    return v if v.startswith(("https://", "http://", "/")) else ""


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _images(v):
    out = []
    for i in (v if isinstance(v, list) else [])[:40]:
        if isinstance(i, dict) and _url(i.get("url")):
            out.append({"url": _url(i.get("url")), "caption": _s(i.get("caption"), 240), "credit": _s(i.get("credit"), 160)})
    return out


def clean_blocks(raw):
    """Keep only known block types and fields, with safe values."""
    out = []
    for b in (raw if isinstance(raw, list) else [])[:120]:
        if not isinstance(b, dict) or b.get("type") not in TYPES:
            continue
        t = b["type"]
        c = {"type": t}
        if t == "rich_text":
            c["text"] = _s(b.get("text"), 30000)
        elif t == "heading":
            c.update(title=_s(b.get("title"), 160), intro=_s(b.get("intro"), 1200))
        elif t in ("image", "hero_image"):
            c.update(url=_url(b.get("url")), caption=_s(b.get("caption"), 300), credit=_s(b.get("credit"), 160), alt=_s(b.get("alt"), 200))
        elif t == "gallery":
            c.update(title=_s(b.get("title"), 160), images=_images(b.get("images")))
        elif t == "grid":
            c.update(columns="3" if str(b.get("columns")) == "3" else "2", images=_images(b.get("images")))
        elif t == "image_text":
            c.update(url=_url(b.get("url")), title=_s(b.get("title"), 160), text=_s(b.get("text"), 6000),
                     side="right" if b.get("side") == "right" else "left", caption=_s(b.get("caption"), 240))
        elif t == "quote":
            c.update(quote=_s(b.get("quote"), 800), author=_s(b.get("author"), 160))
        elif t == "video":
            c.update(url=_url(b.get("url")), caption=_s(b.get("caption"), 300))
        elif t == "embed":
            h = _int(b.get("height")) or 450
            c.update(url=_url(b.get("url")), caption=_s(b.get("caption"), 300), height=max(200, min(h, 1000)))
        elif t == "cta":
            c.update(title=_s(b.get("title"), 160), text=_s(b.get("text"), 600), button_label=_s(b.get("button_label"), 60),
                     button_url=_url(b.get("button_url")), style=b.get("style") if b.get("style") in ("dark", "light", "gold") else "dark")
        elif t in ("stay", "experience", "related"):
            c.update(title=_s(b.get("title"), 160), note=_s(b.get("note"), 800),
                     items=[i for i in (_int(x) for x in (b.get("items") or [])[:12]) if i])
        elif t == "island":
            c.update(island=_int(b.get("island")), note=_s(b.get("note"), 1500))
        elif t == "facts":
            rows = [{"label": _s(r.get("label"), 80), "value": _s(r.get("value"), 300)}
                    for r in (b.get("items") or [])[:30] if isinstance(r, dict) and (r.get("label") or r.get("value"))]
            c.update(title=_s(b.get("title"), 160), items=rows, note=_s(b.get("note"), 800))
        out.append(c)
    return out


def blocks_to_text(blocks):
    """Plain text version, in the guide's simple text format. Headings become '## ' lines."""
    parts = []
    for b in blocks:
        t = b.get("type")
        if t == "heading" and b.get("title"):
            parts.append("## " + b["title"] + ("\n\n" + b["intro"] if b.get("intro") else ""))
        elif t == "rich_text" and b.get("text"):
            parts.append(b["text"])
        elif t == "image_text":
            parts.append("\n\n".join(x for x in (b.get("title"), b.get("text")) if x))
        elif t == "quote" and b.get("quote"):
            parts.append(b["quote"] + (f" ({b['author']})" if b.get("author") else ""))
        elif t == "cta":
            line = " ".join(x for x in (b.get("title"), b.get("text")) if x)
            if b.get("button_url"):
                line += f" [{b.get('button_label') or 'More'}]({b['button_url']})"
            parts.append(line.strip())
        elif t == "facts":
            rows = [f"- **{r['label']}:** {r['value']}" for r in b.get("items", [])]
            parts.append("\n".join(([b["title"]] if b.get("title") else []) + rows + ([b["note"]] if b.get("note") else [])))
        elif t in ("stay", "experience", "related", "island", "gallery") and (b.get("note") or b.get("title")):
            parts.append(" ".join(x for x in (b.get("title"), b.get("note")) if x))
        elif t in ("image", "hero_image", "video", "embed") and b.get("caption"):
            parts.append(b["caption"])
    return "\n\n".join(p for p in parts if p.strip())


def first_photo(blocks):
    for b in blocks or []:
        if b.get("type") in ("hero_image", "image", "image_text") and b.get("url"):
            return b["url"]
        if b.get("type") in ("gallery", "grid") and b.get("images"):
            return b["images"][0]["url"]
    return ""


def video_src(url):
    """YouTube or Vimeo link -> privacy-friendly embed address."""
    try:
        u = urlparse(url)
    except ValueError:
        return ""
    host = (u.hostname or "").lower()
    vid = ""
    if host in ("youtu.be",):
        vid = u.path.strip("/").split("/")[0]
    elif host.endswith("youtube.com") or host.endswith("youtube-nocookie.com"):
        if u.path.startswith(("/shorts/", "/embed/", "/live/")):
            vid = u.path.split("/")[2] if len(u.path.split("/")) > 2 else ""
        else:
            vid = (parse_qs(u.query).get("v") or [""])[0]
    if vid and re.fullmatch(r"[\w-]{6,20}", vid):
        return f"https://www.youtube-nocookie.com/embed/{vid}"
    if host.endswith("vimeo.com"):
        m = re.search(r"/(\d{5,12})", u.path)
        if m:
            return f"https://player.vimeo.com/video/{m.group(1)}"
    return ""


def embed_src(url):
    try:
        u = urlparse(url)
    except ValueError:
        return ""
    if u.scheme == "https" and (u.hostname or "").lower() in EMBED_HOSTS:
        return url
    return ""


def resolve(blocks, guide=None):
    """Blocks ready for the template, grouped into segments so full-width images can span the page."""
    from .models import Guide, Island, Listing

    ids = {"l": set(), "i": set(), "g": set()}
    for b in blocks:
        if b["type"] in ("stay", "experience"):
            ids["l"].update(b.get("items", []))
        elif b["type"] == "island" and b.get("island"):
            ids["i"].add(b["island"])
        elif b["type"] == "related":
            ids["g"].update(b.get("items", []))
    listings = {l.pk: l for l in Listing.objects.filter(pk__in=ids["l"], status=Listing.STATUS_APPROVED).select_related("island", "island__atoll")}
    islands = {i.pk: i for i in Island.objects.filter(pk__in=ids["i"], is_published=True).select_related("atoll")}
    guides = {g.pk: g for g in Guide.objects.filter(pk__in=ids["g"], is_published=True).prefetch_related("islands")}
    segments, current = [], []
    for b in blocks:
        b = dict(b)
        t = b["type"]
        if t == "heading":
            b["anchor"] = slugify(b.get("title", ""))
        elif t in ("stay", "experience"):
            b["objects"] = [listings[i] for i in b.get("items", []) if i in listings]
        elif t == "island":
            b["object"] = islands.get(b.get("island"))
        elif t == "related":
            objs = [guides[i] for i in b.get("items", []) if i in guides]
            if not objs and guide is not None:
                qs = Guide.objects.filter(is_published=True, category=guide.category).prefetch_related("islands")
                if guide.pk:
                    qs = qs.exclude(pk=guide.pk)
                objs = list(qs[:3])
            b["objects"] = objs
        elif t == "video":
            b["src"] = video_src(b.get("url", ""))
        elif t == "embed":
            b["src"] = embed_src(b.get("url", ""))
        if t == "hero_image" and b.get("url"):
            if current:
                segments.append({"blocks": current})
                current = []
            segments.append({"bleed": b})
        else:
            current.append(b)
    if current:
        segments.append({"blocks": current})
    return segments
