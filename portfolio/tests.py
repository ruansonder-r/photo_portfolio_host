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


class ContactViewTests(TestCase):
    def test_contact_page_renders(self):
        response = self.client.get(reverse("portfolio:contact"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "mailto:")
