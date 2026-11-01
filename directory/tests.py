from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import ActivityType, Enquiry, Island, Listing

User = get_user_model()


class FlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_maldives", "--demo", stdout=open("/dev/null", "w"))
        cls.owner = User.objects.get(username="owner@demo.mv")
        cls.listing = Listing.objects.get(name="Coral Breeze Inn")
        cls.pending = Listing.objects.get(name="Sunset Sands Guest House")

    def test_island_page_shows_only_approved_listings(self):
        r = self.client.get(reverse("directory:island_detail", args=["gulhi"]))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, self.pending.name)
        r = self.client.get(reverse("directory:island_detail", args=["maafushi"]))
        self.assertContains(r, "Coral Breeze Inn")
        self.assertContains(r, "Known for")
        self.assertContains(r, "Pop. 4,471 (2022)")

    def test_pending_listing_hidden_from_public_but_visible_to_owner(self):
        url = self.pending.get_absolute_url()
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(url), "Preview")

    def test_guest_sends_request_directly_to_owner(self):
        d = timezone.localdate() + timedelta(days=20)
        r = self.client.post(self.listing.get_absolute_url(), {
            "guest_name": "Sara Lee", "guest_email": "sara@example.com", "preferred_contact": "email",
            "check_in": d, "check_out": d + timedelta(days=4), "adults": 2, "children": 0,
            "message": "Do you have a sea view room?", "hp_leave_empty": "",
        })
        e = Enquiry.objects.get(guest_email="sara@example.com")
        self.assertRedirects(r, reverse("directory:enquiry_sent", args=[e.reference]))
        self.assertEqual(e.nights, 4)
        self.assertEqual(len(mail.outbox), 0)  # the site sends no email; the guest messages the host
        page = self.client.get(r.url)
        self.assertContains(page, "mailto:" + self.listing.contact_email)
        self.assertIn("4 nights", e.as_message())
        self.assertIn(e.reference, e.as_message())

    def test_request_without_message_is_accepted(self):
        self.client.post(self.listing.get_absolute_url(), {
            "guest_name": "Ann", "guest_email": "ann@example.com", "preferred_contact": "whatsapp",
            "adults": 2, "children": 0, "hp_leave_empty": ""})
        self.assertTrue(Enquiry.objects.filter(guest_email="ann@example.com").exists())

    def test_request_validation_and_honeypot(self):
        d = timezone.localdate() + timedelta(days=5)
        base = {"guest_name": "X", "guest_email": "x@example.com", "preferred_contact": "email", "adults": 1, "children": 0, "message": "hi"}
        r = self.client.post(self.listing.get_absolute_url(), {**base, "check_in": d, "check_out": d})
        self.assertContains(r, "Check-out must be after check-in")
        self.client.post(self.listing.get_absolute_url(), {**base, "hp_leave_empty": "http://spam"})
        self.assertFalse(Enquiry.objects.filter(guest_email="x@example.com").exists())

    def test_signup_create_listing_and_admin_approval(self):
        r = self.client.post(reverse("accounts:signup"), {
            "full_name": "Ali Hassan", "email": "ali@example.mv", "business_name": "Reef Side",
            "phone": "+9607771234", "island_of_operation": "Thoddoo",
            "password1": "Sup3r-secret-pass", "password2": "Sup3r-secret-pass",
        })
        self.assertRedirects(r, reverse("directory:listing_create"))
        thoddoo = Island.objects.get(slug="thoddoo")
        r = self.client.post(reverse("directory:listing_create"), {
            "kind": "guesthouse", "name": "Reef Side", "island": thoddoo.pk, "short_description": "Nice",
            "description": "Lovely place", "currency": "USD", "price_unit": "night", "price_from": "60",
            "contact_name": "Ali", "contact_email": "ali@example.mv",
            "rooms-TOTAL_FORMS": "1", "rooms-INITIAL_FORMS": "0", "rooms-MIN_NUM_FORMS": "0", "rooms-MAX_NUM_FORMS": "1000",
            "rooms-0-name": "Double", "rooms-0-price_from": "60",
        })
        listing = Listing.objects.get(name="Reef Side")
        self.assertRedirects(r, reverse("directory:listing_photos", args=[listing.pk]))
        self.assertEqual(listing.status, Listing.STATUS_PENDING)
        self.assertEqual(listing.rooms.count(), 1)
        self.assertNotContains(self.client.get(thoddoo.get_absolute_url()), "Reef Side")

        admin = User.objects.create_superuser("admin", "admin@x.mv", "pw")
        self.client.force_login(admin)
        mail.outbox.clear()
        self.client.post(reverse("admin:directory_listing_changelist"), {"action": "approve", "_selected_action": [listing.pk]})
        listing.refresh_from_db()
        self.assertEqual(listing.status, Listing.STATUS_APPROVED)
        self.assertEqual(len(mail.outbox), 0)  # owners see the status in their dashboard
        self.client.logout()
        self.assertContains(self.client.get(thoddoo.get_absolute_url()), "Reef Side")

    def test_owner_dashboard_and_permissions(self):
        e = self.listing.enquiries.first()
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse("directory:dashboard")), e.reference)
        r = self.client.post(reverse("directory:enquiry_detail", args=[e.reference]), {"status": "confirmed", "owner_notes": "Paid deposit"})
        e.refresh_from_db()
        self.assertEqual(e.status, "confirmed")
        self.assertContains(self.client.get(reverse("directory:listing_edit", args=[self.listing.pk])), "Coral Breeze Inn")

        other = User.objects.create_user("other@x.mv", "other@x.mv", "pw")
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("directory:enquiry_detail", args=[e.reference])).status_code, 404)
        self.assertEqual(self.client.get(reverse("directory:listing_edit", args=[self.listing.pk])).status_code, 404)

    def test_filters(self):
        r = self.client.get(reverse("directory:island_list"), {"activity": "whale-shark-excursion"})
        self.assertContains(r, "Dhigurah")
        self.assertNotContains(r, "Thulusdhoo")
        with self.settings(SHOW_PRICES=True):
            r = self.client.get(reverse("directory:stay_list"), {"max_price": "80"})
            self.assertContains(r, "Coral Breeze Inn")
            self.assertNotContains(r, "Lagoon View Hotel")

    def test_prices_hidden_by_default(self):
        r = self.client.get(reverse("directory:stay_list"), {"max_price": "80"})
        self.assertContains(r, "Lagoon View Hotel")  # the filter is ignored
        self.assertNotContains(r, "max_price")
        r = self.client.get(self.listing.get_absolute_url())
        self.assertNotContains(r, "$75")
        self.client.force_login(self.owner)
        self.assertNotContains(self.client.get(reverse("directory:listing_create")), "price_from")


