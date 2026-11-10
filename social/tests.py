import os

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import SocialPost
from .planner import generate_plan


class SocialPlanTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_maldives", "--demo", stdout=open(os.devnull, "w"))
        cls.admin = get_user_model().objects.create_superuser("boss@x.mv", "boss@x.mv", "pw")

    def setUp(self):
        self.client.force_login(self.admin)

    def test_plan_drafts_six_posts_a_week_without_repeating_islands(self):
        posts = generate_plan(weeks=2)
        self.assertEqual(len(posts), 12)
        self.assertTrue(all(p.status == "draft" and p.publish_at for p in posts))
        spotlights = [p.island_id for p in posts if p.template == "island"]
        self.assertEqual(len(spotlights), len(set(spotlights)))
        self.assertTrue(all("#IslandStay" in p.hashtags for p in posts))
        # A second run continues with islands not posted yet.
        later = generate_plan(weeks=1)
        self.assertFalse({p.island_id for p in later if p.template == "island"} & set(spotlights))

    def test_admin_pages_render(self):
        generate_plan(weeks=1)
        post = SocialPost.objects.first()
        for url in [reverse("admin:social_calendar"), reverse("admin:social_templates"),
                    reverse("admin:social_templates") + "?format=landscape", reverse("admin:social_playbook"),
                    reverse("admin:social_socialpost_changelist"), reverse("admin:social_socialpost_add") + "?template=fact",
                    reverse("admin:social_socialpost_design", args=[post.pk]) + "?format=story"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_calendar_button_drafts_plan(self):
        r = self.client.post(reverse("admin:social_calendar"), {"weeks": "2"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(SocialPost.objects.count(), 12)

    def test_image_proxy_only_allows_known_hosts(self):
        r = self.client.get(reverse("admin:social_image_proxy"), {"u": "https://evil.example.com/x.jpg"})
        self.assertEqual(r.status_code, 404)

    def test_headline_accent_split(self):
        p = SocialPost(headline="Stay on Dhangethi", accent_word="Dhangethi")
        self.assertEqual(p.headline_parts, ("Stay on ", "Dhangethi", ""))


class SocialTemplateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_maldives", "--demo", stdout=open(os.devnull, "w"))
        cls.admin = get_user_model().objects.create_superuser("boss2@x.mv", "boss2@x.mv", "pw")

    def test_every_template_renders_in_every_format(self):
        self.client.force_login(self.admin)
        for fmt in SocialPost.FORMAT_SIZES:
            r = self.client.get(reverse("admin:social_templates"), {"format": fmt})
            self.assertEqual(r.status_code, 200)
            for key, _ in SocialPost.TEMPLATE_CHOICES:
                self.assertContains(r, f"sp-{key} sp-{fmt}")

    def test_body_pairs(self):
        p = SocialPost(body="Dec – Apr | Dry season\nAll year")
        self.assertEqual(p.body_pairs, [("Dec – Apr", "Dry season"), ("", "All year")])
