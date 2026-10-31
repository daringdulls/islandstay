import functools
import re

from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

register = template.Library()


@functools.lru_cache(maxsize=1)
def _symbols():
    sprite = (settings.BASE_DIR / "static" / "img" / "icons.svg").read_text()
    return {m.group(1): m.group(2) for m in re.finditer(r'<symbol id="([\w-]+)" viewBox="0 0 24 24">(.*?)</symbol>', sprite, re.S)}


@register.simple_tag
def inline_icon(name):
    """The icon's paths inlined, so the design can be exported as an image."""
    body = _symbols().get(name) or _symbols().get("waves", "")
    return mark_safe(f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
                     f'stroke-linecap="round" stroke-linejoin="round">{body}</svg>')
