import json
import re

from django.utils.safestring import mark_safe
from django import template
from django.templatetags.static import static
from django.utils.html import conditional_escape, format_html
from django.utils.text import slugify

register = template.Library()


@register.simple_tag
def icon(name, cls=""):
    """Inline reference to a symbol in static/img/icons.svg (Lucide icon set)."""
    return format_html(
        '<svg class="i {}" aria-hidden="true" focusable="false"><use href="{}#{}"></use></svg>',
        cls, static("img/icons.svg"), name,
    )


@register.simple_tag
def cowrie(cls=""):
    """The Island Stay cowrie, which marks verified local hosts."""
    return format_html('<img class="cowrie {}" src="{}" alt="" aria-hidden="true">', cls, static("img/brand/islandstay-cowrie-badge.svg"))


@register.simple_tag
def stars(n, total=5):
    """Official star rating as star symbols, e.g. 4 filled and 1 empty."""
    try:
        n = max(0, min(int(n), total))
    except (TypeError, ValueError):
        return ""
    star = '<svg class="star{}" viewBox="0 0 24 24" aria-hidden="true"><path d="M11.5 2.6a.6.6 0 0 1 1 0l2.7 5.6 6.1.9a.6.6 0 0 1 .3 1l-4.4 4.3 1 6.1a.6.6 0 0 1-.8.6L12 18.2l-5.5 2.9a.6.6 0 0 1-.8-.6l1-6.1-4.4-4.3a.6.6 0 0 1 .3-1l6.1-.9z"/></svg>'
    body = "".join(star.format("" if i < n else " off") for i in range(total))
    return format_html('<span class="stars" role="img" aria-label="{}-star rating" title="Officially rated {} star">{}</span>',
                       n, n, mark_safe(body))


@register.simple_tag
def page_banner(page):
    """Banner photo set in the back office for a page (url, credit), or ('', '')."""
    from directory.models import PageBanner

    return PageBanner.for_page(page, "")


_LINK = re.compile(r"\[([^\]]+)\]\(((?:https?://|/)[^)\s]*)\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*")


def _inline(text):
    text = conditional_escape(text)
    text = _LINK.sub(lambda m: '<a href="%s">%s</a>' % (m.group(2), m.group(1)), text)
    return _BOLD.sub(r"<strong>\1</strong>", text)


_PLACEHOLDER = re.compile(r"\[([^\]\n]{1,80})\](?!\()")


@register.filter
def guide_body(text, mode=""):
    """Turn the simple guide format (## headings, - bullets, blank-line paragraphs, [links](/x/)) into HTML."""
    out, para, items = [], [], []

    def flush():
        if para:
            out.append("<p>%s</p>" % _inline(" ".join(para)))
            para.clear()
        if items:
            out.append("<ul>%s</ul>" % "".join("<li>%s</li>" % _inline(i) for i in items))
            items.clear()

    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            flush()
        elif line.startswith("## "):
            flush()
            out.append('<h2 id="%s">%s</h2>' % (slugify(line[3:]), _inline(line[3:])))
        elif line.startswith(("- ", "• ")):
            if para:
                flush()
            items.append(line[2:])
        else:
            if items:
                flush()
            para.append(line)
    flush()
    html = "\n".join(out)
    if mode == "preview":
        html = _PLACEHOLDER.sub(r'<mark class="gd-todo">[\1]</mark>', html)
    return mark_safe(html)


@register.filter
def jsonld(data):
    """Safe JSON for a <script type="application/ld+json"> block."""
    return mark_safe(json.dumps(data, ensure_ascii=False).replace("<", "\\u003c"))


@register.filter
def thumb(url):
    """Smaller (960px) Wikimedia version of a photo link, for cards."""
    from ..models import card_size
    return card_size(url)
