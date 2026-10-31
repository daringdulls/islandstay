"""Show a setup checklist instead of the site while required hosting settings are missing."""
import os

from django.conf import settings
from django.http import HttpResponse
from django.utils.html import escape

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Finish setting up Island Stay</title>
<style>body{{font:16px/1.6 system-ui,sans-serif;background:#fff8ec;color:#122a31;margin:0;padding:48px 16px}}
main{{max-width:620px;margin:auto;background:#fff;border-radius:14px;padding:32px;box-shadow:0 6px 20px rgba(10,61,76,.1)}}
h1{{margin:0 0 8px;font-size:1.6rem}}li{{margin:12px 0}}b{{color:#0b6e8a}}p.small{{color:#4a6068;font-size:.9rem}}</style></head>
<body><main><h1>Almost there</h1><p>The site is deployed, but these settings are still missing:</p><ul>{items}</ul>
<p class="small">After adding them, redeploy (Deployments, then the ⋯ menu, then Redeploy) and reload this page.</p>
<h2 style="font-size:1rem;margin-top:24px">What this deployment can see</h2>
<table style="font-size:.9rem;border-collapse:collapse">{diag}</table>
<p class="small">Settings only reach a deployment if they're ticked for its environment and were saved before it was built.
Values are never shown.</p></main></body></html>"""


def diagnostics():
    """Which deployment this is and which settings it can see (names only, never values)."""
    env = os.environ
    db_vars = sorted(k for k in env if "DATABASE_URL" in k or "POSTGRES_URL" in k)
    rows = [
        ("Vercel environment", env.get("VERCEL_ENV", "not on Vercel")),
        ("Deployment address", env.get("VERCEL_URL", "–")),
        ("Production address", env.get("VERCEL_PROJECT_PRODUCTION_URL", "–")),
        ("Code version", (env.get("VERCEL_GIT_COMMIT_SHA") or "–")[:7]),
        ("Database variables found", ", ".join(db_vars) or "none"),
    ] + [(name, "set" if env.get(name) else "missing")
         for name in ("DJANGO_SECRET_KEY", "BLOB_READ_WRITE_TOKEN", "ADMIN_EMAIL", "ADMIN_PASSWORD", "CRON_SECRET")]
    return "".join(f"<tr><td style='padding:3px 16px 3px 0;color:#4a6068'>{escape(k)}</td><td><b>{escape(v)}</b></td></tr>"
                   for k, v in rows)


class SetupCheckMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        missing = getattr(settings, "SETUP_MISSING", [])
        if missing:
            items = "".join(f"<li><b>{escape(name)}</b><br>{escape(how)}</li>" for name, how in missing)
            return HttpResponse(PAGE.format(items=items, diag=diagnostics()), status=503)
        return self.get_response(request)
