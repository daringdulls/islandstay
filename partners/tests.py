import datetime as dt

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from directory.models import Island

from .models import AdEnquiry, AffiliateOffer, Click, Placement, Sponsor


class PartnerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        import os
        call_command("seed_maldives", "--demo", stdout=open(os.devnull, "w"))

    def setUp(self):
        today = timezone.localdate()
        self.island = Island.objects.filter(is_published=True).first()
        self.other = Island.objects.filter(is_published=True).exclude(pk=self.island.pk).first()
        s = Sponsor.objects.create(name="Reef Dive Co")
        self.p = Placement.objects.create(sponsor=s, where="island", headline="Dive the kandu with us", link="https://example.com/dive",
                                          starts=today - dt.timedelta(days=1), ends=today + dt.timedelta(days=10))
        self.p.islands.add(self.island)
        Placement.objects.create(sponsor=s, where="island", headline="Old campaign", link="https://example.com/old",
                                 starts=today - dt.timedelta(days=30), ends=today - dt.timedelta(days=2))
        self.offer = AffiliateOffer.objects.create(name="SafeTrip", slug="safetrip", category="insurance", title="Travel insurance that covers diving",
                                                   url="https://partner.example.com/?aff=islandstay")

    def test_island_page_shows_live_targeted_sponsor_and_offers(self):
        r = self.client.get(self.island.get_absolute_url(), HTTP_USER_AGENT="Mozilla/5.0")
        self.assertContains(r, "Dive the kandu with us")
        self.assertNotContains(r, "Old campaign")
        self.assertContains(r, "Sponsored")
        self.assertContains(r, 'rel="sponsored noopener"')
        self.assertContains(r, "Travel insurance that covers diving")
        self.assertContains(r, "We may earn a commission")
        self.p.refresh_from_db()
        self.assertEqual(self.p.views, 1)
        r = self.client.get(self.other.get_absolute_url(), HTTP_USER_AGENT="Mozilla/5.0")
        self.assertNotContains(r, "Dive the kandu with us")  # targeted at another island

    def test_bots_are_not_counted(self):
        self.client.get(self.island.get_absolute_url(), HTTP_USER_AGENT="Googlebot/2.1")
        self.p.refresh_from_db()
        self.assertEqual(self.p.views, 0)
        r = self.client.get(f"/go/s/{self.p.pk}/", HTTP_USER_AGENT="facebookexternalhit/1.1")
        self.assertEqual(r.status_code, 302)
        self.p.refresh_from_db()
        self.assertEqual(self.p.clicks, 0)

    def test_click_redirects_and_counts(self):
        r = self.client.get(f"/go/s/{self.p.pk}/?from=/islands/x/&island={self.island.slug}", HTTP_USER_AGENT="Mozilla/5.0")
        self.assertEqual((r.status_code, r["Location"]), (302, "https://example.com/dive"))
        r = self.client.get("/go/safetrip/", HTTP_USER_AGENT="Mozilla/5.0")
        self.assertEqual(r["Location"], "https://partner.example.com/?aff=islandstay")
        self.p.refresh_from_db(); self.offer.refresh_from_db()
        self.assertEqual((self.p.clicks, self.offer.clicks), (1, 1))
        self.assertEqual(Click.objects.get(placement=self.p).island, self.island.slug)
        self.assertEqual(self.client.get("/go/nope/").status_code, 404)

    def test_unsafe_link_is_refused(self):
        bad = AffiliateOffer.objects.create(name="X", slug="x", category="other", title="x", url="javascript:alert(1)")
        self.assertEqual(self.client.get("/go/x/").status_code, 404)

    def test_advertise_form_and_admin(self):
        r = self.client.get("/advertise/")
        self.assertContains(r, "Ask for our rate card")
        r = self.client.post("/advertise/", {"name": "Aisha", "company": "Island Telecom", "email": "a@example.com", "interest": "island"})
        self.assertRedirects(r, "/advertise/thanks/")
        self.assertEqual(AdEnquiry.objects.count(), 1)
        self.client.post("/advertise/", {"name": "Bot", "company": "Spam", "email": "s@example.com", "website": "http://spam"})
        self.assertEqual(AdEnquiry.objects.count(), 1)
        admin = get_user_model().objects.create_superuser("boss@x.mv", "boss@x.mv", "pw")
        self.client.force_login(admin)
        for url in ["/admin/partners/placement/", "/admin/partners/affiliateoffer/", "/admin/partners/sponsor/",
                    "/admin/partners/adenquiry/", f"/admin/partners/placement/{self.p.pk}/report/", "/admin/partners/placement/add/"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)


class PreviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        import os
        call_command("seed_maldives", "--demo", stdout=open(os.devnull, "w"))

    def test_samples_only_in_admin_preview(self):
        from .samples import create_samples, remove_samples
        n = create_samples(Sponsor, Placement, AffiliateOffer, Island, today=timezone.localdate())
        self.assertEqual(n, 9)
        self.assertEqual(create_samples(Sponsor, Placement, AffiliateOffer, Island), 0)  # only once
        island = Island.objects.filter(is_published=True).first()
        for url in (island.get_absolute_url(), "/islands/", "/transport/"):
            r = self.client.get(url, HTTP_USER_AGENT="Mozilla/5.0")
            self.assertNotContains(r, "Sample:")
        self.assertEqual(self.client.get("/go/sample-esim/").status_code, 404)
        sample = Placement.objects.filter(is_sample=True).first()
        self.assertEqual(self.client.get(f"/go/s/{sample.pk}/").status_code, 404)
        admin = get_user_model().objects.create_superuser("boss2@x.mv", "boss2@x.mv", "pw")
        self.client.force_login(admin)
        r = self.client.get("/admin/partners/placement/preview/")
        self.assertContains(r, "Island hopping made simple".split()[0])
        self.assertContains(r, "Advertise with us page")
        r = self.client.get(f"/admin/partners/placement/preview/frame/?placement={sample.pk}")
        self.assertContains(r, sample.headline)
        self.assertEqual(r["X-Frame-Options"], "SAMEORIGIN")
        r = self.client.get("/admin/partners/placement/preview/frame/?offers=all")
        self.assertContains(r, "Before you go")
        r = self.client.get("/admin/partners/placement/preview/frame/?kind=placement&headline=Typed+now&where=guide&button=Go")
        self.assertContains(r, "Typed now")
        r = self.client.get("/admin/partners/placement/preview/frame/?kind=offer&title=New+eSIM&category=esim")
        self.assertContains(r, "New eSIM")
        self.assertContains(self.client.get(f"/admin/partners/placement/{sample.pk}/change/"), 'id="pp-frame"')
        self.client.post("/admin/partners/placement/preview/", {"samples": "remove"})
        self.assertFalse(Placement.objects.filter(is_sample=True).exists())
        self.assertFalse(Sponsor.objects.filter(is_sample=True).exists())
