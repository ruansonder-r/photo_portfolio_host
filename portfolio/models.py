from __future__ import annotations

from django.db import models
from django.urls import reverse


class GalleryQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True)


class Gallery(models.Model):
    """A public portfolio gallery, addressed by slug rather than folder name."""

    slug = models.SlugField(max_length=120, unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    shot_on = models.DateField(null=True, blank=True)

    cover = models.ForeignKey(
        "core.Photo",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Defaults to the first photo when unset",
    )

    position = models.IntegerField(default=0, help_text="Lower numbers appear first")
    is_published = models.BooleanField(
        default=True,
        help_text="Unpublished galleries are hidden from the portfolio. Used for "
        "the hidden 'featured' gallery that feeds the homepage carousel.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = GalleryQuerySet.as_manager()

    class Meta:
        ordering = ["position", "-shot_on", "title"]
        verbose_name_plural = "galleries"

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return reverse("portfolio:gallery_detail", kwargs={"slug": self.slug})

    @property
    def cover_photo(self):
        # ``photos.all()`` is prefetched by the list views, so this does not
        # add a query per gallery card.
        if self.cover_id:
            return self.cover
        return next(iter(self.photos.all()), None)

    @property
    def photo_count(self) -> int:
        return self.photos.count()
