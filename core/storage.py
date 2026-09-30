"""Image hosting seam.

Everything the site knows about where photos live is in this module. Views and
templates never import ``cloudinary`` -- they call ``photo_store``. Swapping to
ImageKit, S3 or anything else means writing one new class with the same methods.

Why this replaced Google Drive
------------------------------
Drive serves image bytes with ``Cross-Origin-Resource-Policy: same-site`` and
``Content-Disposition: attachment``, and returns 403 when the request carries a
cross-site ``Referer``. Browsers therefore refuse to render Drive files in an
``<img>`` on another domain, no matter which URL form is used. It is not a
misconfiguration; Google enforces it deliberately.

Performance note
----------------
Every URL below is built by local string formatting and HMAC signing. Nothing
in this module makes a network call during request handling -- that is what
keeps page rendering to a single database query.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

import cloudinary
import cloudinary.uploader
import cloudinary.utils
from django.conf import settings

logger = logging.getLogger(__name__)


# Widths offered to the browser through srcset. A phone picks 400/800, a
# laptop 1200/1600, a 5K display 2400 -- instead of every device downloading
# the 14 MB original, which is what the Drive setup did.
DISPLAY_WIDTHS: tuple[int, ...] = (400, 800, 1200, 1600, 2400)

# Rendered at upload time so the first visitor never waits on a cold transform.
EAGER_WIDTHS: tuple[int, ...] = (800, 1600)

# Tells the browser how wide the image will actually be drawn, so it can pick
# the right srcset entry before CSS has been applied.
SIZES_GRID = "(max-width: 700px) 100vw, (max-width: 1100px) 50vw, 33vw"
SIZES_FULL = "100vw"

PUBLIC_DELIVERY_TYPE = "upload"
PRIVATE_DELIVERY_TYPE = "authenticated"


class StorageNotConfigured(RuntimeError):
    """Raised when an operation needs Cloudinary credentials that are absent."""


@dataclass(frozen=True)
class UploadedAsset:
    """The subset of an upload response the database records."""

    public_id: str
    version: str
    format: str
    width: int
    height: int
    bytes: int
    original_filename: str
    dominant_color: str = ""
    captured_at: Any = None
    raw: dict = field(default_factory=dict, repr=False)


def _configure() -> bool:
    """Idempotently configure the SDK. Returns whether credentials are present."""
    if cloudinary.config().cloud_name:
        return True

    # CLOUDINARY_URL is the single-variable form and the SDK reads it itself.
    if os.environ.get("CLOUDINARY_URL"):
        cloudinary.config(secure=True)
    elif settings.CLOUDINARY_CLOUD_NAME:
        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
            secure=True,
        )
    return bool(cloudinary.config().cloud_name)


def _transformation(width: int | None, *, quality: str = "auto:good") -> dict:
    opts: dict = {"quality": quality, "fetch_format": "auto"}
    if width:
        # ``limit`` never upscales and never crops, so compositions are
        # preserved -- important for a portfolio.
        opts.update(width=width, crop="limit")
    return opts


class CloudinaryPhotoStore:
    """Cloudinary-backed implementation of the photo store."""

    @property
    def is_configured(self) -> bool:
        return _configure()

    def _require(self) -> None:
        if not self.is_configured:
            raise StorageNotConfigured(
                "Cloudinary is not configured. Set CLOUDINARY_URL (or "
                "CLOUDINARY_CLOUD_NAME / _API_KEY / _API_SECRET) in the environment."
            )

    # -- URL building -----------------------------------------------------

    def _base_options(self, *, version: str, private: bool) -> dict:
        opts: dict = {
            "secure": True,
            "resource_type": "image",
            "type": PRIVATE_DELIVERY_TYPE if private else PUBLIC_DELIVERY_TYPE,
        }
        if version:
            opts["version"] = version
        if private:
            # Signed delivery: the signature is derived from the public_id and
            # transformation, so the URL cannot be guessed or altered.
            opts["sign_url"] = True
            token_key = os.environ.get("CLOUDINARY_AUTH_TOKEN_KEY", "")
            if token_key:
                # Optional, and only available on plans with token-based auth:
                # adds a genuine expiry on top of the signature.
                opts["auth_token"] = {
                    "key": token_key,
                    "duration": settings.PRIVATE_URL_TTL_SECONDS,
                }
        return opts

    def url(
        self,
        public_id: str,
        *,
        version: str = "",
        private: bool = False,
        width: int | None = 1600,
    ) -> str:
        """URL for a single display rendition."""
        self._require()
        opts = self._base_options(version=version, private=private)
        opts.update(_transformation(width))
        return cloudinary.utils.cloudinary_url(public_id, **opts)[0]

    def srcset(
        self,
        public_id: str,
        *,
        version: str = "",
        private: bool = False,
        native_width: int = 0,
        widths: Sequence[int] = DISPLAY_WIDTHS,
    ) -> str:
        """A ``srcset`` string, skipping widths larger than the original."""
        self._require()
        usable = [w for w in widths if not native_width or w <= native_width]
        if not usable:
            usable = [min(widths)]
        parts = []
        for width in usable:
            opts = self._base_options(version=version, private=private)
            opts.update(_transformation(width))
            parts.append(f"{cloudinary.utils.cloudinary_url(public_id, **opts)[0]} {width}w")
        return ", ".join(parts)

    def original_url(self, public_id: str, *, version: str = "", private: bool = False) -> str:
        """Untouched full-resolution master, forced to download rather than display."""
        self._require()
        opts = self._base_options(version=version, private=private)
        opts["flags"] = "attachment"
        return cloudinary.utils.cloudinary_url(public_id, **opts)[0]

    def archive_url(self, public_ids: Iterable[str], *, filename: str, private: bool = True) -> str:
        """Signed URL that makes Cloudinary build a ZIP of the given photos.

        The archive is assembled on Cloudinary's side and streamed straight to
        the client, so a 400 MB album never passes through the web process --
        which is what made the previous implementation impossible on a 30
        second serverless function.
        """
        self._require()
        ids = list(public_ids)
        if not ids:
            raise ValueError("archive_url() needs at least one public_id")
        return cloudinary.utils.download_zip_url(
            public_ids=ids,
            resource_type="image",
            type=PRIVATE_DELIVERY_TYPE if private else PUBLIC_DELIVERY_TYPE,
            target_public_id=filename,
            flatten_folders=True,
            use_original_filename=True,
            allow_missing=True,
            expires_at=int(time.time()) + settings.PRIVATE_URL_TTL_SECONDS,
        )

    # -- Mutation ---------------------------------------------------------

    def upload(self, source: str, *, folder: str, private: bool, public_id: str = "") -> UploadedAsset:
        """Upload one master image and pre-render its common derivatives."""
        self._require()
        options: dict = {
            "folder": folder,
            "resource_type": "image",
            "type": PRIVATE_DELIVERY_TYPE if private else PUBLIC_DELIVERY_TYPE,
            "overwrite": True,
            "invalidate": True,
            # Keep the photographer's filename in the public_id so downloads
            # and the media library stay recognisable.
            "use_filename": True,
            "unique_filename": False,
            "colors": True,          # dominant colour -> placeholder tint
            "image_metadata": True,  # EXIF, for capture date
            # This is the "pre-generate on upload" step: these renditions exist
            # before the first visitor asks for them.
            "eager": [_transformation(w) for w in EAGER_WIDTHS],
            "eager_async": False,
        }
        if public_id:
            options["public_id"] = public_id

        result = cloudinary.uploader.upload(source, **options)
        return self._to_asset(result)

    def delete(self, public_id: str, *, private: bool) -> None:
        self._require()
        cloudinary.uploader.destroy(
            public_id,
            resource_type="image",
            type=PRIVATE_DELIVERY_TYPE if private else PUBLIC_DELIVERY_TYPE,
            invalidate=True,
        )

    @staticmethod
    def _to_asset(result: dict) -> UploadedAsset:
        colors = result.get("colors") or []
        dominant = colors[0][0] if colors and isinstance(colors[0], (list, tuple)) else ""

        captured_at = None
        metadata = result.get("image_metadata") or {}
        for key in ("DateTimeOriginal", "DateTime", "CreateDate"):
            if metadata.get(key):
                captured_at = metadata[key]
                break

        return UploadedAsset(
            public_id=result["public_id"],
            version=str(result.get("version", "")),
            format=result.get("format", ""),
            width=int(result.get("width", 0)),
            height=int(result.get("height", 0)),
            bytes=int(result.get("bytes", 0)),
            original_filename=result.get("original_filename", ""),
            dominant_color=dominant if isinstance(dominant, str) else "",
            captured_at=captured_at,
            raw=result,
        )


photo_store = CloudinaryPhotoStore()
