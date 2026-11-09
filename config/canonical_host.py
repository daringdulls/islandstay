"""Send visitors on the old vercel.app address to the site's own domain, so Google sees one site.
Switching between islandstaymv.com and www. is left to Vercel's domain settings, to avoid redirect loops."""
from django.conf import settings
from django.http import HttpResponsePermanentRedirect


class CanonicalHostMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        target = settings.CANONICAL_HOST
        if target and request.method in ("GET", "HEAD") and not request.path.startswith("/cron/"):
            host = request.get_host().split(":")[0].lower()
            if host in settings.LEGACY_HOSTS and host != target:
                return HttpResponsePermanentRedirect(f"https://{target}{request.get_full_path()}")
        return self.get_response(request)
