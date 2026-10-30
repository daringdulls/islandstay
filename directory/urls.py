from django.urls import path

from . import views

app_name = "directory"

urlpatterns = [
    path("", views.home, name="home"),
    path("search/", views.search, name="search"),
    path("islands/", views.island_list, name="island_list"),
    path("islands/<slug:slug>/", views.island_detail, name="island_detail"),
    path("atolls/", views.atoll_list, name="atoll_list"),
    path("atolls/<slug:slug>/", views.atoll_detail, name="atoll_detail"),
    path("stays/", views.stay_list, name="stay_list"),
    path("experiences/", views.service_list, name="service_list"),
    path("listing/<slug:slug>/", views.listing_detail, name="listing_detail"),
    path("request-sent/<str:ref>/", views.enquiry_sent, name="enquiry_sent"),
    path("list-your-business/", views.list_your_business, name="list_your_business"),
    path("how-it-works/", views.how_it_works, name="how_it_works"),
    path("suggest-island/", views.suggest_island, name="suggest_island"),
    # Owner dashboard
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/listings/new/", views.listing_create, name="listing_create"),
    path("dashboard/listings/<int:pk>/edit/", views.listing_edit, name="listing_edit"),
    path("dashboard/listings/<int:pk>/photos/", views.listing_photos, name="listing_photos"),
    path("dashboard/photos/<int:pk>/delete/", views.photo_delete, name="photo_delete"),
    path("dashboard/enquiries/", views.enquiry_list, name="enquiry_list"),
    path("dashboard/enquiries/<str:ref>/", views.enquiry_detail, name="enquiry_detail"),
]
