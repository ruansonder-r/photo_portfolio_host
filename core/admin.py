from django.contrib import admin
from django.utils.html import format_html

from .models import Photo


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ["preview", "original_filename", "owner", "dimensions", "is_featured", "position"]
    list_display_links = ["preview", "original_filename"]
    list_editable = ["is_featured", "position"]
    list_filter = ["is_featured", "gallery", "album", "format"]
    search_fields = ["original_filename", "public_id", "caption"]
    readonly_fields = ["id", "public_id", "version", "format", "width", "height", "bytes", "created_at", "large_preview"]
    list_select_related = ["gallery", "album"]

    fieldsets = (
        ("Preview", {"fields": ("large_preview",)}),
        ("Presentation", {"fields": ("caption", "is_featured", "position")}),
        ("Ownership", {"fields": ("gallery", "album")}),
        ("Source file", {
            "fields": ("id", "public_id", "version", "format", "width", "height", "bytes", "captured_at", "created_at"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="")
    def preview(self, obj):
        src = obj._url(120)
        if not src:
            return "—"
        return format_html(
            '<img src="{}" style="height:52px;width:78px;object-fit:cover;border-radius:4px" alt="">', src
        )

    @admin.display(description="Preview")
    def large_preview(self, obj):
        src = obj._url(600)
        if not src:
            return "Storage not configured"
        return format_html('<img src="{}" style="max-width:100%;border-radius:8px" alt="">', src)

    @admin.display(description="Owner")
    def owner(self, obj):
        return obj.gallery or obj.album or "—"

    @admin.display(description="Size")
    def dimensions(self, obj):
        return f"{obj.width}×{obj.height}" if obj.width else "—"
