from django.utils.safestring import mark_safe
from django import template
from django.templatetags.static import static
from django.utils.html import format_html

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
