"""One-time import of the existing Google Drive library into Cloudinary.

    python manage.py migrate_from_drive --dry-run
    python manage.py migrate_from_drive
    python manage.py migrate_from_drive --only "Matric Farewell"

Drive stays the source during the import only. Once this has run, the site
never contacts Drive again -- it cannot, because Drive refuses to serve images
cross-origin (CORP: same-site, and 403 on a cross-site Referer).

Folder mapping:
    Public_Portfolio/public/*   -> homepage carousel (hidden "featured" gallery)
    Public_Portfolio/<Name>/*   -> public gallery "<Name>"
    Private_Albums/<Name>/*     -> private client album "<Name>"
"""

from __future__ import annotations

import io
import json
import os
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core import ingest
from core.storage import photo_store

PUBLIC_ROOT = "Public_Portfolio"
PRIVATE_ROOT = "Private_Albums"
CAROUSEL_FOLDER = "public"
FOLDER_MIME = "application/vnd.google-apps.folder"


class Command(BaseCommand):
    help = "Copy photos from Google Drive into Cloudinary, then index them."

    def add_arguments(self, parser):
        parser.add_argument("--only", help="Import just this Drive subfolder")
        parser.add_argument("--skip-private", action="store_true", help="Public galleries only")
        parser.add_argument("--dry-run", action="store_true", help="Show the plan, change nothing")
        parser.add_argument("--limit", type=int, default=0, help="Stop after N photos (for testing)")

    # -- Drive access ------------------------------------------------------

    def _drive(self):
        # Optional dependency: kept out of requirements.txt because
        # google-api-python-client is ~102 MB and would blow Vercel's function
        # size limit, while this command only ever runs locally.
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise CommandError(
                "Google API libraries are not installed. They are intentionally "
                "excluded from requirements.txt to keep the deployed function small.\n"
                "Install them for this one-time import with:\n"
                "    pip install -r requirements-migrate.txt"
            ) from exc

        raw = settings.GOOGLE_DRIVE_CREDENTIALS
        path = settings.GOOGLE_DRIVE_CREDENTIALS_FILE

        if raw:
            info = json.loads(raw)
            creds = service_account.Credentials.from_service_account_info(
                info, scopes=["https://www.googleapis.com/auth/drive.readonly"]
            )
        elif path and os.path.exists(path):
            creds = service_account.Credentials.from_service_account_file(
                path, scopes=["https://www.googleapis.com/auth/drive.readonly"]
            )
        else:
            raise CommandError(
                "Google Drive credentials not found. Set GOOGLE_DRIVE_CREDENTIALS (the JSON "
                "itself) or GOOGLE_DRIVE_CREDENTIALS_FILE (a path) to run this import."
            )
        return build("drive", "v3", credentials=creds, cache_discovery=False)

    def _folder_id(self, service, name, parent=None):
        query = f"name = '{name}' and mimeType = '{FOLDER_MIME}' and trashed = false"
        if parent:
            query += f" and '{parent}' in parents"
        files = service.files().list(q=query, spaces="drive", fields="files(id,name)").execute()
        found = files.get("files", [])
        return found[0]["id"] if found else None

    def _children(self, service, parent, *, folders):
        """All children of a folder, following pagination."""
        mime = "=" if folders else "!="
        query = f"'{parent}' in parents and mimeType {mime} '{FOLDER_MIME}' and trashed = false"
        results, token = [], None
        while True:
            response = (
                service.files()
                .list(
                    q=query,
                    spaces="drive",
                    fields="nextPageToken, files(id,name,mimeType,size)",
                    orderBy="name",
                    pageSize=1000,
                    pageToken=token,
                )
                .execute()
            )
            results.extend(response.get("files", []))
            token = response.get("nextPageToken")
            if not token:
                return results

    def _download(self, service, file_id, suffix):
        from googleapiclient.http import MediaIoBaseDownload

        handle = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        downloader = MediaIoBaseDownload(handle, service.files().get_media(fileId=file_id))
        done = False
        while not done:
            _, done = downloader.next_chunk()
        handle.close()
        return Path(handle.name)

    # -- Main --------------------------------------------------------------

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if not dry_run and not photo_store.is_configured:
            raise CommandError("Cloudinary is not configured. Set CLOUDINARY_URL first.")

        service = self._drive()
        self.imported = 0
        self.limit = options["limit"]

        public_root = self._folder_id(service, PUBLIC_ROOT)
        if public_root:
            for folder in self._children(service, public_root, folders=True):
                if options["only"] and folder["name"] != options["only"]:
                    continue
                is_carousel = folder["name"] == CAROUSEL_FOLDER
                self._import_gallery(service, folder, carousel=is_carousel, dry_run=dry_run)
        else:
            self.stderr.write(self.style.WARNING(f"Drive folder '{PUBLIC_ROOT}' not found"))

        if not options["skip_private"]:
            private_root = self._folder_id(service, PRIVATE_ROOT)
            if private_root:
                for folder in self._children(service, private_root, folders=True):
                    if options["only"] and folder["name"] != options["only"]:
                        continue
                    self._import_album(service, folder, dry_run=dry_run)
            else:
                self.stderr.write(self.style.WARNING(f"Drive folder '{PRIVATE_ROOT}' not found"))

        self.stdout.write("")
        verb = "Would import" if dry_run else "Imported"
        self.stdout.write(self.style.SUCCESS(f"{verb} {self.imported} photo(s)"))

    def _import_gallery(self, service, folder, *, carousel, dry_run):
        files = [f for f in self._children(service, folder["id"], folders=False)
                 if f.get("mimeType", "").startswith("image/")]
        if not files:
            return

        title = "Featured" if carousel else folder["name"]
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(f"{title}  ({len(files)} photos)"))
        if dry_run:
            self.imported += len(files)
            return

        gallery, _ = ingest.ensure_gallery(title, published=not carousel)
        self._copy(service, files, gallery=gallery, featured=carousel)

    def _import_album(self, service, folder, *, dry_run):
        files = [f for f in self._children(service, folder["id"], folders=False)
                 if f.get("mimeType", "").startswith("image/")]
        if not files:
            return

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(f"[private] {folder['name']}  ({len(files)} photos)"))
        if dry_run:
            self.imported += len(files)
            return

        album, _ = ingest.ensure_album(folder["name"])
        album.folder_name = folder["name"]
        album.save(update_fields=["folder_name"])
        self._copy(service, files, album=album)

    def _copy(self, service, files, *, gallery=None, album=None, featured=False):
        owner = gallery or album
        start = owner.photos.count()

        for offset, meta in enumerate(files):
            if self.limit and self.imported >= self.limit:
                self.stdout.write(self.style.WARNING("Reached --limit, stopping"))
                return

            name = meta["name"]
            temp_path = None
            try:
                temp_path = self._download(service, meta["id"], Path(name).suffix or ".jpg")
                ingest.ingest(
                    str(temp_path),
                    gallery=gallery,
                    album=album,
                    position=start + offset,
                    featured=featured,
                    display_name=name,
                )
                self.imported += 1
                self.stdout.write(f"  [{offset + 1}/{len(files)}] {name}  ok")
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"  [{offset + 1}/{len(files)}] {name}  FAILED: {exc}"))
            finally:
                if temp_path and temp_path.exists():
                    temp_path.unlink(missing_ok=True)
