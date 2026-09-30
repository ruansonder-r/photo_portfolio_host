from __future__ import annotations

import uuid

from django.db import models
from django.urls import reverse
from django.utils import timezone


class ClientAlbum(models.Model):
    """A private client delivery.

    The UUID primary key is the share secret -- it is the whole URL. Photos in
    an album are uploaded with Cloudinary's ``authenticated`` delivery type, so
    even someone holding a raw public_id cannot fetch them without a signature.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    date = models.DateField()
    description = models.TextField(blank=True)

    # Optional link to the billing customer. A ClientAlbum is identified by
    # its `name` -- "Smith Wedding" is a shoot, not a customer -- so this is
    # nullable and nothing reads it unless it is set. It exists so a client's
    # shoots and their invoices can be seen together.
    client = models.ForeignKey(
        "billing.Client",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="albums",
        help_text="Optional. Links this shoot to a billing client.",
    )

    is_active = models.BooleanField(
        default=True, help_text="Untick to revoke the client's link immediately"
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Optional. After this moment the link stops working.",
    )

    # Retained so `migrate_from_drive` can map an existing Drive subfolder onto
    # the album. Not used to serve anything.
    folder_name = models.CharField(
        max_length=200, blank=True, null=True, help_text="Legacy Google Drive subfolder"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self) -> str:
        return f"{self.name} ({self.date:%Y-%m-%d})"

    def get_absolute_url(self) -> str:
        return reverse("albums:album_detail", kwargs={"album_id": self.id})

    @property
    def is_available(self) -> bool:
        if not self.is_active:
            return False
        return not (self.expires_at and self.expires_at <= timezone.now())

    @property
    def cover_photo(self):
        return next(iter(self.photos.all()), None)

    @property
    def photo_count(self) -> int:
        return self.photos.count()
