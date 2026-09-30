"""Shared logic for getting photos into Cloudinary and into the index.

Used by both ``upload_photos`` (local files) and ``migrate_from_drive``
(one-time Google Drive import).
"""

from __future__ import annotations

import datetime as dt
import logging
import re
import tempfile
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


# Cloudinary rejects image uploads above this on the free plan.
DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024

# Quality ladder tried before giving up resolution.
_QUALITY_STEPS = (95, 92, 88, 84, 80, 75)


def prepare_for_upload(
    path: Path, *, max_bytes: int = DEFAULT_MAX_UPLOAD_BYTES, max_edge: int = 0
) -> tuple[Path, bool, str]:
    """Return an upload-ready copy of ``path``.

    Returns ``(path_to_upload, is_temporary, note)``. Resolution is given up
    only after re-encoding alone fails to get under ``max_bytes``, so a master
    keeps as many pixels as the plan allows.
    """
    from PIL import Image

    size = path.stat().st_size
    with Image.open(path) as probe:
        width, height = probe.size
        exif = probe.info.get("exif")

    too_big = max_bytes and size > max_bytes
    too_wide = max_edge and max(width, height) > max_edge
    if not (too_big or too_wide):
        return path, False, ""

    with Image.open(path) as im:
        im = im.convert("RGB")
        if too_wide:
            im.thumbnail((max_edge, max_edge), Image.LANCZOS)

        handle = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        handle.close()
        out = Path(handle.name)

        scale = 1.0
        while True:
            work = im
            if scale < 1.0:
                work = im.resize(
                    (max(1, int(im.width * scale)), max(1, int(im.height * scale))),
                    Image.LANCZOS,
                )
            for quality in _QUALITY_STEPS:
                save_kwargs = dict(quality=quality, optimize=True, progressive=True)
                if exif:
                    save_kwargs["exif"] = exif
                work.save(out, "JPEG", **save_kwargs)
                if not max_bytes or out.stat().st_size <= max_bytes:
                    note = (
                        f"{width}x{height} {size / 1048576:.1f}MB -> "
                        f"{work.width}x{work.height} {out.stat().st_size / 1048576:.1f}MB q{quality}"
                    )
                    return out, True, note
            scale *= 0.85
            if min(im.width, im.height) * scale < 800:
                note = f"could not fit under {max_bytes / 1048576:.0f}MB"
                return out, True, note


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
    # When `source` is a re-encoded temp file, use_filename would name the asset
    # after the tempfile (portfolio/featured/tmpcyg7isbe). Pin the public_id to
    # the photographer's own filename so the media library stays readable and
    # downloads arrive with a sensible name.
    explicit_id = ""
    if display_name:
        stem = Path(display_name).stem
        if stem and stem != Path(str(source)).stem:
            explicit_id = re.sub(r"[^A-Za-z0-9_\-]+", "_", stem) or stem

    asset = photo_store.upload(
        source,
        folder=cloudinary_folder(gallery=gallery, album=album),
        private=private,
        public_id=explicit_id,
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
