from django.contrib import admin
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html

from core.models import Photo

from .models import ClientAlbum


class AlbumPhotoInline(admin.TabularInline):
    model = Photo
    fk_name = "album"
    extra = 0
    fields = ["original_filename", "caption", "position"]
    readonly_fields = ["original_filename"]
    ordering = ["position"]


@admin.register(ClientAlbum)
class ClientAlbumAdmin(admin.ModelAdmin):
    list_display = ["name", "date", "num_photos", "is_active", "expires_at", "share_link"]
    list_filter = ["is_active", "date"]
    search_fields = ["name", "description"]
    readonly_fields = ["id", "created_at", "updated_at", "share_link"]
    date_hierarchy = "date"
    inlines = [AlbumPhotoInline]

    fieldsets = (
        (None, {"fields": ("name", "date", "description")}),
        ("Access", {
            "fields": ("is_active", "expires_at", "share_link"),
            "description": "The share link is the album's secret. Untick 'is active' to revoke it.",
        }),
        ("System", {"fields": ("id", "folder_name", "created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_num_photos=Count("photos"))

    @admin.display(description="Photos", ordering="_num_photos")
    def num_photos(self, obj):
        return obj._num_photos

    @admin.display(description="Client link")
    def share_link(self, obj):
        if not obj.pk:
            return "—"
        url = reverse("albums:album_detail", kwargs={"album_id": obj.pk})
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', url, url)
