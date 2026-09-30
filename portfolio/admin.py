from django.contrib import admin
from django.db.models import Count

from core.models import Photo

from .models import Gallery


class PhotoInline(admin.TabularInline):
    model = Photo
    fk_name = "gallery"
    extra = 0
    fields = ["original_filename", "caption", "is_featured", "position"]
    readonly_fields = ["original_filename"]
    ordering = ["position"]
    show_change_link = True


@admin.register(Gallery)
class GalleryAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "num_photos", "shot_on", "is_published", "position"]
    list_editable = ["is_published", "position"]
    list_filter = ["is_published"]
    search_fields = ["title", "slug", "description"]
    prepopulated_fields = {"slug": ("title",)}
    inlines = [PhotoInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_num_photos=Count("photos"))

    @admin.display(description="Photos", ordering="_num_photos")
    def num_photos(self, obj):
        return obj._num_photos

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Only offer this gallery's own photos as its cover.
        if db_field.name == "cover":
            gallery_id = request.resolver_match.kwargs.get("object_id") if request.resolver_match else None
            kwargs["queryset"] = Photo.objects.filter(gallery_id=gallery_id) if gallery_id else Photo.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
