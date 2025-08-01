from django.urls import path
from . import views

app_name = 'albums'

urlpatterns = [
    path('<uuid:album_id>/', views.album_detail, name='album_detail'),
    path('<uuid:album_id>/download/<str:image_id>/', views.download_image, name='download_image'),
    path('<uuid:album_id>/download-zip/', views.download_album_zip, name='download_album_zip'),
    path('admin/list/', views.admin_album_list, name='admin_list'),
    path('admin/generate-link/<uuid:album_id>/', views.generate_album_link, name='generate_link'),
] 
