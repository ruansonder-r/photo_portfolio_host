"""The photo index.

One row per image in the Cloudinary media library. Pages are rendered entirely
from these rows -- no external API call happens while serving a request, which
is what removed the multi-second Drive round-trips from every page load.
"""

from __future__ import annotations

import os
import uuid

from django.db import models

from core.storage import DISPLAY_WIDTHS, SIZES_FULL, SIZES_GRID, photo_store


class Photo(models.Model):
    """A single image, owned by exactly one Gallery or one ClientAlbum."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # --- Cloudinary identity ---
    public_id = models.CharField(max_length=300, unique=True)
    version = models.CharField(max_length=32, blank=True, help_text="Cache-busting version")
    format = models.CharField(max_length=12, blank=True)

    # --- Intrinsic dimensions, used to reserve layout space and cap srcset ---
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    bytes = models.BigIntegerField(default=0)

    original_filename = models.CharField(max_length=255, blank=True)
    caption = models.CharField(max_length=255, blank=True)
    dominant_color = models.CharField(
        max_length=9, blank=True, help_text="Hex tint shown while the image loads"
    )

    # --- Ownership: exactly one of these is set (enforced by CheckConstraint) ---
    gallery = models.ForeignKey(
        "portfolio.Gallery",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="photos",
    )
    album = models.ForeignKey(
        "albums.ClientAlbum",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="photos",
    )

    is_featured = models.BooleanField(
        default=False, help_text="Show this photo in the homepage carousel"
    )
    position = models.PositiveIntegerField(default=0)
    captured_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "original_filename"]
        indexes = [
            models.Index(fields=["gallery", "position"]),
            models.Index(fields=["album", "position"]),
            models.Index(fields=["is_featured"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(gallery__isnull=False, album__isnull=True)
                    | models.Q(gallery__isnull=True, album__isnull=False)
                ),
                name="photo_belongs_to_exactly_one_owner",
            )
        ]

    def __str__(self) -> str:
        return self.original_filename or self.public_id

    # -- Presentation -----------------------------------------------------

    @property
    def is_private(self) -> bool:
        """Album photos are delivered through signed, unguessable URLs."""
        return self.album_id is not None

    @property
    def alt(self) -> str:
        """Descriptive alternative text.

        Never falls back to the camera filename: "_MG_6316.jpg" is what a
        screen reader would read aloud and what Google Images would index.
        Set `caption` in the admin to override.
        """
        if self.caption:
            return self.caption
        owner = ""
        if self.gallery_id is not None:
            # An unpublished gallery is an internal grouping ("Featured"), not
            # something a reader or a search engine should be told about.
            if self.gallery.is_published:
                owner = self.gallery.title
        elif self.album_id is not None:
            owner = self.album.name
        where = os.environ.get("PHOTOGRAPHER_LOCATION", "")
        who = os.environ.get("PHOTOGRAPHER_NAME", "")
        parts = [p for p in (owner, f"photograph by {who}" if who else "", where) if p]
        return " — ".join(parts) if parts else "Photograph"

    @property
    def aspect_ratio(self) -> str:
        """CSS ``aspect-ratio`` value, so the grid reserves space before load."""
        if self.width and self.height:
            return f"{self.width} / {self.height}"
        return "3 / 2"

    @property
    def aspect_value(self) -> float:
        """width/height as a bare number, fed to CSS as --ar.

        Each tile's flex-basis is this times the row height, so a row of
        photos fills the width with only a hair of cropping.
        """
        if self.width and self.height:
            return round(self.width / self.height, 4)
        return 1.5

    @property
    def is_portrait(self) -> bool:
        return bool(self.height and self.width and self.height > self.width)

    @property
    def placeholder(self) -> str:
        return self.dominant_color or "#e8e6e1"

    def _url(self, width: int | None) -> str:
        # Never let an unconfigured store turn a page into a 500; the template
        # shows its empty state instead.
        if not photo_store.is_configured:
            return ""
        return photo_store.url(
            self.public_id, version=self.version, private=self.is_private, width=width
        )

    @property
    def thumb_src(self) -> str:
        return self._url(800)

    @property
    def full_src(self) -> str:
        return self._url(2400)

    @property
    def srcset(self) -> str:
        if not photo_store.is_configured:
            return ""
        return photo_store.srcset(
            self.public_id,
            version=self.version,
            private=self.is_private,
            native_width=self.width,
            widths=DISPLAY_WIDTHS,
        )

    @property
    def sizes_grid(self) -> str:
        return SIZES_GRID

    @property
    def sizes_full(self) -> str:
        return SIZES_FULL

    @property
    def social_src(self) -> str:
        """1200x630 JPEG used for link previews."""
        if not photo_store.is_configured:
            return ""
        return photo_store.social_url(
            self.public_id, version=self.version, private=self.is_private
        )

    @property
    def download_url(self) -> str:
        """Full-resolution master, as a download."""
        if not photo_store.is_configured:
            return ""
        return photo_store.original_url(
            self.public_id, version=self.version, private=self.is_private
        )

    @property
    def megapixels(self) -> float:
        return round((self.width * self.height) / 1_000_000, 1)
