import re

from django.contrib.auth import get_user_model
from django.test import TestCase

from directory.models import Atoll, Island, Listing


class OwnerInviteTests(TestCase):
    def setUp(self):
        atoll = Atoll.objects.create(name="Baa", slug="baa")
        self.island = Island.objects.create(name="Fehendhoo", slug="fehendhoo", atoll=atoll)
        self.admin = get_user_model().objects.create_superuser("boss@x.mv", "boss@x.mv", "pw")
        self.client.force_login(self.admin)

    def add(self, **extra):
        data = {"name": "Tropical Tree", "slug": "", "kind": "guesthouse", "island": self.island.pk, "short_description": "Garden rooms",
                "description": "Garden rooms near the bikini beach.", "status": "approved", "contact_name": "Ahmed Rasheed", "contact_phone": "", "currency": "USD",
                "price_unit": "night", "rooms-TOTAL_FORMS": "0", "rooms-INITIAL_FORMS": "0", "routes-TOTAL_FORMS": "0", "routes-INITIAL_FORMS": "0"}
        data.update(extra)
        return self.client.post("/admin/directory/listing/add/", data)

    def test_listing_with_owner_email_creates_account_and_invite(self):
        r = self.add(owner_email="Owner@Tropical.mv")
        self.assertEqual(r.status_code, 302, getattr(r, "context", None) and r.context["adminform"].form.errors)
        listing = Listing.objects.get(name="Tropical Tree")
        owner = listing.owner
        self.assertEqual((owner.username, owner.email, owner.has_usable_password()), ("owner@tropical.mv", "owner@tropical.mv", False))
        self.assertEqual((listing.contact_email, listing.is_claimed), ("owner@tropical.mv", True))
        page = self.client.get(f"/admin/directory/listing/{listing.pk}/change/").content.decode()
        self.assertIn("Copy invite message", page)
        link = re.search(r"/accounts/welcome/[^/]+/[^/\"]+/", page).group(0)
        # the owner opens the link and sets a password
        self.client.logout()
        r = self.client.get(link, follow=True)
        self.assertContains(r, "Welcome to Island Stay")
        r = self.client.post(r.redirect_chain[-1][0] if r.redirect_chain else link,
                             {"new_password1": "Coral-reef-2026!", "new_password2": "Coral-reef-2026!"})
        self.assertRedirects(r, "/dashboard/", fetch_redirect_response=False)
        owner.refresh_from_db()
        self.assertTrue(owner.has_usable_password())
        self.assertEqual(int(self.client.session["_auth_user_id"]), owner.pk)
        r = self.client.get(link)  # used links stop working
        self.assertContains(r, "This link has expired")

    def test_existing_account_is_reused_and_empty_email_keeps_it_with_island_stay(self):
        existing = get_user_model().objects.create_user("host@x.mv", "host@x.mv", "pw12345678")
        self.add(owner_email="host@x.mv", name="Reef House")
        self.assertEqual(Listing.objects.get(name="Reef House").owner, existing)
        self.add(name="Unclaimed Place", contact_email="bookings@x.mv")
        unclaimed = Listing.objects.get(name="Unclaimed Place")
        self.assertEqual((unclaimed.owner, unclaimed.is_claimed), (self.admin, False))
        r = self.add(name="No Email Place")
        self.assertEqual(r.status_code, 200)  # needs a contact or owner email
        self.assertFalse(Listing.objects.filter(name="No Email Place").exists())


class OwnerEmailFieldTests(TestCase):
    def setUp(self):
        atoll = Atoll.objects.create(name="Baa", slug="baa")
        self.island = Island.objects.create(name="Fehendhoo", slug="fehendhoo", atoll=atoll)
        self.admin = get_user_model().objects.create_superuser("boss@x.mv", "boss@x.mv", "pw")
        self.client.force_login(self.admin)

    def test_field_shows_and_changes_owner(self):
        page = self.client.get("/admin/directory/listing/add/").content.decode()
        self.assertIn('name="owner_email"', page)
        self.assertIn('type="email"', page)
        self.assertNotIn('name="owner"', page)  # no account dropdown
        base = {"name": "Reef House", "slug": "", "kind": "guesthouse", "island": self.island.pk, "short_description": "Rooms",
                "description": "Rooms by the reef.", "status": "approved", "contact_name": "Aisha", "currency": "USD", "price_unit": "night",
                "rooms-TOTAL_FORMS": "0", "rooms-INITIAL_FORMS": "0", "routes-TOTAL_FORMS": "0", "routes-INITIAL_FORMS": "0"}
        self.client.post("/admin/directory/listing/add/", {**base, "owner_email": "first@x.mv"})
        listing = Listing.objects.get(name="Reef House")
        self.assertEqual(listing.owner.email, "first@x.mv")
        page = self.client.get(f"/admin/directory/listing/{listing.pk}/change/").content.decode()
        self.assertIn('value="first@x.mv"', page)
        self.client.post(f"/admin/directory/listing/{listing.pk}/change/", {**base, "slug": listing.slug, "owner_email": "second@x.mv",
                                                                           "contact_email": "first@x.mv"})
        listing.refresh_from_db()
        self.assertEqual(listing.owner.email, "second@x.mv")
        self.client.post(f"/admin/directory/listing/{listing.pk}/change/", {**base, "slug": listing.slug, "owner_email": "",
                                                                           "contact_email": "first@x.mv"})
        listing.refresh_from_db()
        self.assertEqual((listing.owner, listing.is_claimed), (self.admin, False))


class ListingSlugTests(TestCase):
    def setUp(self):
        atoll = Atoll.objects.create(name="Gnaviyani", slug="gnaviyani")
        self.island = Island.objects.create(name="Fuvahmulah", slug="fuvahmulah", atoll=atoll)
        self.admin = get_user_model().objects.create_superuser("boss@x.mv", "boss@x.mv", "pw")
        self.client.force_login(self.admin)

    def post(self, name, slug=""):
        self.client.post("/admin/directory/listing/add/", {
            "name": name, "slug": slug, "kind": "guesthouse", "island": self.island.pk, "short_description": "Rooms",
            "description": "Rooms by the reef.", "status": "approved", "contact_name": "Aisha", "currency": "USD", "price_unit": "night",
            "owner_email": "o@x.mv", "rooms-TOTAL_FORMS": "0", "rooms-INITIAL_FORMS": "0", "routes-TOTAL_FORMS": "0", "routes-INITIAL_FORMS": "0"})
        return Listing.objects.filter(name=name).latest("pk").slug

    def test_slug_comes_from_name_without_repeating_island(self):
        self.assertEqual(self.post("Cozy Nest"), "cozy-nest-fuvahmulah")
        self.assertEqual(self.post("Cozy Nest Fuvahmulah"), "cozy-nest-fuvahmulah-2")
        self.assertEqual(self.post("Tiger Dive", slug="Tiger Dive FM"), "tiger-dive-fm")

    def test_add_page_has_address_prefix_and_steps(self):
        page = self.client.get("/admin/directory/listing/add/").content.decode()
        self.assertIn("islandstaymv.com/listing/", page)  # live address preview (JS)
        self.assertIn("nl-steps", page)
