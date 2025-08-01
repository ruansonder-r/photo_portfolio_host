from django.contrib import admin
from .models import ClientAlbum


@admin.register(ClientAlbum)
class ClientAlbumAdmin(admin.ModelAdmin):
    list_display = ['title', 'date', 'folder_name', 'created_at']
    list_filter = ['date', 'created_at']
    search_fields = ['title', 'description', 'folder_name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'date')
        }),
        ('Google Drive Integration', {
            'fields': ('folder_name',)
        }),
        ('System Information', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
