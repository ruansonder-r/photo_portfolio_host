from django.urls import path

from . import views

app_name = "albums"

urlpatterns = [
    # Literal prefixes first so they are never shadowed by the UUID pattern.
    path("manage/", views.admin_album_list, name="admin_list"),
    path("manage/<uuid:album_id>/link/", views.generate_album_link, name="generate_link"),
    path("<uuid:album_id>/", views.album_detail, name="album_detail"),
    path("<uuid:album_id>/photo/<uuid:photo_id>/", views.download_photo, name="download_photo"),
    path("<uuid:album_id>/zip/", views.download_album_zip, name="download_album_zip"),
]
