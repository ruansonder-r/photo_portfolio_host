import datetime as dt

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from albums.models import ClientAlbum
from core.models import Photo


class AlbumAccessTests(TestCase):
    def setUp(self):
        import cloudinary

        cloudinary.config(cloud_name="testcloud", api_key="1", api_secret="s", secure=True)
        self.album = ClientAlbum.objects.create(name="Smith Wedding", date=dt.date(2025, 2, 14))
        self.photo = Photo.objects.create(
            public_id="albums/x/a", album=self.album, width=3000, height=2000,
            original_filename="IMG_1.jpg",
        )
        self.url = reverse("albums:album_detail", kwargs={"album_id": self.album.pk})

    def test_active_album_renders_its_name(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        # Regression: the template used to read album.title, which does not
        # exist, so every client album rendered a blank heading.
        self.assertContains(response, "Smith Wedding")

    def test_private_album_is_never_cached(self):
        cache_control = self.client.get(self.url)["Cache-Control"]
        self.assertIn("no-store", cache_control)
        self.assertIn("private", cache_control)

    def test_private_album_never_emits_a_link_preview_image(self):
        # og:image on an album page would hand a signed, working image URL to
        # every link-preview crawler that touches the secret link.
        body = self.client.get(self.url).content.decode()
        self.assertNotIn("og:image", body)
        self.assertNotIn("twitter:image", body)
        self.assertIn("noindex", body)

    def test_revoked_album_is_not_found(self):
        self.album.is_active = False
        self.album.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_expired_album_is_not_found(self):
        self.album.expires_at = timezone.now() - dt.timedelta(minutes=1)
        self.album.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_future_expiry_still_works(self):
        self.album.expires_at = timezone.now() + dt.timedelta(days=1)
        self.album.save()
        self.assertEqual(self.client.get(self.url).status_code, 200)


class AlbumDownloadTests(TestCase):
    def setUp(self):
        import cloudinary

        cloudinary.config(cloud_name="testcloud", api_key="1", api_secret="s", secure=True)
        self.album = ClientAlbum.objects.create(name="Smith Wedding", date=dt.date(2025, 2, 14))
        self.photo = Photo.objects.create(
            public_id="albums/x/a", album=self.album, width=3000, height=2000,
        )

    def test_zip_redirects_to_a_generated_archive(self):
        url = reverse("albums:download_album_zip", kwargs={"album_id": self.album.pk})
        response = self.client.get(url)
        # The old view built a ZIP in memory and wrote empty strings for any
        # file it could not find locally, handing clients 0-byte photos.
        self.assertEqual(response.status_code, 302)
        self.assertIn("generate_archive", response["Location"])

    def test_zip_of_an_empty_album_is_not_found(self):
        self.photo.delete()
        url = reverse("albums:download_album_zip", kwargs={"album_id": self.album.pk})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_single_photo_download_redirects_rather_than_injecting_script(self):
        url = reverse(
            "albums:download_photo",
            kwargs={"album_id": self.album.pk, "photo_id": self.photo.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("fl_attachment", response["Location"])

    def test_photo_from_another_album_is_not_downloadable(self):
        other = ClientAlbum.objects.create(name="Other", date=dt.date(2025, 3, 1))
        stray = Photo.objects.create(public_id="albums/y/b", album=other, width=10, height=10)
        url = reverse(
            "albums:download_photo",
            kwargs={"album_id": self.album.pk, "photo_id": stray.pk},
        )
        self.assertEqual(self.client.get(url).status_code, 404)


class AdminViewTests(TestCase):
    def test_album_management_requires_staff(self):
        response = self.client.get(reverse("albums:admin_list"))
        self.assertIn(response.status_code, (302, 403))
