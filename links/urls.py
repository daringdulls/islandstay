from django.urls import path

from . import views

app_name = "links"
urlpatterns = [
    path("r/<slug:code>/", views.follow, name="follow"),
    path("dashboard/listings/<int:pk>/links/", views.manage, name="manage"),
    path("dashboard/links/<int:pk>/qr.<str:fmt>", views.qr, name="qr"),
]