class CategoryTests(TestCase):
    """Transport, food, island guide and verified-host features."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_maldives", "--demo", stdout=open("/dev/null", "w"))
        cls.owner = User.objects.get(username="owner@demo.mv")

    def test_island_page_has_all_sections(self):
        r = self.client.get(reverse("directory:island_detail", args=["dhangethi"]))
        for text in ["Ari Reef View Guest House", "Dhangethi Whale Shark Trips", "Fathuhu Café", "South Ari Speed Link",
                     "Maamigili (VAM)", "Local regulations", "Accessibility", "Pharmacy", "Domestic flight"]:
            self.assertContains(r, text)

    def test_search_jumps_to_island_section(self):
        r = self.client.get(reverse("directory:search"), {"q": "dhangethi", "section": "food"})
        self.assertRedirects(r, "/islands/dhangethi/#food", fetch_redirect_response=False)

    def test_transport_page_filters_by_island_and_mode(self):
        r = self.client.get(reverse("directory:transport_list"), {"island": "dhangethi", "mode": "flight"})
        self.assertContains(r, "Domestic flight")
        self.assertNotContains(r, "<h4>Shared speedboat")
        self.assertContains(r, "South Ari Speed Link")  # operator sidebar

    def test_routes_of_unapproved_operator_are_hidden(self):
        op = Listing.objects.get(name="South Ari Speed Link")
        op.status = Listing.STATUS_SUSPENDED
        op.save()
        r = self.client.get(reverse("directory:transport_list"), {"island": "dhangethi"})
        self.assertNotContains(r, "South Ari Speed Link")

    def test_food_list_and_kind_separation(self):
        r = self.client.get(reverse("directory:food_list"), {"q": "seafood"})
        self.assertContains(r, "Fathuhu Café")
        self.assertNotContains(self.client.get(reverse("directory:service_list")), "Fathuhu Café")

    def test_verified_filter(self):
        r = self.client.get(reverse("directory:stay_list"), {"verified": "1"})
        self.assertContains(r, "Coral Breeze Inn")
        self.assertNotContains(r, "Lagoon View Hotel")

    def test_owner_requests_verification_and_manages_routes(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_login(self.owner)
        hotel = Listing.objects.get(name="Lagoon View Hotel")
        r = self.client.post(reverse("directory:listing_verify", args=[hotel.pk]), {
            "registration_number": "TR-12345",
            "verification_document": SimpleUploadedFile("licence.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
        })
        self.assertRedirects(r, reverse("directory:dashboard"))
        hotel.refresh_from_db()
        self.assertTrue(hotel.verification_pending)
        hotel.verification_document.delete()

        op = Listing.objects.get(name="South Ari Speed Link")
        before = op.routes.count()
        mgmt = {"routes-TOTAL_FORMS": str(before + 1), "routes-INITIAL_FORMS": str(before), "routes-MIN_NUM_FORMS": "0", "routes-MAX_NUM_FORMS": "1000"}
        data = dict(mgmt)
        for i, route in enumerate(op.routes.all()):
            data.update({f"routes-{i}-id": route.pk, f"routes-{i}-island": route.island_id, f"routes-{i}-mode": route.mode,
                         f"routes-{i}-origin": route.origin, f"routes-{i}-duration": route.duration, f"routes-{i}-currency": "USD",
                         f"routes-{i}-is_active": "on"})
        n = before
        data.update({f"routes-{n}-island": Island.objects.get(slug="dhigurah").pk, f"routes-{n}-mode": "speedboat",
                     f"routes-{n}-origin": "Dhangethi", f"routes-{n}-duration": "15 min", f"routes-{n}-currency": "USD",
                     f"routes-{n}-is_active": "on"})
        self.client.post(reverse("directory:listing_routes", args=[op.pk]), data)
        self.assertEqual(op.routes.count(), before + 1)
        self.assertContains(self.client.get(reverse("directory:island_detail", args=["dhigurah"])), "South Ari Speed Link")


class FetchPhotoTests(TestCase):
    """Photos are linked from Wikimedia Commons (stored as URLs with credits), not downloaded."""

    def test_links_cover_gallery_and_activity_photos(self):
        from unittest import mock

        call_command("seed_maldives", stdout=open("/dev/null", "w"))

        def info(title, w=2400):
            return {"title": title, "index": 1, "imageinfo": [{
                "thumburl": f"https://upload.wikimedia.org/x/1920px-{title[5:]}", "mime": "image/jpeg", "width": w,
                "descriptionurl": f"https://commons.wikimedia.org/wiki/{title}",
                "extmetadata": {"Artist": {"value": '<a href="#">Jane Doe</a>'}, "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                "ImageDescription": {"value": "Beach"}}}]}

        def fake_json(url):
            if "en.wikipedia.org" in url:
                return {"query": {"pages": {"1": {"pageimage": "Maafushi_beach.jpg"}}}}
            if "generator=search" in url:
                return {"query": {"pages": {
                    "1": info("File:Maafushi_harbour.jpg"), "2": info("File:Maafushi_map.png"),
                    "3": info("File:Unrelated_island.jpg"), "4": info("File:Maafushi_small.jpg", w=300)}}}
            return {"query": {"pages": {"-1": info("File:Maafushi_beach.jpg")}}}

        with mock.patch("directory.management.commands.fetch_island_photos.get_json", side_effect=fake_json):
            call_command("fetch_island_photos", stdout=open("/dev/null", "w"))
        island = Island.objects.get(slug="maafushi")
        self.assertEqual(island.cover_image_url, "https://upload.wikimedia.org/x/1920px-Maafushi_beach.jpg")
        self.assertEqual(island.card_photo_url, "https://upload.wikimedia.org/x/960px-Maafushi_beach.jpg")
        self.assertEqual((island.cover_credit, island.cover_license), ("Jane Doe", "CC BY-SA 4.0"))
        # Gallery keeps only files named after the island, skipping maps and small images.
        self.assertEqual(list(island.photos.values_list("image_url", flat=True)), ["https://upload.wikimedia.org/x/1920px-Maafushi_harbour.jpg"])
        self.assertTrue(ActivityType.objects.get(name="Snorkeling").image_url)

        r = self.client.get(island.get_absolute_url())
        self.assertContains(r, 'src="https://upload.wikimedia.org/x/1920px-Maafushi_beach.jpg"')
        self.assertContains(r, "Jane Doe")
        self.assertContains(self.client.get(reverse("directory:photo_credits")), "Maafushi (cover)")
        # A second run without --force makes no requests for an island that already has photos.
        with mock.patch("directory.management.commands.fetch_island_photos.get_json", side_effect=AssertionError("no request expected")) as m:
            call_command("fetch_island_photos", island="maafushi", stdout=open("/dev/null", "w"))
        m.assert_not_called()

    def test_listing_cards_fall_back_to_island_photo(self):
        call_command("seed_maldives", "--demo", stdout=open("/dev/null", "w"))
        island = Island.objects.get(slug="dhangethi")
        island.cover_image_url = "https://upload.wikimedia.org/x/1920px-Dhangethi.jpg"
        island.save()
        r = self.client.get(reverse("directory:stay_list"))
        self.assertContains(r, "960px-Dhangethi.jpg")


class BackOfficeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_maldives", "--demo", stdout=open("/dev/null", "w"))
        cls.admin = User.objects.create_superuser("boss@x.mv", "boss@x.mv", "pw")

    def setUp(self):
        self.client.force_login(self.admin)

    def test_admin_pages_render(self):
        listing = Listing.objects.get(name="Coral Breeze Inn")
        for url in ["/admin/", "/admin/directory/listing/", "/admin/directory/listing/?status__exact=pending",
                    f"/admin/directory/listing/{listing.pk}/change/", "/admin/directory/island/", "/admin/directory/island/?photo=no",
                    f"/admin/directory/island/{listing.island_id}/change/", "/admin/directory/enquiry/",
                    f"/admin/directory/enquiry/{listing.enquiries.first().pk}/change/", "/admin/directory/transportroute/",
                    "/admin/auth/user/", "/admin/directory/atoll/", "/admin/directory/activitytype/"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        r = self.client.get("/admin/")
        self.assertContains(r, "Listings waiting for review")
        self.assertContains(r, "Sunset Sands Guest House")

    def test_one_click_approve_and_buttons_follow_state(self):
        pending = Listing.objects.get(name="Sunset Sands Guest House")
        url = reverse("admin:directory_listing_change", args=[pending.pk])
        r = self.client.get(url)
        self.assertContains(r, "Approve &amp; publish")
        import re

        approve_url = re.search(r'href="([^"]*/approve/[^"]*)"', r.content.decode()).group(1)
        self.client.get(approve_url)
        pending.refresh_from_db()
        self.assertEqual(pending.status, Listing.STATUS_APPROVED)
        self.assertNotContains(self.client.get(url), "Approve &amp; publish")


class AtollIndexTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_maldives", stdout=open("/dev/null", "w"))

    def test_every_seeded_island_and_atoll_has_coordinates(self):
        from .models import Atoll

        self.assertFalse(Island.objects.filter(latitude__isnull=True).exists())
        self.assertFalse(Atoll.objects.filter(map_lat__isnull=True).exists())

    def test_home_lists_atolls_north_to_south_without_a_map(self):
        r = self.client.get(reverse("directory:home"))
        html = r.content.decode()
        self.assertLess(html.index("/atolls/haa-alif/"), html.index("/atolls/addu/"))
        self.assertNotIn("leaflet", html)
        self.assertContains(r, "islandstay-horizontal-colour-light.svg")


class VercelTests(TestCase):
    def test_blob_storage_uploads_and_builds_public_url(self):
        import io
        import json
        from unittest import mock

        from django.core.files.uploadedfile import SimpleUploadedFile

        from config.blob_storage import VercelBlobStorage

        calls = []

        class Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout=None):
            calls.append(req)
            if req.full_url.endswith("/delete"):
                return Resp(b"")
            return Resp(json.dumps({"url": "https://abc123.public.blob.vercel-storage.com/listings/x-Ab12.jpg",
                                    "pathname": "listings/x-Ab12.jpg"}).encode())

        storage = VercelBlobStorage(token="vercel_blob_rw_ABC123_secretpart")
        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            name = storage.save("listings/x.jpg", SimpleUploadedFile("x.jpg", b"img", content_type="image/jpeg"))
            storage.delete(name)
        self.assertEqual(name, "listings/x-Ab12.jpg")
        self.assertEqual(storage.url(name), "https://abc123.public.blob.vercel-storage.com/listings/x-Ab12.jpg")
        put = calls[0]
        self.assertEqual(put.get_method(), "PUT")
        self.assertIn("pathname=listings%2Fx.jpg", put.full_url)
        self.assertEqual(put.get_header("Authorization"), "Bearer vercel_blob_rw_ABC123_secretpart")
        self.assertEqual(put.get_header("X-vercel-blob-access"), "public")
        self.assertEqual(calls[1].full_url, "https://vercel.com/api/blob/delete")

    def test_startup_setup_seeds_empty_database_and_creates_admin(self):
        import os
        from unittest import mock

        from config import startup

        with mock.patch.dict(os.environ, {"ADMIN_EMAIL": "boss@islandstay.mv", "ADMIN_PASSWORD": "pw-123456"}):
            startup.run()
            startup.run()  # second cold start: nothing to do
        self.assertEqual(Island.objects.count(), 22)
        self.assertTrue(User.objects.filter(username="boss@islandstay.mv", is_superuser=True).exists())

    def test_cron_endpoint_requires_secret(self):
        from unittest import mock

        self.assertEqual(self.client.get("/cron/photos/").status_code, 403)
        with self.settings(CRON_SECRET="s3cret"), \
                mock.patch("directory.management.commands.fetch_island_photos.get_json", side_effect=OSError("offline")):
            self.assertEqual(self.client.get("/cron/photos/", HTTP_AUTHORIZATION="Bearer wrong").status_code, 403)
            r = self.client.get("/cron/photos/", HTTP_AUTHORIZATION="Bearer s3cret")
        self.assertEqual(r.status_code, 200)


class SetupCheckTests(TestCase):
    def test_missing_settings_show_checklist(self):
        with self.settings(SETUP_MISSING=[("DJANGO_SECRET_KEY", "Add it under Environment Variables.")]):
            r = self.client.get("/")
        self.assertEqual(r.status_code, 503)
        self.assertContains(r, "DJANGO_SECRET_KEY", status_code=503)
        self.assertEqual(self.client.get("/").status_code, 200)


class PrivateBlobTests(TestCase):
    def test_private_store_upload_falls_back_and_is_served_through_site(self):
        import io
        import json
        from unittest import mock
        from urllib.error import HTTPError

        from django.core.files.uploadedfile import SimpleUploadedFile

        from config import blob_storage
        from config.blob_storage import VercelBlobStorage

        class Resp(io.BytesIO):
            headers = {"content-type": "image/jpeg"}

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        calls = []

        def fake_urlopen(req, timeout=None):
            calls.append((req.get_method(), req.full_url, req.get_header("X-vercel-blob-access")))
            if req.get_method() == "PUT" and req.get_header("X-vercel-blob-access") == "public":
                raise HTTPError(req.full_url, 400, "Bad Request", {}, io.BytesIO(b'{"error":"store is private"}'))
            if req.get_method() == "PUT":
                return Resp(json.dumps({"pathname": "listings/x-Zz9.jpg",
                                        "url": "https://abc.private.blob.vercel-storage.com/listings/x-Zz9.jpg"}).encode())
            return Resp(b"jpegbytes")

        VercelBlobStorage.access = None
        storage = VercelBlobStorage(token="vercel_blob_rw_ABC_secret")
        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            name = storage.save("listings/x.jpg", SimpleUploadedFile("x.jpg", b"img", content_type="image/jpeg"))
            self.assertEqual(name, "~p/listings/x-Zz9.jpg")
            self.assertEqual(storage.url(name), "/media/blob/listings/x-Zz9.jpg")
            with mock.patch("django.core.files.storage.default_storage", storage), \
                    mock.patch.object(blob_storage, "VercelBlobStorage", VercelBlobStorage):
                r = self.client.get("/media/blob/listings/x-Zz9.jpg")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, b"jpegbytes")
        self.assertEqual([c[2] for c in calls if c[0] == "PUT"], ["public", "private"])
        VercelBlobStorage.access = None


class ErrorDetailsTests(TestCase):
    def test_superusers_see_error_details_others_do_not(self):
        from unittest import mock

        admin = User.objects.create_superuser("boss2@x.mv", "boss2@x.mv", "pw")
        self.client.raise_request_exception = False
        with mock.patch("directory.views.home", side_effect=RuntimeError("boom from test")), \
                mock.patch("directory.urls.views.home", side_effect=RuntimeError("boom from test")):
            from django.urls import clear_url_caches
            clear_url_caches()
            r = self.client.get("/how-it-works/")  # sanity: unaffected page still works
            self.assertEqual(r.status_code, 200)
        from config.error_details import AdminErrorDetailsMiddleware
        from django.test import RequestFactory

        req = RequestFactory().get("/")
        req.user = admin
        resp = AdminErrorDetailsMiddleware(lambda r: None).process_exception(req, RuntimeError("boom from test"))
        self.assertEqual(resp.status_code, 500)
        self.assertIn(b"boom from test", resp.content)
        from django.contrib.auth.models import AnonymousUser

        req.user = AnonymousUser()
        self.assertIsNone(AdminErrorDetailsMiddleware(lambda r: None).process_exception(req, RuntimeError("x")))


class OidcBlobTests(TestCase):
    def test_store_id_with_request_oidc_token(self):
        import io
        import json
        from unittest import mock

        from django.core.files.uploadedfile import SimpleUploadedFile

        from config.blob_storage import VercelBlobStorage
        from config.request_context import vercel_oidc_token

        class Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        seen = []

        def fake_urlopen(req, timeout=None):
            seen.append(req)
            return Resp(json.dumps({"pathname": "islands/a-X1.jpg",
                                    "url": "https://abcdef.public.blob.vercel-storage.com/islands/a-X1.jpg"}).encode())

        VercelBlobStorage.access = None
        storage = VercelBlobStorage(token="", store_id="store_AbCdEf")
        # Without a token from Vercel the error explains what to switch on.
        with self.assertRaisesMessage(OSError, "OIDC"):
            storage.save("islands/a.jpg", SimpleUploadedFile("a.jpg", b"img", content_type="image/jpeg"))
        reset = vercel_oidc_token.set("oidc-abc")
        try:
            with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
                name = storage.save("islands/a.jpg", SimpleUploadedFile("a.jpg", b"img", content_type="image/jpeg"))
        finally:
            vercel_oidc_token.reset(reset)
        self.assertEqual(name, "islands/a-X1.jpg")
        self.assertEqual(storage.url(name), "https://abcdef.public.blob.vercel-storage.com/islands/a-X1.jpg")
        self.assertEqual(seen[0].get_header("Authorization"), "Bearer oidc-abc")
        self.assertEqual(seen[0].get_header("X-vercel-blob-store-id"), "AbCdEf")
        VercelBlobStorage.access = None

    def test_middleware_passes_vercel_header_to_context(self):
        from django.test import RequestFactory

        from config.request_context import RequestContextMiddleware, current_oidc_token

        captured = {}
        mw = RequestContextMiddleware(lambda r: captured.setdefault("t", current_oidc_token()))
        mw(RequestFactory().get("/", HTTP_X_VERCEL_OIDC_TOKEN="tok-123"))
        self.assertEqual(captured["t"], "tok-123")
        self.assertIsNone(current_oidc_token())


from django.core import mail





class AIAssistTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("ai@x.mv", "ai@x.mv", "pw")
        self.client.force_login(self.admin)

    def _fake_client(self, responses):
        from types import SimpleNamespace as NS
        from unittest import mock

        calls = []

        def create(**kwargs):
            calls.append(kwargs)
            return responses.pop(0)

        client = NS(beta=NS(messages=NS(create=create)))
        return mock.patch("anthropic.Anthropic", return_value=client), calls

    def test_research_returns_fields_after_pause(self):
        import os
        from types import SimpleNamespace as NS
        from unittest import mock

        submit = NS(type="tool_use", name="submit_details", input={
            "tagline": "Surf breaks and a quiet harbour", "population": "1200", "has_atm": "yes",
            "sources": ["https://en.wikipedia.org/wiki/Gaafaru"], "notes": "Check ferry days"})
        patch, calls = self._fake_client([
            NS(stop_reason="pause_turn", content=[NS(type="server_tool_use", name="web_search")]),
            NS(stop_reason="tool_use", content=[NS(type="text", text="Done"), submit]),
        ])
        with patch, mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}):
            r = self.client.post("/admin/ai-assist/", {"kind": "island", "name": "Gaafaru", "context": "North Malé atoll"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["fields"]["tagline"], "Surf breaks and a quiet harbour")
        self.assertEqual(data["fields"]["overview"], "")  # missing keys come back empty
        self.assertEqual(data["sources"], ["https://en.wikipedia.org/wiki/Gaafaru"])
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1]["messages"][-1]["role"], "assistant")  # resumed, no extra user turn
        self.assertTrue(calls[0]["tools"][-1]["strict"])
        self.assertIn("Gaafaru", calls[0]["messages"][0]["content"])

    def test_missing_key_and_errors_are_explained(self):
        import os
        from unittest import mock

        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
            r = self.client.post("/admin/ai-assist/", {"kind": "listing", "name": "Cozy Nest"})
        self.assertEqual(r.status_code, 502)
        self.assertIn("ANTHROPIC_API_KEY", r.json()["error"])
        self.assertEqual(self.client.post("/admin/ai-assist/", {"kind": "island", "name": ""}).status_code, 400)

    def test_staff_only_and_panel_shown(self):
        self.assertContains(self.client.get(reverse("admin:directory_island_add")), "Quick lookup")
        self.assertContains(self.client.get(reverse("admin:directory_listing_add")), "Quick lookup")
        self.client.logout()
        r = self.client.post("/admin/ai-assist/", {"kind": "island", "name": "Gaafaru"})
        self.assertEqual(r.status_code, 302)  # sent to the admin login


class AIAssistErrorTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser("ai2@x.mv", "ai2@x.mv", "pw"))

    def _err(self, msg):
        import anthropic
        import httpx2

        req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
        return anthropic.BadRequestError(msg, response=httpx2.Response(400, request=req),
                                         body={"type": "error", "error": {"type": "invalid_request_error", "message": msg}})

    def _run(self, beta_effects, plain_effects=()):
        import os
        from types import SimpleNamespace as NS
        from unittest import mock

        beta, plain = list(beta_effects), list(plain_effects)

        def pop(queue):
            def create(**kwargs):
                item = queue.pop(0)
                if isinstance(item, Exception):
                    raise item
                return item
            return create

        fake = NS(beta=NS(messages=NS(create=pop(beta))), messages=NS(create=pop(plain)))
        with mock.patch("anthropic.Anthropic", return_value=fake), mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k"}):
            return self.client.post("/admin/ai-assist/", {"kind": "island", "name": "Gaafaru"})

    def test_retries_without_optional_features(self):
        from types import SimpleNamespace as NS

        ok = NS(stop_reason="tool_use", content=[NS(type="tool_use", name="submit_details", input={"tagline": "Hi", "sources": []})])
        r = self._run([self._err("fallbacks: not available for this organization")], [ok])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["fields"]["tagline"], "Hi")

    def test_credit_and_real_reason_are_shown(self):
        r = self._run([self._err("Your credit balance is too low to access the Anthropic API.")])
        self.assertIn("no credit", r.json()["error"])
        r = self._run([self._err("first")], [self._err("tools.0: something specific")])
        self.assertIn("something specific", r.json()["error"])


class QuickLookupTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser("ql@x.mv", "ql@x.mv", "pw"))

    def fake_json(self, url, **kw):
        if "list=search" in url:
            return {"query": {"search": [{"title": "Gaafaru"}]}}
        if "prop=extracts" in url:
            return {"query": {"pages": {"1": {"title": "Gaafaru", "extract": "Gaafaru is an inhabited island of Kaafu Atoll.\nIt is known for shipwrecks.",
                                              "coordinates": [{"lat": 4.7356, "lon": 73.5003}], "pageprops": {"wikibase_item": "Q123"}}}}}
        if "wikidata" in url:
            return {"entities": {"Q123": {"claims": {
                "P1082": [{"mainsnak": {"datavalue": {"value": {"amount": "+1150", "unit": "1"}}},
                           "qualifiers": {"P585": [{"datavalue": {"value": {"time": "+2022-09-01T00:00:00Z"}}}]}}],
                "P2046": [{"mainsnak": {"datavalue": {"value": {"amount": "+21", "unit": "http://www.wikidata.org/entity/Q35852"}}}}]}}}}
        if "overpass" in url:
            return {"elements": [{"tags": {"amenity": "atm"}}, {"tags": {"amenity": "police"}}, {"tags": {"shop": "supermarket"}},
                                 {"tags": {"tourism": "guest_house", "name": "Reef Inn"}}, {"tags": {"amenity": "place_of_worship"}}]}
        if "nominatim" in url:
            return [{"osm_type": "node", "osm_id": 5, "address": {"island": "Fuvahmulah", "road": "Magu Rd"},
                     "extratags": {"phone": "+960 777 1234", "website": "https://cozynest.example"}}]
        raise AssertionError(url)

    def test_island_quick_lookup(self):
        from unittest import mock

        with mock.patch("directory.web_lookup._json", side_effect=self.fake_json):
            r = self.client.post("/admin/ai-assist/", {"kind": "island", "name": "Gaafaru", "mode": "quick", "context": "North Malé atoll"})
        f = r.json()["fields"]
        self.assertEqual((f["population"], f["population_year"], f["area_km2"]), ("1150", "2022", "0.21"))
        self.assertEqual((f["has_atm"], f["has_police"], f["has_supermarket"], f["has_pharmacy"]), ("yes", "yes", "yes", "unknown"))
        self.assertEqual(f["nearest_airport"], "Velana International (MLE)")
        self.assertIn("Kaafu", f["overview"])
        self.assertIn("Reef Inn", r.json()["notes"])

    def test_listing_quick_lookup_reads_website(self):
        from unittest import mock

        page = ('<html><head><meta property="og:description" content="Cosy rooms by the beach in Fuvahmulah."></head>'
                '<body>Email us: hello@cozynest.example Call +960 777 1234 <a href="https://wa.me/9607771234">WA</a>'
                ' <a href="https://www.instagram.com/cozynest">IG</a> Check-in 14:00, check-out 12:00. We have 18 rooms.</body></html>')
        with mock.patch("directory.web_lookup._json", side_effect=self.fake_json), mock.patch("directory.web_lookup._get", return_value=page):
            r = self.client.post("/admin/ai-assist/", {"kind": "listing", "name": "Cozy Nest", "mode": "quick"})
        f = r.json()["fields"]
        self.assertEqual(f["island_name"], "Fuvahmulah")
        self.assertEqual(f["contact_email"], "hello@cozynest.example")
        self.assertEqual(f["whatsapp"], "+9607771234")
        self.assertEqual((f["check_in_time"], f["check_out_time"], f["room_count"]), ("14:00", "12:00", "18"))
        self.assertIn("Cosy rooms", f["short_description"])

    def test_nothing_found(self):
        from unittest import mock

        def none(url, **kw):
            if "list=search" in url:
                return {"query": {"search": []}}
            return []
        with mock.patch("directory.web_lookup._json", side_effect=none):
            r = self.client.post("/admin/ai-assist/", {"kind": "island", "name": "Zzzz", "mode": "quick"})
        self.assertEqual(r.status_code, 404)
        self.assertIn("No Wikipedia article", r.json()["error"])


class ActivitySuggestionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_maldives", stdout=open("/dev/null", "w"))

    def test_suggests_existing_activities_from_text(self):
        from directory.web_lookup import suggest_activities

        found = suggest_activities("Closest island to Hanifaru Bay, where manta rays feed. Several dive centres and a sandbank nearby.")
        self.assertIn("Manta ray snorkeling", found)
        self.assertIn("Scuba diving", found)
        self.assertIn("Sandbank picnic", found)
        self.assertNotIn("Surfing", found)

    def test_activities_are_tick_boxes(self):
        self.client.force_login(User.objects.create_superuser("cb@x.mv", "cb@x.mv", "pw"))
        page = self.client.get(reverse("admin:directory_island_add")).content.decode()
        self.assertIn('type="checkbox" name="activities"', page)
        self.assertIn('data-autogrow="1"', page)
        page = self.client.get(reverse("admin:directory_listing_add")).content.decode()
        self.assertIn('type="checkbox" name="activity_types"', page)


class HealthcareAndMobileTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_maldives", stdout=open("/dev/null", "w"))

    def test_hospital_and_5g_shown(self):
        male = Island.objects.get(name="Malé")
        self.assertTrue(male.has_full_hospital and male.has_5g)
        page = self.client.get(male.get_absolute_url())
        self.assertContains(page, "Hospital")
        self.assertContains(page, "5G")
        thoddoo = Island.objects.get(slug="thoddoo")
        self.assertEqual(thoddoo.healthcare_label, "Health centre")
        self.assertEqual(thoddoo.mobile_data_label, "4G")


class HomeFeatureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_maldives", stdout=open("/dev/null", "w"))

    def test_chosen_islands_and_order_drive_the_home_page(self):
        from directory.models import HomeFeature

        HomeFeature.objects.all().delete()
        a, b, c = Island.objects.get(slug="thoddoo"), Island.objects.get(slug="maafushi"), Island.objects.get(slug="fulidhoo")
        for n, isl in enumerate((c, a, b), 1):
            HomeFeature.objects.create(section="portrait", island=isl, order=n)
        HomeFeature.objects.create(section="popular", island=a, order=1)
        r = self.client.get("/")
        self.assertEqual([i.slug for i in r.context["portraits"]], ["fulidhoo", "thoddoo", "maafushi"])
        self.assertEqual([i.slug for i in r.context["popular"]], ["thoddoo"])
        HomeFeature.objects.filter(section="popular").update(is_active=False)
        self.assertNotEqual([i.slug for i in self.client.get("/").context["popular"]], ["thoddoo"])  # falls back to Featured

    def test_admin_page(self):
        self.client.force_login(User.objects.create_superuser("hp@x.mv", "hp@x.mv", "pw"))
        self.assertEqual(self.client.get(reverse("admin:directory_homefeature_changelist")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:directory_homefeature_add")).status_code, 200)
