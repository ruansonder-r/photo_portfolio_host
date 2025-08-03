from django.contrib import admin
from .models import ClientAlbum, Image


@admin.register(ClientAlbum)
class ClientAlbumAdmin(admin.ModelAdmin):
    list_display = ['name', 'date', 'folder_name', 'created_at']
    list_filter = ['date', 'created_at']
    search_fields = ['name', 'description', 'folder_name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'date')
        }),
        ('Google Drive Integration', {
            'fields': ('folder_name',)
        }),
        ('System Information', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = ['name', 'folder_name', 'parent_folder_name', 'downloaded_at', 'size']
    list_filter = ['folder_name', 'parent_folder_name', 'downloaded_at', 'mime_type']
    search_fields = ['name', 'google_drive_id', 'folder_name']
    readonly_fields = ['id', 'google_drive_id', 'downloaded_at', 'last_accessed']
    fieldsets = (
        ('Image Information', {
            'fields': ('name', 'mime_type', 'size', 'width', 'height')
        }),
        ('Storage Information', {
            'fields': ('google_drive_id', 'local_file_path', 'folder_name', 'parent_folder_name')
        }),
        ('System Information', {
            'fields': ('id', 'downloaded_at', 'last_accessed'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related()
