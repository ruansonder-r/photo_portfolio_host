from django.conf import settings
from django.db.models import Count
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import cache_control

from core.models import Photo
from portfolio.models import Gallery

# Public pages hold no per-visitor data, so they can sit in the CDN and the
# browser cache. This replaces @cache_page, which was useless on serverless
# because each invocation got a fresh empty in-process cache.
public_cache = cache_control(public=True, max_age=settings.PUBLIC_PAGE_CACHE_SECONDS)

# Carousel slides are lazy-loaded apart from the first, so the ceiling is
# about curation rather than page weight. Kept high enough that a curated
# featured set is shown in full rather than silently truncated.
MAX_CAROUSEL_PHOTOS = 24


def _published_galleries():
    """Published galleries that actually have photos in them.

    An empty gallery renders as a blank card advertising nothing, which is
    what a half-finished import looks like to a visitor. Direct links still
    resolve and show the gallery's own empty state.
    """
    return (
        Gallery.objects.published()
        .select_related("cover")
        .annotate(num_photos=Count("photos"))
        .filter(num_photos__gt=0)
    )


def _featured_photos(limit=MAX_CAROUSEL_PHOTOS):
    # select_related: Photo.alt reads its gallery's title, which would
    # otherwise be one query per photo.
    return list(
        Photo.objects.filter(is_featured=True)
        .select_related("gallery")
        .order_by("position", "original_filename")[:limit]
    )


def _share(photo):
    """Link-preview image for a page, or empty context if there is none."""
    if not photo:
        return {}
    return {"share_image": photo.social_src, "share_image_alt": photo.alt}


@public_cache
def home(request):
    galleries = list(_published_galleries())
    carousel = _featured_photos()
    # Fall back to gallery covers so a fresh install is never a blank page.
    # cover_photo (not cover) because a gallery's cover is often implicit.
    if not carousel:
        carousel = [c for c in (g.cover_photo for g in galleries) if c][:MAX_CAROUSEL_PHOTOS]

    # A link preview must survive having no featured photos at all.
    share_photo = carousel[0] if carousel else next(
        (c for c in (g.cover_photo for g in galleries) if c), None
    )

    context = {
        "galleries": galleries,
        "carousel_photos": carousel,
    }
    context.update(_share(share_photo))
    return render(request, "portfolio/home.html", context)


@public_cache
def gallery_detail(request, slug):
    gallery = get_object_or_404(Gallery.objects.published().select_related("cover"), slug=slug)
    photos = list(gallery.photos.select_related("gallery"))
    others = list(_published_galleries().exclude(pk=gallery.pk)[:3])

    context = {
        "gallery": gallery,
        "photos": photos,
        "other_galleries": others,
        "page_title": gallery.title,
        "page_description": gallery.description or None,
    }
    context.update(_share(gallery.cover or (photos[0] if photos else None)))
    return render(request, "portfolio/gallery_detail.html", context)


@public_cache
def contact(request):
    context = {"page_title": "Contact"}
    context.update(_share(next(iter(_featured_photos(1)), None)))
    return render(request, "portfolio/contact.html", context)
