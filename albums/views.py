import logging

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import never_cache

from core.auth import is_admin_user
from core.storage import StorageNotConfigured, photo_store

from .models import ClientAlbum

logger = logging.getLogger(__name__)


def _get_available_album(album_id) -> ClientAlbum:
    """Fetch an album, treating revoked and expired links as missing.

    404 rather than 403: a revoked link should not confirm that the album ever
    existed.
    """
    album = get_object_or_404(ClientAlbum, id=album_id)
    if not album.is_available:
        raise Http404("This album link is no longer active.")
    return album


# Private album pages embed signed URLs and must never be stored by a CDN,
# a proxy, or the browser's back/forward cache.
@never_cache
def album_detail(request, album_id):
    album = _get_available_album(album_id)
    photos = list(album.photos.select_related("album"))
    return render(
        request,
        "albums/album_detail.html",
        {
            "album": album,
            "photos": photos,
            "page_title": f"{album.name} — Private album",
            # Per-photo downloads route through our view so a revoked album
            # stops working immediately, rather than handing out raw CDN URLs.
            "download_url_base": reverse(
                "albums:album_detail", kwargs={"album_id": album.pk}
            ) + "photo/",
        },
    )


@never_cache
def download_photo(request, album_id, photo_id):
    """Redirect to the signed full-resolution master.

    The bytes travel straight from the CDN to the client, so the web process
    never buffers a 14 MB file.
    """
    album = _get_available_album(album_id)
    photo = get_object_or_404(album.photos, id=photo_id)
    url = photo.download_url
    if not url:
        raise Http404("This photo is not available for download.")
    return HttpResponseRedirect(url)


@never_cache
def download_album_zip(request, album_id):
    """Redirect to a Cloudinary-generated ZIP of the whole album.

    Replaces the previous implementation, which wrote empty strings into the
    archive whenever no local copy existed -- clients received a ZIP full of
    0-byte files.
    """
    album = _get_available_album(album_id)
    public_ids = list(album.photos.values_list("public_id", flat=True))
    if not public_ids:
        raise Http404("This album has no photos yet.")

    safe_name = "".join(c if c.isalnum() or c in "-_" else "-" for c in album.name).strip("-")
    try:
        url = photo_store.archive_url(
            public_ids, filename=safe_name or "album", private=True
        )
    except StorageNotConfigured:
        logger.exception("ZIP requested for album %s but storage is not configured", album.pk)
        raise Http404("Downloads are temporarily unavailable.")
    return HttpResponseRedirect(url)


@login_required
@user_passes_test(is_admin_user)
def admin_album_list(request):
    albums = ClientAlbum.objects.all().prefetch_related("photos")
    for album in albums:
        album.share_url = request.build_absolute_uri(album.get_absolute_url())
    return render(
        request, "albums/admin_list.html",
        {"albums": albums, "page_title": "Client albums — admin"},
    )


@login_required
@user_passes_test(is_admin_user)
def generate_album_link(request, album_id):
    album = get_object_or_404(ClientAlbum, id=album_id)
    return render(
        request,
        "albums/generate_link.html",
        {
            "album": album,
            "album_url": request.build_absolute_uri(album.get_absolute_url()),
            "page_title": f"Share “{album.name}”",
        },
    )
