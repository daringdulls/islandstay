from django.urls import path

from . import partner_views, views

app_name = "links"
urlpatterns = [
    path("r/<slug:code>/", views.follow, name="follow"),
    path("dashboard/listings/<int:pk>/links/", views.manage, name="manage"),
    path("dashboard/links/<int:pk>/qr.<str:fmt>", views.qr, name="qr"),
    path("dashboard/listings/<int:pk>/partners/", partner_views.manage, name="partners"),
    path("partners/", partner_views.landing, name="partner_landing"),
    path("partners/join/", partner_views.join, name="partner_join"),
    path("partner/", partner_views.dashboard, name="partner_dashboard"),
    path("partner/profile/", partner_views.profile, name="partner_profile"),
]
