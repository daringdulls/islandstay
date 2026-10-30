from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Enquiry, Island, Listing

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
        self.assertContains(r, "famous for")

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
        r = self.client.get(reverse("directory:stay_list"), {"max_price": "80"})
        self.assertContains(r, "Coral Breeze Inn")
        self.assertNotContains(r, "Lagoon View Hotel")
