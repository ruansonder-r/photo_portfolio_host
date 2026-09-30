from django.test import TestCase
from django.urls import reverse

from core.models import Photo
from portfolio.models import Gallery


class GalleryViewTests(TestCase):
    def setUp(self):
        import cloudinary

        cloudinary.config(cloud_name="testcloud", api_key="1", api_secret="s", secure=True)
        self.gallery = Gallery.objects.create(slug="matric-farewell", title="Matric Farewell")
        for i in range(3):
            Photo.objects.create(
                public_id=f"portfolio/matric-farewell/{i}", gallery=self.gallery,
                width=3000, height=2000, original_filename=f"IMG_{i}.jpg", position=i,
            )

    def test_home_lists_published_galleries(self):
        response = self.client.get(reverse("portfolio:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Matric Farewell")

    def test_home_is_publicly_cacheable(self):
        self.assertIn("public", self.client.get(reverse("portfolio:home"))["Cache-Control"])

    def test_gallery_detail_renders_a_responsive_srcset(self):
        response = self.client.get(self.gallery.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "srcset")
        self.assertContains(response, "w_400")

    def test_unpublished_gallery_is_hidden_and_unreachable(self):
        hidden = Gallery.objects.create(slug="featured", title="Featured", is_published=False)
        Photo.objects.create(public_id="portfolio/featured/a", gallery=hidden, width=10, height=10)
        self.assertEqual(self.client.get(hidden.get_absolute_url()).status_code, 404)
        self.assertNotContains(self.client.get(reverse("portfolio:home")), "featured/")

    def test_rendering_a_gallery_takes_a_constant_number_of_queries(self):
        # The old implementation called the Drive API once per gallery per
        # request; this must stay independent of how many photos there are.
        for i in range(3, 40):
            Photo.objects.create(
                public_id=f"portfolio/matric-farewell/{i}", gallery=self.gallery,
                width=3000, height=2000, position=i,
            )
        with self.assertNumQueries(3):
            self.client.get(self.gallery.get_absolute_url())

    def test_empty_gallery_is_not_advertised_on_the_home_page(self):
        Gallery.objects.create(slug="half-imported", title="Half Imported")
        response = self.client.get(reverse("portfolio:home"))
        self.assertNotContains(response, "Half Imported")
        # ...but a direct link still works and shows its own empty state.
        self.assertEqual(self.client.get("/gallery/half-imported/").status_code, 200)

    def test_cover_falls_back_to_the_first_photo(self):
        self.assertIsNotNone(self.gallery.cover_photo)


class SocialMetadataTests(TestCase):
    def setUp(self):
        import cloudinary

        cloudinary.config(cloud_name="testcloud", api_key="1", api_secret="s", secure=True)
        self.gallery = Gallery.objects.create(slug="g", title="Sunset Shoot")
        self.photo = Photo.objects.create(
            public_id="portfolio/g/a", gallery=self.gallery, width=3000, height=2000,
            original_filename="_MG_1.jpg",
        )

    def test_home_emits_open_graph_tags_with_a_real_image(self):
        body = self.client.get(reverse("portfolio:home")).content.decode()
        for tag in ('property="og:title"', 'property="og:image"',
                    'property="og:description"', 'name="twitter:card"', 'rel="canonical"'):
            self.assertIn(tag, body)
        # 1200x630 JPEG, because link-preview crawlers render neither AVIF nor WebP.
        self.assertIn("w_1200", body)
        self.assertIn("h_630", body)

    def test_canonical_url_drops_the_query_string(self):
        body = self.client.get(reverse("portfolio:home") + "?utm_source=instagram&cb=1").content.decode()
        self.assertIn('rel="canonical" href="http://testserver/"', body)
        self.assertNotIn("utm_source", body.split("</head>")[0])

    def test_gallery_preview_uses_the_gallery_title(self):
        body = self.client.get(self.gallery.get_absolute_url()).content.decode()
        self.assertIn('property="og:title" content="Sunset Shoot"', body)

    def test_alt_text_is_never_a_filename(self):
        body = self.client.get(self.gallery.get_absolute_url()).content.decode()
        self.assertNotIn('alt="_MG_1.jpg"', body)
        self.assertIn("Sunset Shoot", body)


class SitemapAndRobotsTests(TestCase):
    def setUp(self):
        import cloudinary

        cloudinary.config(cloud_name="testcloud", api_key="1", api_secret="s", secure=True)
        self.gallery = Gallery.objects.create(slug="visible", title="Visible")
        Photo.objects.create(public_id="p/1", gallery=self.gallery, width=10, height=10)

    def test_robots_allows_the_site_but_blocks_private_areas(self):
        body = self.client.get("/robots.txt").content.decode()
        self.assertIn("Disallow: /album/", body)
        self.assertIn("Disallow: /admin/", body)
        self.assertIn("Sitemap: http://testserver/sitemap.xml", body)

    def test_sitemap_lists_published_galleries(self):
        body = self.client.get("/sitemap.xml").content.decode()
        self.assertIn("/gallery/visible/", body)

    def test_sitemap_never_leaks_a_private_album_url(self):
        import datetime as dt

        from albums.models import ClientAlbum

        album = ClientAlbum.objects.create(name="Private", date=dt.date(2025, 1, 1))
        body = self.client.get("/sitemap.xml").content.decode()
        self.assertNotIn(str(album.pk), body)
        self.assertNotIn("/album/", body)


class ContactViewTests(TestCase):
    def test_contact_page_renders(self):
        response = self.client.get(reverse("portfolio:contact"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "mailto:")
