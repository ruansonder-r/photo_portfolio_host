"""Shared logic for getting photos into Cloudinary and into the index.

Used by both ``upload_photos`` (local files) and ``migrate_from_drive``
(one-time Google Drive import).
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from albums.models import ClientAlbum
from core.models import Photo
from core.storage import photo_store
from portfolio.models import Gallery

logger = logging.getLogger(__name__)

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".tif", ".tiff", ".heic", ".heif"}

# EXIF dates look like "2025:03:09 18:03:40"
_EXIF_DATE = re.compile(r"^(\d{4}):(\d{2}):(\d{2})[ T](\d{2}):(\d{2}):(\d{2})")


def parse_exif_datetime(value) -> dt.datetime | None:
    if not value or not isinstance(value, str):
        return None
    match = _EXIF_DATE.match(value.strip())
    if not match:
        return None
    try:
        naive = dt.datetime(*(int(part) for part in match.groups()))
    except ValueError:
        return None
    return timezone.make_aware(naive, timezone.get_default_timezone())


def iter_image_files(directory: Path) -> list[Path]:
    """Every image directly inside ``directory``, in stable filename order."""
    if not directory.is_dir():
        raise NotADirectoryError(f"{directory} is not a directory")
    files = [p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES]
    return sorted(files, key=lambda p: p.name.lower())


def ensure_gallery(title: str, *, slug: str = "", published: bool = True) -> tuple[Gallery, bool]:
    slug = slug or slugify(title)
    gallery, created = Gallery.objects.get_or_create(
        slug=slug, defaults={"title": title, "is_published": published}
    )
    return gallery, created


def ensure_album(name: str, *, date: dt.date | None = None) -> tuple[ClientAlbum, bool]:
    album = ClientAlbum.objects.filter(name=name).first()
    if album:
        return album, False
    return ClientAlbum.objects.create(name=name, date=date or timezone.now().date()), True


def cloudinary_folder(*, gallery: Gallery | None, album: ClientAlbum | None) -> str:
    if gallery is not None:
        return f"{settings.CLOUDINARY_PUBLIC_FOLDER}/{gallery.slug}"
    return f"{settings.CLOUDINARY_PRIVATE_FOLDER}/{album.pk}"


@transaction.atomic
def ingest(
    source,
    *,
    gallery: Gallery | None = None,
    album: ClientAlbum | None = None,
    position: int = 0,
    featured: bool = False,
    display_name: str = "",
) -> Photo:
    """Upload one image and record it. ``source`` is a path, URL or file object."""
    if (gallery is None) == (album is None):
        raise ValueError("Provide exactly one of gallery or album")

    private = album is not None
    asset = photo_store.upload(
        source, folder=cloudinary_folder(gallery=gallery, album=album), private=private
    )

    filename = display_name or asset.original_filename or Path(str(source)).name

    photo, _ = Photo.objects.update_or_create(
        public_id=asset.public_id,
        defaults={
            "version": asset.version,
            "format": asset.format,
            "width": asset.width,
            "height": asset.height,
            "bytes": asset.bytes,
            "original_filename": filename,
            "dominant_color": asset.dominant_color,
            "captured_at": parse_exif_datetime(asset.captured_at),
            "gallery": gallery,
            "album": album,
            "position": position,
            "is_featured": featured,
        },
    )

    # First photo in becomes the cover unless one was chosen explicitly.
    if gallery is not None and gallery.cover_id is None:
        gallery.cover = photo
        gallery.save(update_fields=["cover"])

    return photo
