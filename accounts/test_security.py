import io
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image


class LoginThrottleTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("host@x.mv", "host@x.mv", "right-pass-123")

    def attempt(self, password, ip="1.2.3.4"):
        return self.client.post("/accounts/login/", {"username": "host@x.mv", "password": password},
                                HTTP_X_FORWARDED_FOR=ip)

    def test_locks_after_repeated_wrong_passwords(self):
        for _ in range(8):
            self.assertEqual(self.attempt("wrong").status_code, 200)
        r = self.attempt("right-pass-123")  # right password, but locked for now
        self.assertContains(r, "Too many sign-in attempts")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_success_clears_failures(self):
        for _ in range(3):
            self.attempt("wrong")
        r = self.attempt("right-pass-123")
        self.assertEqual(r.status_code, 302)
        from accounts.models import LoginFailure
        self.assertFalse(LoginFailure.objects.filter(key="user:host@x.mv").exists())

    def test_admin_login_is_throttled_too(self):
        get_user_model().objects.create_superuser("boss@x.mv", "boss@x.mv", "boss-pass-123")
        for _ in range(8):
            self.client.post("/admin/login/", {"username": "boss@x.mv", "password": "nope"})
        r = self.client.post("/admin/login/", {"username": "boss@x.mv", "password": "boss-pass-123"})
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(r.status_code, 200)


class UploadedFileServingTests(TestCase):
    def test_proxy_ignores_uploaded_content_type(self):
        from django.test import RequestFactory

        from config import blob_storage

        class FakeStore(blob_storage.VercelBlobStorage):
            def __init__(self):  # no credentials needed
                pass

            def fetch_private(self, path):
                return b"<html><script>x</script>", "text/html"

        with mock.patch("django.core.files.storage.default_storage", new=FakeStore()):
            r = blob_storage.blob_proxy(RequestFactory().get("/"), "contributions/evil.html")
            self.assertEqual(r["Content-Type"], "application/octet-stream")
            self.assertEqual(r["Content-Disposition"], "attachment")
            self.assertIn("sandbox", r["Content-Security-Policy"])
            r = blob_storage.blob_proxy(RequestFactory().get("/"), "islands/photo-abc.jpg")
            self.assertEqual(r["Content-Type"], "image/jpeg")
            self.assertEqual(r["X-Content-Type-Options"], "nosniff")


class PublicPhotoTests(TestCase):
    def test_contributed_photo_loses_location_data(self):
        from directory.views import _clean_public_photo

        img = Image.new("RGB", (40, 30), "teal")
        exif = Image.Exif()
        exif[0x010F] = "PhoneMaker"  # camera make
        buf = io.BytesIO()
        img.save(buf, "JPEG", exif=exif)
        self.assertIn(b"PhoneMaker", buf.getvalue())
        out = _clean_public_photo(SimpleUploadedFile("me.jpg", buf.getvalue(), content_type="text/html"))
        data = out.read()
        self.assertNotIn(b"PhoneMaker", data)
        self.assertEqual(out.content_type, "image/jpeg")
        self.assertEqual(Image.open(io.BytesIO(data)).size, (40, 30))
        self.assertIsNone(_clean_public_photo(SimpleUploadedFile("x.jpg", b"<html>not an image</html>")))
