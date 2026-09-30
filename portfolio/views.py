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


@public_cache
def home(request):
    galleries = list(_published_galleries())
    carousel = list(
        Photo.objects.filter(is_featured=True).order_by("position", "original_filename")[
            :MAX_CAROUSEL_PHOTOS
        ]
    )
    # Fall back to gallery covers so a fresh install is never a blank page.
    if not carousel:
        carousel = [g.cover for g in galleries if g.cover_id][:MAX_CAROUSEL_PHOTOS]

    return render(
        request,
        "portfolio/home.html",
        {"galleries": galleries, "carousel_photos": carousel},
    )


@public_cache
def gallery_detail(request, slug):
    gallery = get_object_or_404(Gallery.objects.published(), slug=slug)
    photos = list(gallery.photos.all())
    others = list(_published_galleries().exclude(pk=gallery.pk)[:3])

    return render(
        request,
        "portfolio/gallery_detail.html",
        {"gallery": gallery, "photos": photos, "other_galleries": others},
    )


@public_cache
def contact(request):
    return render(request, "portfolio/contact.html")
