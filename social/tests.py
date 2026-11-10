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


class MonthPlanTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_maldives", "--demo", stdout=open(os.devnull, "w"))
        cls.admin = get_user_model().objects.create_superuser("boss3@x.mv", "boss3@x.mv", "pw")

    def test_month_plan_has_feed_reels_and_stories_in_a_checkerboard(self):
        from .planner import generate_month
        posts = generate_month(2026, 12)
        types = {t: sum(p.post_type == t for p in posts) for t in ("feed", "carousel", "reel", "story")}
        self.assertGreaterEqual(types["reel"], 4)
        self.assertGreaterEqual(types["story"], 12)
        self.assertEqual(types["carousel"], 1)
        self.assertTrue(all(p.format == "story" for p in posts if p.post_type in ("reel", "story")))
        self.assertTrue(all(p.script for p in posts if p.post_type in ("reel", "story", "carousel")))
        photo = {"island", "experience", "host", "stay", "compare", "hostcall"}
        grid = [p.template in photo for p in sorted(posts, key=lambda p: p.publish_at) if p.on_grid]
        self.assertTrue(all(a != b for a, b in zip(grid, grid[1:])), grid)

    def test_plan_button_feed_page_and_swap(self):
        self.client.force_login(self.admin)
        r = self.client.post(reverse("admin:social_calendar"), {"plan_month": "2026-12"})
        self.assertEqual(r.status_code, 302)
        n = SocialPost.objects.count()
        self.client.post(reverse("admin:social_calendar"), {"plan_month": "2026-12"})
        self.assertEqual(SocialPost.objects.count(), n)  # no duplicates without "replace"
        r = self.client.get(reverse("admin:social_feed"), {"month": "2026-12"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "ig-tile")
        a, b = SocialPost.objects.order_by("publish_at")[:2]
        ta, tb = a.publish_at, b.publish_at
        r = self.client.post(reverse("admin:social_feed_swap"), {"a": a.pk, "b": b.pk})
        self.assertEqual(r.json(), {"ok": True})
        a.refresh_from_db(); b.refresh_from_db()
        self.assertEqual((a.publish_at, b.publish_at), (tb, ta))
        r = self.client.get(reverse("admin:social_socialpost_design", args=[SocialPost.objects.filter(post_type="reel").first().pk]))
        self.assertContains(r, "Reel shot list")


import tempfile  # noqa: E402

from django.test import override_settings  # noqa: E402


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="ig-test-"))
class InstagramPublishTests(TestCase):
    """The Instagram API is faked: each test lists what Instagram answers."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_maldives", "--demo", stdout=open(os.devnull, "w"))
        cls.admin = get_user_model().objects.create_superuser("boss4@x.mv", "boss4@x.mv", "pw")

    def setUp(self):
        import datetime as dt
        from django.utils import timezone
        from .models import InstagramAccount
        self.account = InstagramAccount.objects.create(ig_user_id="17841", username="islandstaymv", access_token="tok",
                                                       token_expires_at=timezone.now() + dt.timedelta(days=50))
        self.post = SocialPost.objects.create(title="Spotlight", headline="Stay on Maafushi", caption="Hello",
                                              publish_at=timezone.now() - dt.timedelta(minutes=5), ig_state="queued",
                                              ig_image_url="https://www.islandstaymv.com/media/blob/social/ig/1.jpg")
        self.calls = []

    def fake(self, answers):
        from unittest import mock
        from . import instagram

        def call(method, url, params=None, data=None, headers=None, timeout=60):
            self.calls.append((method, url, data))
            for key, value in answers:
                if key in url:
                    if isinstance(value, Exception):
                        raise value
                    return value
            raise AssertionError("unexpected call " + url)
        return mock.patch.object(instagram, "_call", side_effect=call)

    def test_feed_post_publishes_when_due(self):
        from . import instagram
        with self.fake([("/media_publish", {"id": "999"}), ("/17841/media", {"id": "c1"}),
                        ("/c1", {"status_code": "FINISHED"}), ("/999", {"permalink": "https://instagram.com/p/x"})]):
            log = instagram.run()
        self.post.refresh_from_db()
        self.assertEqual((self.post.ig_state, self.post.status, self.post.posted_url), ("published", "posted", "https://instagram.com/p/x"))
        self.assertEqual(self.calls[0][2]["image_url"], self.post.ig_image_url)
        self.assertIn("published", log[-1])

    def test_not_due_yet_is_left_alone(self):
        import datetime as dt
        from django.utils import timezone
        from . import instagram
        SocialPost.objects.filter(pk=self.post.pk).update(publish_at=timezone.now() + dt.timedelta(hours=2))
        with self.fake([]):
            self.assertEqual(instagram.run(), ["Nothing due."])

    def test_story_and_reel_containers(self):
        from . import instagram
        from .models import SocialAsset
        self.post.post_type = "story"
        with self.fake([("/17841/media", {"id": "c2"})]):
            instagram.create_containers(self.account, self.post)
        self.assertEqual(self.calls[-1][2]["media_type"], "STORIES")
        self.post.post_type = "reel"
        self.post.save()
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage
        for i, chunk in enumerate([b"abc", b"def"]):
            name = default_storage.save(f"social/assets/t-{i}.part", ContentFile(chunk))
            SocialAsset.objects.create(post=self.post, kind="video", file=name, order=i, size=3)
        with self.fake([("rupload.facebook.com", {"success": True}), ("/17841/media", {"id": "c3"})]):
            instagram.create_containers(self.account, self.post)
        self.assertEqual(self.calls[-2][2]["media_type"], "REELS")
        self.assertEqual(self.calls[-1][2], b"abcdef")

    def test_failure_retries_then_gives_up(self):
        from . import instagram
        err = instagram.InstagramError("Instagram said (400): Only photo or video can be accepted as media type.")
        for _ in range(3):
            with self.fake([("/17841/media", err)]):
                instagram.run()
        self.post.refresh_from_db()
        self.assertEqual(self.post.ig_state, "failed")
        self.assertIn("media type", self.post.ig_error)

    def test_cron_needs_secret_and_queue_view(self):
        from django.test import override_settings
        with override_settings(CRON_SECRET="s3"):
            self.assertEqual(self.client.get("/cron/instagram/").status_code, 403)
            with self.fake([("/media_publish", {"id": "9"}), ("/17841/media", {"id": "c1"}),
                            ("/c1", {"status_code": "FINISHED"}), ("/9", {})]):
                r = self.client.get("/cron/instagram/", {"key": "s3"})
            self.assertEqual(r.status_code, 200)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("admin:social_instagram")).status_code, 200)
        post = SocialPost.objects.create(title="Tip", headline="Ferry days", publish_at=self.post.publish_at)
        from django.core.files.uploadedfile import SimpleUploadedFile
        r = self.client.post(reverse("admin:social_instagram_queue", args=[post.pk]),
                             {"image": SimpleUploadedFile("d.jpg", b"\xff\xd8jpeg", content_type="image/jpeg")})
        self.assertEqual(r.json()["ok"], True)
        post.refresh_from_db()
        self.assertEqual((post.ig_state, post.status), ("queued", "scheduled"))
        self.assertTrue(post.ig_image_url.startswith("http"))
        r = self.client.get(reverse("admin:social_socialpost_design", args=[post.pk]))
        self.assertContains(r, "Update on Instagram")
        reel = SocialPost.objects.create(title="Reel", headline="Surf", post_type="reel", format="story", publish_at=self.post.publish_at)
        r = self.client.post(reverse("admin:social_instagram_queue", args=[reel.pk]), {"image": SimpleUploadedFile("d.jpg", b"x")})
        self.assertIn("Reel video", r.json()["error"])
