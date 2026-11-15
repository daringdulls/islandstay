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


class PartnerProgrammeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_maldives", "--demo", stdout=open("/dev/null", "w"))
        cls.owner = User.objects.get(username="owner@demo.mv")
        cls.listing = Listing.objects.get(name="Coral Breeze Inn")

    def setUp(self):
        LinkPlan.objects.create(listing=self.listing)
        self.url = reverse("links:partners", args=[self.listing.pk])

    def start(self, **extra):
        self.client.force_login(self.owner)
        data = {"action": "settings", "is_active": "on", "joining": "open", "commission_type": "percent", "rate": "10", "currency": "USD",
                "terms": "Paid within 14 days of check-out."}
        data.update(extra)
        self.client.post(self.url, data)
        from .models import Programme
        return Programme.objects.get(listing=self.listing)

    def book_via(self, url, email="guest@example.com"):
        guest = self.client_class()
        guest.get(url, **BROWSER)
        d = timezone.localdate() + timedelta(days=10)
        guest.post(self.listing.get_absolute_url(), {"guest_name": "Maria Lopez", "guest_email": email, "preferred_contact": "email",
                                                     "check_in": d, "check_out": d + timedelta(days=4), "adults": 2, "children": 0,
                                                     "hp_leave_empty": ""}, **BROWSER)
        return Enquiry.objects.get(guest_email=email)

    def test_needs_pro_plan(self):
        LinkPlan.objects.all().delete()
        self.client.force_login(self.owner)
        self.assertRedirects(self.client.get(self.url), reverse("links:manage", args=[self.listing.pk]))

    def test_partner_applies_gets_approved_and_earns_commission(self):
        from .models import Commission, Membership, Partner
        prog = self.start()
        self.assertEqual(prog.offer, "10% of each booking")
        # a creator signs up and applies from the public page
        creator = self.client_class()
        self.assertContains(creator.get(reverse("links:partner_landing")), "Coral Breeze Inn")
        creator.post(reverse("links:partner_join"), {"name": "Aishath Travels", "email": "aish@example.com", "password": "lagoon-2026-x",
                                                      "instagram": "@aish", "audience": "10k", "payout": "BML 7730000123"})
        partner = Partner.objects.get(name="Aishath Travels")
        creator.post(reverse("links:partner_dashboard"), {"action": "apply", "programme": prog.pk, "message": "I post Maafushi trips"})
        m = Membership.objects.get(partner=partner)
        self.assertEqual((m.status, m.link), ("applied", None))
        # the property approves: the partner gets a link
        self.client.post(self.url, {"action": "approve", "id": m.pk})
        m.refresh_from_db()
        self.assertEqual(m.status, "active")
        self.assertEqual(m.link.code, "coral-breeze-inn-aishath-travels")
        dash = creator.get(reverse("links:partner_dashboard"))
        self.assertContains(dash, f"/r/{m.link.code}/")
        self.assertEqual(creator.get(reverse("links:qr", args=[m.link.pk, "svg"])).status_code, 200)
        # partner links stay off the owner's own tracked-links list
        self.assertNotContains(self.client.get(reverse("links:manage", args=[self.listing.pk])), m.link.code)

        # a guest books through the link; the owner confirms and records the value
        e = self.book_via(m.link.get_absolute_url())
        self.assertContains(self.client.get(self.url), e.reference)
        e.status = "confirmed"
        e.save()
        page = self.client.get(reverse("directory:enquiry_detail", args=[e.reference]))
        self.assertContains(page, "Booked via a partner")
        self.client.post(self.url, {"action": "record", "ref": e.reference, "value": "480"})
        c = Commission.objects.get()
        self.assertEqual((str(c.amount), c.status, c.nights), ("48.00", "pending", 4))
        self.client.post(self.url, {"action": "record", "ref": e.reference, "value": "480"})  # no double commission
        self.assertEqual(Commission.objects.count(), 1)

        # partner sees it with limited guest details
        dash = creator.get(reverse("links:partner_dashboard"))
        self.assertContains(dash, "Maria L.")
        self.assertNotContains(dash, "guest@example.com")

        # after the stay: approve, pay, partner confirms receipt
        self.client.post(self.url, {"action": "c_approve", "id": c.pk})
        self.client.post(self.url, {"action": "c_paid", "id": c.pk, "reference": "BML-1234"})
        c.refresh_from_db()
        self.assertEqual((c.status, c.paid_reference), ("paid", "BML-1234"))
        creator.post(reverse("links:partner_dashboard"), {"action": "received", "id": c.pk})
        c.refresh_from_db()
        self.assertIsNotNone(c.received_at)

    def test_invite_paused_partner_and_fixed_commission(self):
        from .models import Commission, Membership
        prog = self.start(joining="invite", commission_type="night", rate="15")
        self.assertNotContains(self.client.get(reverse("links:partner_landing")), "Coral Breeze Inn")  # invite only
        r = self.client.post(self.url, {"action": "invite", "name": "Group Leader Ali", "email": "ali@example.com"}, follow=True)
        self.assertContains(r, "Group Leader Ali is in")
        self.assertContains(r, "/accounts/welcome/")
        m = Membership.objects.get(partner__name="Group Leader Ali")
        self.assertEqual(m.status, "active")
        e = self.book_via(m.link.get_absolute_url())
        e.status = "confirmed"
        e.save()
        self.client.post(self.url, {"action": "record", "ref": e.reference, "nights": "4"})
        self.assertEqual(str(Commission.objects.get().amount), "60.00")
        self.client.post(self.url, {"action": "c_reject", "id": Commission.objects.get().pk, "note": "Cancelled"})
        self.assertEqual(Commission.objects.get().status, "rejected")
        # paused partners' links still open the page but no longer count
        self.client.post(self.url, {"action": "pause", "id": m.pk})
        before = TrackedLink.objects.get(pk=m.link_id).clicks
        r = self.client_class().get(m.link.get_absolute_url(), **BROWSER)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(TrackedLink.objects.get(pk=m.link_id).clicks, before)

    def test_other_owner_cannot_touch_commissions(self):
        self.start()
        other = User.objects.create_user("o@x.mv", "o@x.mv", "pw")
        self.client.force_login(other)
        self.assertEqual(self.client.get(self.url).status_code, 404)
