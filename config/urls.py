from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "IslandStay Maldives — Admin"
admin.site.site_title = "IslandStay Admin"
admin.site.index_title = "Manage islands, listings & enquiries"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("", include("directory.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
