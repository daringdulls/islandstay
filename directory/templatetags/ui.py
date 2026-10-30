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
