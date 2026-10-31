"""Show administrators what went wrong when a page fails, instead of a bare "Server Error (500)".

Only superusers see the details; everyone else gets the normal error page. The full traceback is
still written to the server log.
"""
import logging
import traceback

from django.http import HttpResponse
from django.utils.html import escape

log = logging.getLogger("django.request")


class AdminErrorDetailsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated and user.is_superuser):
            return None  # normal 500 page for everyone else
        log.error("Internal Server Error: %s", request.path, exc_info=exception)
        frames = traceback.format_exception(type(exception), exception, exception.__traceback__)
        detail = "".join(frames)[-6000:]
        html = (
            "<!doctype html><meta charset='utf-8'><title>Error details</title>"
            "<body style='font:15px/1.5 system-ui,sans-serif;background:#fff8ec;color:#122a31;padding:32px'>"
            "<h1 style='font-size:1.4rem'>Something went wrong</h1>"
            f"<p><b>{escape(type(exception).__name__)}:</b> {escape(str(exception))}</p>"
            "<p style='color:#4a6068'>You're seeing this because you're an administrator. "
            "Send a screenshot of this page to whoever maintains the site.</p>"
            f"<pre style='white-space:pre-wrap;background:#fff;padding:16px;border-radius:12px;font-size:12px'>{escape(detail)}</pre>"
            "</body>"
        )
        return HttpResponse(html, status=500)
