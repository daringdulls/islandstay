from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from directory.models import Enquiry, Listing
from partners.models import AdEnquiry

from .models import LinkLead, LinkPlan, LinkVisit, TrackedLink

User = get_user_model()
BROWSER = {"HTTP_USER_AGENT": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari/604.1"}


class TrackedLinksTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_maldives", "--demo", stdout=open("/dev/null", "w"))
        cls.owner = User.objects.get(username="owner@demo.mv")
        cls.listing = Listing.objects.get(name="Coral Breeze Inn")

    def manage_url(self):
        return reverse("links:manage", args=[self.listing.pk])

    def test_without_plan_owner_sees_offer_and_can_request_it(self):
        self.client.force_login(self.owner)
        r = self.client.get(self.manage_url())
        self.assertContains(r, "Switch on Tracked links")
        self.client.post(self.manage_url(), {"action": "request"})
        self.assertTrue(AdEnquiry.objects.filter(interest="links", company=self.listing.name).exists())
        self.assertContains(self.client.get(self.manage_url()), "Request received")
        # can't sneak a link in without a plan
        self.client.post(self.manage_url(), {"label": "IG", "channel": "instagram"})
        self.assertFalse(TrackedLink.objects.exists())

    def test_other_users_cannot_open_the_page(self):
        other = User.objects.create_user("x@x.mv", "x@x.mv", "pw")
        self.client.force_login(other)
        self.assertEqual(self.client.get(self.manage_url()).status_code, 404)

    def test_full_flow_link_visit_and_credited_request(self):
        LinkPlan.objects.create(listing=self.listing)
        self.client.force_login(self.owner)
        self.client.post(self.manage_url(), {"label": "Instagram bio", "channel": "instagram", "to_form": "on"})
        link = TrackedLink.objects.get()
        self.assertEqual(link.code, "coral-breeze-inn-ig")
        page = self.client.get(self.manage_url())
        self.assertContains(page, "/r/coral-breeze-inn-ig/")
        self.assertEqual(self.client.get(reverse("links:qr", args=[link.pk, "svg"])).status_code, 200)
        self.assertEqual(self.client.get(reverse("links:qr", args=[link.pk, "png"]))["Content-Type"], "image/png")

        guest = self.client_class()
        r = guest.get("/r/coral-breeze-inn-ig/", **BROWSER)
        self.assertRedirects(r, self.listing.get_absolute_url() + "#request", fetch_redirect_response=False)
        guest.get("/r/coral-breeze-inn-ig/", HTTP_USER_AGENT="facebookexternalhit/1.1")  # link previews don't count
        link.refresh_from_db()
        self.assertEqual((link.clicks, LinkVisit.objects.get().device), (1, "mobile"))

        d = timezone.localdate() + timedelta(days=10)
        guest.post(self.listing.get_absolute_url(), {"guest_name": "Sara", "guest_email": "sara@example.com", "preferred_contact": "email",
                                                     "check_in": d, "check_out": d + timedelta(days=3), "adults": 2, "children": 0,
                                                     "hp_leave_empty": ""}, **BROWSER)
        lead = LinkLead.objects.get()
        self.assertEqual((lead.link, lead.enquiry.guest_email), (link, "sara@example.com"))
        self.assertContains(self.client.get(self.manage_url()), "Sara")

        # a request from someone who never used the link isn't credited
        self.client_class().post(self.listing.get_absolute_url(), {"guest_name": "Ann", "guest_email": "ann@example.com",
                                                                    "preferred_contact": "email", "adults": 2, "children": 0, "hp_leave_empty": ""})
        self.assertTrue(Enquiry.objects.filter(guest_email="ann@example.com").exists())
        self.assertEqual(LinkLead.objects.count(), 1)

    def test_expired_plan_keeps_links_working_without_counting(self):
        plan = LinkPlan.objects.create(listing=self.listing)
        link = TrackedLink.objects.create(listing=self.listing, code="cbi-flyer", label="Flyer", channel="print")
        plan.ends = timezone.localdate() - timedelta(days=1)
        plan.save()
        r = self.client.get("/r/cbi-flyer/", **BROWSER)
        self.assertRedirects(r, self.listing.get_absolute_url(), fetch_redirect_response=False)
        link.refresh_from_db()
        self.assertEqual(link.clicks, 0)
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(self.manage_url()), "Renew Tracked links")

    def test_custom_codes_are_cleaned_and_unique(self):
        LinkPlan.objects.create(listing=self.listing)
        TrackedLink.objects.create(listing=self.listing, code="taken", label="x")
        self.client.force_login(self.owner)
        r = self.client.post(self.manage_url(), {"label": "A", "channel": "whatsapp", "code": "taken"})
        self.assertContains(r, "That short link is taken")
        self.client.post(self.manage_url(), {"label": "B", "channel": "whatsapp", "code": "Coral WA Status!"})
        self.assertTrue(TrackedLink.objects.filter(code="coral-wa-status").exists())
        self.assertEqual(self.client.get("/r/nope-not-here/").status_code, 404)
