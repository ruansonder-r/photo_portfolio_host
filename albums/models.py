from django.db import models
from django.contrib.auth.models import User
import uuid
import os


class ClientAlbum(models.Model):
    """Model for storing client album information"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    date = models.DateField()
    description = models.TextField(blank=True)
    folder_name = models.CharField(max_length=200, blank=True, null=True, help_text="Google Drive subfolder name")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.name} - {self.date}"


class Image(models.Model):
    """Model for storing downloaded image metadata and local file paths"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    google_drive_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)
    local_file_path = models.CharField(max_length=500)
    folder_name = models.CharField(max_length=200)  # Google Drive folder name
    parent_folder_name = models.CharField(max_length=200, blank=True, null=True)  # Parent folder if nested
    size = models.BigIntegerField(default=0)
    width = models.IntegerField(default=0)
    height = models.IntegerField(default=0)
    downloaded_at = models.DateTimeField(auto_now_add=True)
    last_accessed = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['google_drive_id']),
            models.Index(fields=['folder_name']),
            models.Index(fields=['parent_folder_name']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.folder_name})"
    
    @property
    def local_url(self):
        """Return the local URL for the image"""
        if self.local_file_path and os.path.exists(self.local_file_path):
            return f"/media/images/{os.path.basename(self.local_file_path)}"
        return None
    
    def delete_local_file(self):
        """Delete the local file if it exists"""
        if self.local_file_path and os.path.exists(self.local_file_path):
            try:
                os.remove(self.local_file_path)
                return True
            except OSError:
                return False
        return False
