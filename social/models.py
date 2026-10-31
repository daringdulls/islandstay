"""Social media plan: posts with a branded design template, caption and schedule."""
from django.db import models
from django.urls import reverse
from django.utils import timezone

from directory.models import ActivityType, Island, Listing


class SocialPost(models.Model):
    PLATFORM_CHOICES = [
        ("instagram", "Instagram"), ("facebook", "Facebook"), ("tiktok", "TikTok"),
        ("x", "X"), ("linkedin", "LinkedIn"),
    ]
    FORMAT_CHOICES = [
        ("square", "Square post 1080 × 1080"),
        ("portrait", "Portrait post 1080 × 1350"),
        ("story", "Story / Reel cover 1080 × 1920"),
        ("landscape", "Link / banner 1200 × 630"),
    ]
    FORMAT_SIZES = {"square": (1080, 1080), "portrait": (1080, 1350), "story": (1080, 1920), "landscape": (1200, 630)}
    TEMPLATE_CHOICES = [
        ("island", "Island spotlight"),
        ("experience", "Experience"),
        ("host", "Host spotlight"),
        ("tip", "Travel tip / rules"),
        ("fact", "Did you know"),
        ("quote", "Guest or host quote"),
        ("announce", "Announcement"),
    ]
    TEMPLATE_HELP = {
        "island": "Photo with the island name, atoll and three quick facts on a solid panel.",
        "experience": "Photo of the activity with an icon, a short line and how many islands offer it.",
        "host": "Introduce a local host: photo, name, island and the verified cowrie when it applies.",
        "tip": "Practical advice as a short numbered list: dress code, transfers, what to pack.",
        "fact": "One big number or fact on Lagoon, for Maldives history and island trivia.",
        "quote": "A guest review or a host's own words, large, with who said it.",
        "announce": "News from Island Stay: new islands, new hosts, features.",
    }
    PILLAR_CHOICES = [
        ("islands", "Islands"), ("hosts", "Local hosts"), ("experiences", "Experiences"),
        ("practical", "Practical tips"), ("culture", "Culture & story"), ("news", "News"),
    ]
    STATUS_IDEA, STATUS_DRAFT, STATUS_READY, STATUS_SCHEDULED, STATUS_POSTED = "idea", "draft", "ready", "scheduled", "posted"
    STATUS_CHOICES = [
        (STATUS_IDEA, "Idea"), (STATUS_DRAFT, "Draft"), (STATUS_READY, "Ready to post"),
        (STATUS_SCHEDULED, "Scheduled"), (STATUS_POSTED, "Posted"),
    ]

    title = models.CharField(max_length=120, help_text="Internal name, e.g. 'Dhangethi spotlight'")
    pillar = models.CharField(max_length=12, choices=PILLAR_CHOICES, default="islands")
    template = models.CharField("Design template", max_length=12, choices=TEMPLATE_CHOICES, default="island")
    format = models.CharField(max_length=10, choices=FORMAT_CHOICES, default="portrait")
    platforms = models.CharField(max_length=80, default="instagram,facebook",
                                 help_text="Comma-separated: instagram, facebook, tiktok, x, linkedin")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    publish_at = models.DateTimeField("Post on", null=True, blank=True)

    island = models.ForeignKey(Island, on_delete=models.SET_NULL, null=True, blank=True, related_name="social_posts")
    listing = models.ForeignKey(Listing, on_delete=models.SET_NULL, null=True, blank=True, related_name="social_posts",
                                help_text="For host spotlights")
    activity = models.ForeignKey(ActivityType, on_delete=models.SET_NULL, null=True, blank=True, related_name="social_posts")

    eyebrow = models.CharField(max_length=60, blank=True, help_text="Small label above the headline, e.g. 'Island spotlight · South Ari'")
    headline = models.CharField(max_length=120, help_text="Short. Sentence case.")
    accent_word = models.CharField(max_length=40, blank=True, help_text="One word from the headline to colour in Lagoon (Shallows on dark)")
    body = models.TextField("Design text", blank=True,
                            help_text="Text on the design. For tips and facts, one point per line (3–4 lines max).")
    attribution = models.CharField(max_length=80, blank=True, help_text="Quotes: who said it. Others: footer line, e.g. 'islandstay.mv/dhangethi'")
    image = models.ImageField(upload_to="social/", blank=True, help_text="Upload a photo, or leave empty to use the island / host / activity photo")
    image_url = models.URLField(max_length=500, blank=True, help_text="Or a photo link")
    photo_credit = models.CharField(max_length=120, blank=True)

    caption = models.TextField(blank=True, help_text="Post caption. At most one emoji.")
    hashtags = models.CharField(max_length=300, blank=True)
    link = models.CharField(max_length=200, blank=True, help_text="Link in bio / link to share")
    notes = models.TextField(blank=True, help_text="Internal notes")
    posted_url = models.URLField(blank=True, help_text="Link to the published post")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["publish_at", "id"]
        verbose_name = "social post"

    def __str__(self):
        return self.title

    def get_design_url(self):
        return reverse("admin:social_socialpost_design", args=[self.pk])

    @property
    def size(self):
        return self.FORMAT_SIZES[self.format]

    @property
    def platform_list(self):
        names = dict(self.PLATFORM_CHOICES)
        return [names.get(p.strip(), p.strip()) for p in self.platforms.split(",") if p.strip()]

    @property
    def body_lines(self):
        return [line.strip() for line in self.body.splitlines() if line.strip()]

    @property
    def photo(self):
        if self.image:
            try:
                return self.image.url
            except Exception:
                return ""
        if self.image_url:
            return self.image_url
        for obj in (self.listing, self.island, self.activity):
            url = getattr(obj, "photo_url", None) or getattr(obj, "image_url", None) if obj else None
            if url:
                return url
        return ""

    @property
    def headline_parts(self):
        """Split the headline around the accent word: (before, accent, after)."""
        word = self.accent_word.strip()
        if word and word in self.headline:
            before, after = self.headline.split(word, 1)
            return before, word, after
        return self.headline, "", ""

    @property
    def full_caption(self):
        parts = [self.caption.strip()]
        if self.link:
            parts.append(self.link)
        if self.hashtags:
            parts.append(self.hashtags.strip())
        return "\n\n".join(p for p in parts if p)

    @property
    def is_overdue(self):
        return self.publish_at and self.publish_at < timezone.now() and self.status not in (self.STATUS_POSTED,)
