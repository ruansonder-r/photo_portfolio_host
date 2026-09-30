"""Sitemaps for the public portfolio.

Private client albums are deliberately absent: their URLs are secrets and must
never be published to a crawler.
"""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from portfolio.models import Gallery


class GallerySitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.8

    def items(self):
        return Gallery.objects.published().order_by("position", "title")

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return obj.get_absolute_url()


class StaticViewSitemap(Sitemap):
    changefreq = "monthly"
    priority = 1.0

    def items(self):
        return ["portfolio:home", "portfolio:contact"]

    def location(self, item):
        return reverse(item)


sitemaps = {"static": StaticViewSitemap, "galleries": GallerySitemap}
