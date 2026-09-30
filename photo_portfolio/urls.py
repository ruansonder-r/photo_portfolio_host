from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Photo Portfolio"
admin.site.site_title = "Photo Portfolio"
admin.site.index_title = "Manage galleries and client albums"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("album/", include("albums.urls")),
    path("", include("portfolio.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
