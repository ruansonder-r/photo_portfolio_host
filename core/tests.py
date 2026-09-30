import datetime as dt
import re

from django.db.utils import IntegrityError
from django.test import SimpleTestCase, TestCase

from albums.models import ClientAlbum
from core.models import Photo
from core.storage import photo_store
from core.templatetags.photo_tags import at_most
from portfolio.models import Gallery


def make_photo(**kwargs):
    defaults = dict(public_id="portfolio/demo/a", width=3000, height=2000, format="jpg")
    return Photo.objects.create(**{**defaults, **kwargs})


class PhotoOwnershipTests(TestCase):
    def setUp(self):
        self.gallery = Gallery.objects.create(slug="g", title="G")
        self.album = ClientAlbum.objects.create(name="A", date=dt.date(2025, 1, 1))

    def test_photo_cannot_have_two_owners(self):
        with self.assertRaises(IntegrityError):
            make_photo(gallery=self.gallery, album=self.album)

    def test_photo_cannot_be_orphaned(self):
        with self.assertRaises(IntegrityError):
            make_photo()

    def test_album_photos_are_private_gallery_photos_are_not(self):
        self.assertTrue(make_photo(album=self.album, public_id="x").is_private)
        self.assertFalse(make_photo(gallery=self.gallery, public_id="y").is_private)


class PhotoPresentationTests(TestCase):
    def setUp(self):
        self.gallery = Gallery.objects.create(slug="g", title="G")

    def test_aspect_ratio_and_value_come_from_stored_dimensions(self):
        photo = make_photo(gallery=self.gallery, width=3000, height=2000)
        self.assertEqual(photo.aspect_ratio, "3000 / 2000")
        self.assertEqual(photo.aspect_value, 1.5)

    def test_missing_dimensions_fall_back_instead_of_dividing_by_zero(self):
        photo = make_photo(gallery=self.gallery, width=0, height=0)
        self.assertEqual(photo.aspect_value, 1.5)
        self.assertEqual(photo.aspect_ratio, "3 / 2")

    def test_alt_prefers_a_caption_when_one_is_set(self):
        photo = make_photo(gallery=self.gallery, original_filename="IMG_1.jpg", caption="Bride at sunset")
        self.assertEqual(photo.alt, "Bride at sunset")

    def test_alt_omits_the_name_of_an_unpublished_gallery(self):
        hidden = Gallery.objects.create(slug="featured", title="Featured", is_published=False)
        photo = make_photo(gallery=hidden, public_id="h", original_filename="_MG_1.jpg")
        self.assertNotIn("Featured", photo.alt)
        self.assertIn("photograph by", photo.alt)

    def test_alt_never_falls_back_to_the_camera_filename(self):
        # "_MG_6316.jpg" is what a screen reader would read aloud and what
        # Google Images would index, so it must never reach the alt attribute.
        photo = make_photo(gallery=self.gallery, original_filename="_MG_6316.jpg")
        self.assertNotIn("_MG_6316", photo.alt)
        self.assertNotIn(".jpg", photo.alt)
        self.assertIn(self.gallery.title, photo.alt)


class StorageUrlTests(SimpleTestCase):
    """URL construction must stay offline -- no network call while rendering."""

    def setUp(self):
        import cloudinary

        cloudinary.config(cloud_name="testcloud", api_key="1", api_secret="s", secure=True)

    def test_public_url_is_unsigned_and_carries_transformations(self):
        url = photo_store.url("portfolio/g/a", width=800)
        self.assertIn("/testcloud/image/upload/", url)
        self.assertIn("w_800", url)
        self.assertIn("f_auto", url)
        self.assertIn("q_auto:good", url)
        self.assertNotIn("/s--", url)

    def test_private_url_is_signed_and_uses_authenticated_delivery(self):
        url = photo_store.url("albums/1/a", width=800, private=True)
        self.assertIn("/image/authenticated/", url)
        self.assertIn("/s--", url)

    @staticmethod
    def _descriptors(srcset):
        # Cloudinary URLs contain commas (c_limit,f_auto,...), so a srcset
        # cannot be split on ","; read the "<n>w" descriptors instead. The HTML
        # parser is fine with this because it splits on whitespace first.
        return [int(w) for w in re.findall(r"\s(\d+)w", srcset)]

    def test_srcset_never_offers_a_width_above_the_original(self):
        widths = self._descriptors(photo_store.srcset("portfolio/g/a", native_width=1000))
        self.assertTrue(all(w <= 1000 for w in widths), widths)
        self.assertIn(400, widths)

    def test_srcset_for_a_tiny_original_still_offers_one_width(self):
        self.assertEqual(
            self._descriptors(photo_store.srcset("portfolio/g/a", native_width=50)), [400]
        )

    def test_srcset_candidates_are_separated_by_comma_space(self):
        # Guards the parsing contract: each candidate ends in "<n>w" and the
        # next begins after ", ", so URL-internal commas are unambiguous.
        srcset = photo_store.srcset("portfolio/g/a", native_width=4000)
        self.assertEqual(len(self._descriptors(srcset)), 5)
        for candidate in re.split(r"(?<=w), ", srcset):
            self.assertRegex(candidate.strip(), r"^https://\S+ \d+w$")

    def test_original_url_is_flagged_as_an_attachment(self):
        self.assertIn("fl_attachment", photo_store.original_url("portfolio/g/a"))

    def test_archive_url_requires_at_least_one_photo(self):
        with self.assertRaises(ValueError):
            photo_store.archive_url([], filename="x")


class TemplateFilterTests(SimpleTestCase):
    def test_at_most_caps_columns_to_the_photo_count(self):
        self.assertEqual(at_most(2, 4), 2)
        self.assertEqual(at_most(9, 4), 4)

    def test_at_most_survives_rubbish_input(self):
        self.assertEqual(at_most(None, 3), 3)
