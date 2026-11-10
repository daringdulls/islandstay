"""Status tabs with counts and an 'active filters' bar above back-office lists (see BaseAdmin.list_tabs)."""
import urllib.parse

from django import template

register = template.Library()
SKIP = {"p", "o", "e", "_changelist_filters"}


@register.inclusion_tag("admin/_list_header.html", takes_context=True)
def list_header(context):
    request, cl = context["request"], context.get("cl")
    if cl is None:
        return {}
    admin = cl.model_admin
    current = {k: v for k, v in request.GET.items() if k not in SKIP}
    tabs = []
    base = admin.get_queryset(request)
    for label, params, q in getattr(admin, "list_tabs", None) or []:
        tabs.append({"label": label, "count": base.filter(q).count() if q is not None else base.count(),
                     "url": "?" + urllib.parse.urlencode(params), "active": current == params})
    filters = []
    for spec in cl.filter_specs:
        try:
            chosen = [c for c in spec.choices(cl) if c.get("selected") and c.get("query_string") is not None]
        except Exception:
            chosen = []
        for c in chosen:
            text = str(c.get("display", ""))
            if text and text.lower() not in ("all", "---------"):
                filters.append({"title": str(spec.title).capitalize(), "value": text})
    query = request.GET.get("q", "")
    is_tab = any(t["active"] for t in tabs)
    return {"tabs": tabs, "filters": [] if is_tab else filters, "query": query,
            "filtered": bool(current), "clear_url": "?", "result": cl.result_count, "total": cl.full_result_count,
            "noun": str(cl.opts.verbose_name_plural)}
