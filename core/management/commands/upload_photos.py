"""Upload a local folder of photos straight from your camera exports.

    python manage.py upload_photos ~/Exports/Smith_Wedding --gallery "Smith Wedding"
    python manage.py upload_photos ~/Exports/Smith_Wedding --album "Smith Wedding" --date 2025-03-09
    python manage.py upload_photos ~/Exports/Best_Of --gallery "Featured" --unpublished --featured

Nothing passes through Google Drive, so the masters keep their original
resolution and the untouched file is what clients download.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core import ingest
from core.storage import StorageNotConfigured, photo_store


class Command(BaseCommand):
    help = "Upload a directory of images to Cloudinary and index them."

    def add_arguments(self, parser):
        parser.add_argument("directory", type=Path, help="Local folder containing the images")
        target = parser.add_mutually_exclusive_group(required=True)
        target.add_argument("--gallery", help="Public gallery title")
        target.add_argument("--album", help="Private client album name")
        parser.add_argument("--slug", default="", help="Gallery slug (default: slugified title)")
        parser.add_argument("--date", help="Album date, YYYY-MM-DD (default: today)")
        parser.add_argument(
            "--featured", action="store_true", help="Also show these in the homepage carousel"
        )
        parser.add_argument(
            "--unpublished",
            action="store_true",
            help="Create the gallery hidden (use with --featured for a carousel-only set)",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Delete photos already indexed for this target before uploading",
        )
        parser.add_argument(
            "--max-mb",
            type=float,
            default=10.0,
            help="Re-encode anything larger than this before upload "
            "(default 10, Cloudinary's free-plan image limit). 0 disables.",
        )
        parser.add_argument(
            "--max-edge",
            type=int,
            default=0,
            help="Cap the longest side in pixels before upload (default: unchanged)",
        )
        parser.add_argument("--dry-run", action="store_true", help="List what would be uploaded")

    def handle(self, *args, **options):
        directory: Path = options["directory"].expanduser()

        try:
            files = ingest.iter_image_files(directory)
        except NotADirectoryError as exc:
            raise CommandError(str(exc)) from exc
        if not files:
            raise CommandError(f"No images found in {directory}")

        if options["dry_run"]:
            self.stdout.write(f"Would upload {len(files)} image(s) from {directory}:")
            for path in files:
                self.stdout.write(f"  {path.name}  ({path.stat().st_size / 1_048_576:.1f} MB)")
            return

        if not photo_store.is_configured:
            raise CommandError(
                "Cloudinary is not configured. Set CLOUDINARY_URL in your .env first."
            )

        gallery = album = None
        if options["gallery"]:
            gallery, created = ingest.ensure_gallery(
                options["gallery"], slug=options["slug"], published=not options["unpublished"]
            )
            target_label = f"gallery '{gallery.title}' (/gallery/{gallery.slug}/)"
        else:
            date = None
            if options["date"]:
                try:
                    date = dt.date.fromisoformat(options["date"])
                except ValueError as exc:
                    raise CommandError("--date must be YYYY-MM-DD") from exc
            album, created = ingest.ensure_album(options["album"], date=date)
            target_label = f"album '{album.name}' (/album/{album.pk}/)"

        self.stdout.write(f"{'Created' if created else 'Using existing'} {target_label}")

        owner = gallery or album
        if options["replace"]:
            deleted, _ = owner.photos.all().delete()
            if deleted:
                self.stdout.write(self.style.WARNING(f"Removed {deleted} previously indexed photo(s)"))

        start = owner.photos.count()
        uploaded = failed = 0

        max_bytes = int(options["max_mb"] * 1024 * 1024) if options["max_mb"] else 0

        for offset, path in enumerate(files):
            label = f"[{offset + 1}/{len(files)}] {path.name}"
            source, is_temp, note = path, False, ""
            try:
                source, is_temp, note = ingest.prepare_for_upload(
                    path, max_bytes=max_bytes, max_edge=options["max_edge"]
                )
                photo = ingest.ingest(
                    str(source),
                    gallery=gallery,
                    album=album,
                    position=start + offset,
                    featured=options["featured"],
                    display_name=path.name,
                )
            except StorageNotConfigured as exc:
                raise CommandError(str(exc)) from exc
            except Exception as exc:  # one bad file must not abort the batch
                failed += 1
                self.stderr.write(self.style.ERROR(f"{label}  FAILED: {exc}"))
                continue
            finally:
                if is_temp and source != path:
                    Path(source).unlink(missing_ok=True)

            uploaded += 1
            suffix = f"  [fitted: {note}]" if note else ""
            self.stdout.write(f"{label}  ok  {photo.width}x{photo.height}{suffix}")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Uploaded {uploaded} photo(s)"))
        if failed:
            self.stdout.write(self.style.ERROR(f"{failed} failed"))
        if gallery:
            self.stdout.write(f"View at /gallery/{gallery.slug}/")
        else:
            self.stdout.write(f"Client link: /album/{album.pk}/")
