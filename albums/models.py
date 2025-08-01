from django.db import models
import uuid


class ClientAlbum(models.Model):
    """Model for private client albums"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date = models.DateField()
    folder_name = models.CharField(max_length=200, help_text="Google Drive subfolder name")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.title} - {self.date}"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('albums:album_detail', kwargs={'album_id': self.id})
