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
            "message": "Do you have a sea view room?", "website": "",
        })
        e = Enquiry.objects.get(guest_email="sara@example.com")
        self.assertRedirects(r, reverse("directory:enquiry_sent", args=[e.reference]))
        self.assertEqual(e.nights, 4)
        self.assertEqual(len(mail.outbox), 2)
        owner_mail, guest_mail = mail.outbox
        self.assertEqual(owner_mail.to, [self.listing.contact_email])
        self.assertEqual(owner_mail.reply_to, ["sara@example.com"])
        self.assertIn(e.reference, owner_mail.subject)
        self.assertEqual(guest_mail.to, ["sara@example.com"])

    def test_request_validation_and_honeypot(self):
        d = timezone.localdate() + timedelta(days=5)
        base = {"guest_name": "X", "guest_email": "x@example.com", "preferred_contact": "email", "adults": 1, "children": 0, "message": "hi"}
        r = self.client.post(self.listing.get_absolute_url(), {**base, "check_in": d, "check_out": d})
        self.assertContains(r, "Check-out must be after check-in")
        self.client.post(self.listing.get_absolute_url(), {**base, "website": "http://spam"})
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
        self.assertEqual(mail.outbox[0].to, ["ali@example.mv"])
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


class MapTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_maldives", stdout=open("/dev/null", "w"))

    def test_every_seeded_island_and_atoll_has_a_map_position(self):
        from .models import Atoll

        self.assertFalse(Island.objects.filter(latitude__isnull=True).exists())
        self.assertFalse(Atoll.objects.filter(map_lat__isnull=True).exists())

    def test_home_page_ships_map_data_and_atoll_index_north_to_south(self):
        import json
        import re

        r = self.client.get(reverse("directory:home"))
        data = json.loads(re.search(r'<script id="map-data" type="application/json">(.*?)</script>', r.content.decode(), re.S).group(1))
        self.assertEqual(len(data["islands"]), Island.objects.count())
        self.assertEqual(data["atolls"][0]["name"], "Haa Alif")
        dhangethi = next(i for i in data["islands"] if i["slug"] == "dhangethi")
        self.assertEqual(dhangethi["atoll"], "south-ari")
        html = r.content.decode()
        self.assertLess(html.index('data-atoll-link="haa-alif"'), html.index('data-atoll-link="addu"'))
        self.assertContains(r, "vendor/leaflet/leaflet.js")

    def test_island_page_has_focused_mini_map(self):
        r = self.client.get(reverse("directory:island_detail", args=["dhangethi"]))
        self.assertContains(r, 'data-focus-island="dhangethi"')
        self.assertContains(r, 'data-focus-atoll="south-ari"')


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
