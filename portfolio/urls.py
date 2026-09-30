from django.urls import path

from . import views

app_name = "portfolio"

urlpatterns = [
    path("", views.home, name="home"),
    path("contact/", views.contact, name="contact"),
    path("gallery/<slug:slug>/", views.gallery_detail, name="gallery_detail"),
]
