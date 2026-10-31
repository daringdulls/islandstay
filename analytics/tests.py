import json
import os
import uuid

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from directory.models import Enquiry, Listing

from .models import AnonymousPageview, Event, Visit, Visitor

UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1"


class TrackingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_maldives", "--demo", stdout=open(os.devnull, "w"))

    def beacon(self, events, vid, sid, consent="all", **headers):
        self.client.cookies["is_consent"] = consent
        if vid:
            self.client.cookies["is_vid"] = str(vid)
        return self.client.post("/t/", json.dumps({"vid": str(vid), "sid": str(sid), "lang": "de-DE", "events": events}),
                                content_type="text/plain", HTTP_USER_AGENT=UA, **headers)

    def test_full_journey_is_recorded_and_linked_to_request(self):
        vid, sid = uuid.uuid4(), uuid.uuid4()
        listing = Listing.objects.filter(status="approved", kind__in=Listing.STAY_KINDS).first()
        r = self.beacon([{"type": "pageview", "path": "/", "referrer": "https://www.google.com/", "t": 9000},
                         {"type": "search", "path": "/", "label": "Search", "value": "Dhangethi", "t": 8000},
                         {"type": "pageview", "path": listing.get_absolute_url(), "t": 5000},
                         {"type": "request_start", "path": listing.get_absolute_url(), "t": 2000},
                         {"type": "bogus", "path": "/"}], vid, sid,
                        HTTP_X_VERCEL_IP_COUNTRY="DE", HTTP_X_VERCEL_IP_CITY="M%C3%BCnchen")
        self.assertEqual(r.status_code, 204)
        v = Visitor.objects.get(pk=vid)
        self.assertEqual((v.country, v.city, v.device, v.first_source, v.visits, v.pageviews), ("DE", "München", "Mobile", "Google", 1, 2))
        self.assertEqual(Event.objects.filter(visitor=v).count(), 4)
        # The request made in the same browser is linked to the visitor
        self.client.post(listing.get_absolute_url(), {"guest_name": "Ana", "guest_email": "ana@example.com",
                                                      "preferred_contact": "email", "adults": 2, "children": 0},
                         HTTP_USER_AGENT=UA, HTTP_X_VERCEL_IP_COUNTRY="DE")
        e = Enquiry.objects.latest("id")
        self.assertEqual((e.visitor_id, e.source, e.country, e.device), (vid, "Google", "DE", "Mobile"))
        self.assertIsNone(e.ip_address)
        # The guest presses WhatsApp on the confirmation page
        self.client.post(reverse("directory:enquiry_sent_via", args=[e.reference]), {"channel": "whatsapp"})
        e.refresh_from_db()
        self.assertEqual(e.sent_via, "whatsapp")
        self.assertIsNotNone(e.sent_at)

    def test_declined_cookies_only_count_pages(self):
        self.beacon([{"type": "pageview", "path": "/islands/"}, {"type": "click", "path": "/", "label": "x"}], "", "", consent="necessary")
        self.assertEqual(Visitor.objects.count(), 0)
        self.assertEqual(AnonymousPageview.objects.get(path="/islands/").views, 1)

    def test_bots_and_staff_are_ignored(self):
        self.client.cookies["is_consent"] = "all"
        self.client.post("/t/", json.dumps({"vid": str(uuid.uuid4()), "sid": str(uuid.uuid4()), "events": [{"type": "pageview", "path": "/"}]}),
                         content_type="text/plain", HTTP_USER_AGENT="Googlebot/2.1")
        self.assertEqual(Visit.objects.count(), 0)

    def test_sent_via_requires_own_session(self):
        listing = Listing.objects.filter(status="approved").first()
        e = Enquiry.objects.create(listing=listing, guest_name="X", guest_email="x@example.com", message="")
        self.client.post(reverse("directory:enquiry_sent_via", args=[e.reference]), {"channel": "email"})
        e.refresh_from_db()
        self.assertEqual(e.sent_via, "")

    def test_admin_pages(self):
        vid, sid = uuid.uuid4(), uuid.uuid4()
        self.beacon([{"type": "pageview", "path": "/"}, {"type": "leave", "path": "/", "label": "12s", "value": "80"}], vid, sid)
        admin_user = get_user_model().objects.create_superuser("boss@x.mv", "boss@x.mv", "pw")
        self.client.force_login(admin_user)
        for days in (1, 30, 365):
            self.assertEqual(self.client.get(reverse("admin:analytics_dashboard") + f"?days={days}").status_code, 200)
        page = self.client.get(reverse("admin:analytics_visitor_change", args=[vid]))
        self.assertContains(page, "Journey")
        self.assertEqual(self.client.get(reverse("admin:analytics_visitor_changelist")).status_code, 200)
        e = Enquiry.objects.first()
        r = self.client.post(reverse("admin:directory_enquiry_changelist"), {"action": "export_csv", "_selected_action": [e.pk]})
        self.assertIn("Reference,Received", r.content.decode("utf-8-sig"))
        self.assertEqual(self.client.get(reverse("admin:directory_enquiry_change", args=[e.pk])).status_code, 200)

    def test_policy_pages(self):
        self.assertContains(self.client.get("/privacy/"), "Privacy policy")
        self.assertContains(self.client.get("/cookies/"), "is_vid")
        self.assertContains(self.client.get("/"), 'id="cookie-banner"')
