import django
from django.apps import apps

# Vercel's build inspects the URLconf before Django has started; start it here if needed.
if not apps.ready:
    django.setup()

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

admin.site.site_header = "Island Stay — Admin"
admin.site.site_title = "Island Stay Admin"
admin.site.index_title = "Dashboard"

from config.blob_storage import blob_proxy  # noqa: E402
from analytics.views import collect  # noqa: E402
from directory.admin_ui import ai_assist_view  # noqa: E402
from django.contrib.sitemaps.views import sitemap  # noqa: E402
from django.http import HttpResponse  # noqa: E402
from django.views.decorators.cache import cache_page  # noqa: E402
from directory.sitemaps import SITEMAPS  # noqa: E402


def robots_txt(request):
    lines = ["User-agent: *", "Allow: /",
             *[f"Disallow: {p}" for p in ("/admin/", "/dashboard/", "/accounts/", "/t/", "/saved/", "/request-sent/",
                                          "/review/", "/cron/", "/search/suggest/")],
             "", f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}"]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


urlpatterns = [
    path("media/blob/<path:path>", blob_proxy, name="blob_proxy"),
    path("t/", collect, name="track"),
    path("robots.txt", robots_txt, name="robots_txt"),
    path("sitemap.xml", cache_page(3600)(sitemap), {"sitemaps": SITEMAPS}, name="django.contrib.sitemaps.views.sitemap"),
    path("admin/ai-assist/", admin.site.admin_view(ai_assist_view), name="ai_assist"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("", include("directory.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif settings.SERVE_MEDIA:
    urlpatterns += [re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT})]
