import datetime as dt

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from directory.models import Atoll, Island

from .messages import DEFAULT_MESSAGES, fill
from .models import HostLead, OutreachMessage


class OutreachTests(TestCase):
    def setUp(self):
        atoll = Atoll.objects.create(name="Kaafu", slug="kaafu")
        self.island = Island.objects.create(name="Maafushi", slug="maafushi", atoll=atoll)
        self.assertEqual(OutreachMessage.objects.count(), len(DEFAULT_MESSAGES))  # added by the data migration
        self.admin = get_user_model().objects.create_superuser("boss@x.mv", "boss@x.mv", "pw")
        self.client.force_login(self.admin)

    def test_messages_speak_as_island_stay(self):
        for m in OutreachMessage.objects.all():
            for word in (" I ", "I'm", "I'll", " me ", " my "):
                self.assertNotIn(word, f" {m.text} ", m.use)

    def test_fill_and_follow_up_dates(self):
        lead = HostLead.objects.create(business="Coral View", island=self.island, instagram="@coralview")
        first = OutreachMessage.objects.get(use="First DM")
        text = fill(first.text, lead, views=42)
        self.assertIn("Coral View", text)
        self.assertIn("Maafushi", text)
        self.assertIn("42", fill(OutreachMessage.objects.get(use="Follow-up 1").text, lead, views=42))
        lead.mark("messaged")
        self.assertEqual(lead.next_follow_up, timezone.localdate() + dt.timedelta(days=3))
        lead.mark("followup1")
        self.assertEqual(lead.next_follow_up, timezone.localdate() + dt.timedelta(days=7))
        lead.mark("listed")
        self.assertIsNone(lead.next_follow_up)
        self.assertEqual(lead.date_listed, timezone.localdate())
        self.assertEqual(lead.instagram_url, "https://instagram.com/coralview")

    def test_admin_pages_and_sent_button(self):
        lead = HostLead.objects.create(business="Coral View", island=self.island, whatsapp="+960 777 1234")
        r = self.client.get(f"/admin/outreach/hostlead/{lead.pk}/change/")
        self.assertContains(r, "Messages for Coral View")
        self.assertContains(r, "Hello Coral View team!")
        self.assertContains(r, "https://wa.me/9607771234?text=")
        first = OutreachMessage.objects.get(use="First DM")
        r = self.client.post(f"/admin/outreach/hostlead/{lead.pk}/sent/", {"message": first.pk})
        self.assertEqual(r.json()["status"], "Messaged")
        lead.refresh_from_db()
        self.assertEqual((lead.status, lead.first_contact), ("messaged", timezone.localdate()))
        HostLead.objects.filter(pk=lead.pk).update(next_follow_up=timezone.localdate() - dt.timedelta(days=1))
        for url in ["/admin/outreach/hostlead/", "/admin/outreach/hostlead/?due=yes", "/admin/outreach/hostlead/?status__in=messaged,followup1,followup2",
                    "/admin/outreach/outreachmessage/", "/admin/outreach/hostlead/dashboard/", "/admin/outreach/hostlead/add/"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        r = self.client.get("/admin/outreach/hostlead/dashboard/")
        self.assertContains(r, "Follow-ups due")
        self.assertContains(r, "Coral View")
        r = self.client.post("/admin/outreach/hostlead/dashboard/", {"start_date": "2026-11-23"})
        self.assertEqual(r.status_code, 302)


class LeadFormTests(TestCase):
    def test_pasted_links_become_handles(self):
        from .admin import _handle
        self.assertEqual(_handle("https://www.instagram.com/coral.view/?hl=en", "instagram.com/"), "@coral.view")
        self.assertEqual(_handle("coral.view", "instagram.com/"), "@coral.view")
        self.assertEqual(_handle("https://www.tiktok.com/@reefboys", "tiktok.com/"), "@reefboys")
        self.assertEqual(_handle("", "instagram.com/"), "")

    def test_add_page_and_local_number(self):
        admin = get_user_model().objects.create_superuser("b2@x.mv", "b2@x.mv", "pw")
        self.client.force_login(admin)
        r = self.client.get("/admin/outreach/hostlead/add/")
        self.assertContains(r, "Quick fill")
        self.assertContains(r, "qf-islands")
        r = self.client.post("/admin/outreach/hostlead/add/", {"business": "Reef Boys", "kind": "excursion", "channel": "instagram",
                                                                "status": "messaged", "instagram": "https://instagram.com/reefboys/",
                                                                "whatsapp": "7771234"})
        self.assertEqual(r.status_code, 302)
        lead = HostLead.objects.get(business="Reef Boys")
        self.assertEqual((lead.instagram, lead.whatsapp, lead.first_contact), ("@reefboys", "+960 777 1234", timezone.localdate()))
        self.assertIsNotNone(lead.next_follow_up)
