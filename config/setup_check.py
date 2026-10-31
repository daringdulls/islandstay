"""Show a setup checklist instead of the site while required hosting settings are missing."""
from django.conf import settings
from django.http import HttpResponse
from django.utils.html import escape

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Finish setting up Island Stay</title>
<style>body{{font:16px/1.6 system-ui,sans-serif;background:#fff8ec;color:#122a31;margin:0;padding:48px 16px}}
main{{max-width:620px;margin:auto;background:#fff;border-radius:14px;padding:32px;box-shadow:0 6px 20px rgba(10,61,76,.1)}}
h1{{margin:0 0 8px;font-size:1.6rem}}li{{margin:12px 0}}b{{color:#0b6e8a}}p.small{{color:#4a6068;font-size:.9rem}}</style></head>
<body><main><h1>Almost there</h1><p>The site is deployed, but these settings are still missing:</p><ul>{items}</ul>
<p class="small">After adding them, redeploy (Deployments, then the ⋯ menu, then Redeploy) and reload this page.</p></main></body></html>"""


class SetupCheckMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        missing = getattr(settings, "SETUP_MISSING", [])
        if missing:
            items = "".join(f"<li><b>{escape(name)}</b><br>{escape(how)}</li>" for name, how in missing)
            return HttpResponse(PAGE.format(items=items), status=503)
        return self.get_response(request)
