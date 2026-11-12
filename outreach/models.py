"""Getting businesses to list: a lead tracker, ready-made messages (sent from the Island Stay accounts) and a plan."""
import datetime as dt

from django.db import models
from django.utils import timezone

from directory.models import Island, Listing


class OutreachMessage(models.Model):
    """A message template, written as Island Stay ('we'), never as a person."""
    STATUS_AFTER = [("", "Don't change"), ("messaged", "Messaged"), ("followup1", "Follow-up 1 sent"),
                    ("followup2", "Follow-up 2 sent"), ("listed", "Listed")]
    use = models.CharField(max_length=60, help_text="e.g. 'First DM'")
    when = models.CharField(max_length=80, blank=True, help_text="e.g. '3 days after the first DM'")
    text = models.TextField("Message", help_text="Placeholders: <name> (contact's first name, or '<business> team'), <business>, <island>, "
                                                 "<X> (travellers who viewed the island in the last 30 days; the sentence is left out below 20), "
                                                 "<link> (their page). Anything else in <brackets> you fill in yourself.")
    text_dv = models.TextField("Dhivehi version", blank=True, help_text="Written by a native speaker")
    sets_status = models.CharField("After sending, mark the lead as", max_length=12, choices=STATUS_AFTER, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "message template"

    def __str__(self):
        return self.use


class HostLead(models.Model):
    KIND_CHOICES = [("guesthouse", "Guest house"), ("hotel", "Hotel"), ("dive", "Dive centre"), ("excursion", "Excursion / boat"),
                    ("transfer", "Transfer"), ("food", "Café / restaurant"), ("shop", "Shop"), ("other", "Other")]
    CHANNEL_CHOICES = [("instagram", "Instagram"), ("facebook", "Facebook"), ("tiktok", "TikTok"), ("whatsapp", "WhatsApp"), ("referral", "Referral")]
    STATUS_CHOICES = [
        ("to_contact", "To contact"), ("engaged", "Engaged (liked / commented)"), ("messaged", "Messaged"),
        ("followup1", "Follow-up 1 sent"), ("followup2", "Follow-up 2 sent"), ("replied", "Replied"), ("interested", "Interested"),
        ("listed", "Listed"), ("verified", "Verified"), ("no_reply", "No reply"), ("not_interested", "Not interested"),
    ]
    CONTACTED = ("messaged", "followup1", "followup2", "replied", "interested", "listed", "verified", "no_reply", "not_interested")
    REPLIED = ("replied", "interested", "listed", "verified", "not_interested")
    LISTED = ("listed", "verified")
    FOLLOW_UP_DAYS = {"messaged": 3, "followup1": 7, "followup2": 7}

    business = models.CharField(max_length=120)
    kind = models.CharField("Type", max_length=12, choices=KIND_CHOICES, default="guesthouse")
    island = models.ForeignKey(Island, on_delete=models.SET_NULL, null=True, blank=True, related_name="host_leads")
    contact_name = models.CharField(max_length=80, blank=True)
    instagram = models.CharField(max_length=80, blank=True, help_text="Handle, e.g. @coralview.maafushi")
    facebook = models.URLField(max_length=300, blank=True, help_text="Page link")
    tiktok = models.CharField(max_length=80, blank=True, help_text="Handle")
    whatsapp = models.CharField("WhatsApp / phone", max_length=30, blank=True, help_text="With country code, e.g. +960 7xx xxxx")
    found_via = models.CharField(max_length=80, blank=True, help_text="e.g. #maafushi hashtag, location tag, Facebook group")
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default="instagram")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="to_contact", db_index=True)
    first_contact = models.DateField(null=True, blank=True)
    last_contact = models.DateField(null=True, blank=True)
    next_follow_up = models.DateField(null=True, blank=True, editable=False, db_index=True)
    date_listed = models.DateField(null=True, blank=True)
    listing = models.ForeignKey(Listing, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
                                help_text="Their Island Stay page, once listed")
    referred_by = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["next_follow_up", "-updated_at"]
        verbose_name = "lead"

    def __str__(self):
        return self.business

    def save(self, *args, **kwargs):
        days = self.FOLLOW_UP_DAYS.get(self.status)
        self.next_follow_up = (self.last_contact + dt.timedelta(days=days)) if (days and self.last_contact) else None
        if self.status in self.LISTED and not self.date_listed:
            self.date_listed = timezone.localdate()
        super().save(*args, **kwargs)

    def mark(self, status, when=None):
        """Record a message sent / a new status today."""
        when = when or timezone.localdate()
        if status in ("messaged", "followup1", "followup2"):
            self.first_contact = self.first_contact or when
            self.last_contact = when
        self.status = status
        self.save()

    @property
    def instagram_url(self):
        h = self.instagram.strip().lstrip("@")
        return f"https://instagram.com/{h}" if h else ""

    @property
    def tiktok_url(self):
        h = self.tiktok.strip().lstrip("@")
        return f"https://www.tiktok.com/@{h}" if h else ""

    @property
    def whatsapp_number(self):
        return "".join(ch for ch in self.whatsapp if ch.isdigit())


class LeadMessage(models.Model):
    """A message rewritten for one lead. The template stays as it is for everyone else."""
    lead = models.ForeignKey(HostLead, on_delete=models.CASCADE, related_name="custom_messages")
    message = models.ForeignKey(OutreachMessage, on_delete=models.CASCADE, related_name="+")
    text = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("lead", "message")]
        verbose_name = "customised message"


class OutreachPlan(models.Model):
    """One row: when the plan started and the weekly targets (cumulative)."""
    start_date = models.DateField(default=dt.date(2026, 11, 16))
    listed_targets = models.CharField(max_length=200, default="0,0,5,12,19,25,33,41,50,60,75,100",
                                      help_text="Businesses listed by the end of each week (cumulative)")
    message_targets = models.CharField(max_length=200, default="0,0,75,150,225,300,375,450,525,600,675,750",
                                       help_text="Businesses messaged by the end of each week (cumulative)")

    class Meta:
        verbose_name = "outreach plan"

    @classmethod
    def get(cls):
        return cls.objects.first() or cls.objects.create()

    def targets(self, field):
        out = []
        for x in getattr(self, field).split(","):
            try:
                out.append(int(x.strip()))
            except ValueError:
                out.append(0)
        return out
