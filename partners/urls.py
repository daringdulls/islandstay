from django.urls import path

from . import views

app_name = "partners"
urlpatterns = [
    path("go/s/<int:pk>/", views.go_sponsor, name="go_sponsor"),
    path("go/<slug:slug>/", views.go_affiliate, name="go_affiliate"),
    path("advertise/", views.advertise, name="advertise"),
    path("advertise/thanks/", views.advertise_thanks, name="advertise_thanks"),
]
