"""Tracked links: a paid add-on for properties.

A property with a live LinkPlan creates short links (islandstaymv.com/r/<code>/) for each place it
promotes itself: Instagram bio, WhatsApp status, Booking.com profile, flyers (QR code) and so on.
Every visit is counted, and booking requests made within 14 days of a visit are credited to the link.
"""
from django.db import models
from django.utils import timezone

from directory.models import Enquiry, Listing


class LinkPlan(models.Model):
    """The paid subscription. You invoice the property, then switch it on here."""
    listing = models.OneToOneField(Listing, on_delete=models.CASCADE, related_name="link_plan")
    is_active = models.BooleanField("On", default=True, help_text="Turn off to pause the add-on (links keep working but stop counting)")
    starts = models.DateField(default=timezone.localdate)
    ends = models.DateField(null=True, blank=True, help_text="Last day it's paid for. Leave empty for no end date.")
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="For your records")
    currency = models.CharField(max_length=3, default="USD", choices=[("USD", "USD"), ("MVR", "MVR")])
    billing = models.CharField(max_length=10, default="monthly", choices=[("monthly", "Monthly"), ("yearly", "Yearly"), ("once", "One-off")])
    notes = models.TextField(blank=True, help_text="Invoice numbers, agreement: internal only")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "tracked links plan"
        verbose_name_plural = "tracked links plans"

    def __str__(self):
        return f"Tracked links · {self.listing.name}"

    @property
    def is_live(self):
        today = timezone.localdate()
        return self.is_active and self.starts <= today and (self.ends is None or self.ends >= today)


def plan_is_live(listing):
    try:
        plan = listing.link_plan
    except LinkPlan.DoesNotExist:
        return False
    return plan.is_live


class TrackedLink(models.Model):
    CHANNEL_CHOICES = [
        ("instagram", "Instagram"), ("facebook", "Facebook"), ("tiktok", "TikTok"), ("whatsapp", "WhatsApp"),
        ("booking", "Booking.com / Agoda profile"), ("google", "Google Business profile"), ("website", "Our own website"),
        ("email", "Email signature"), ("print", "Flyer / card (QR code)"), ("partner", "Partner or agent"), ("other", "Other"),
    ]
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="tracked_links")
    code = models.SlugField(max_length=40, unique=True, help_text="The short part of the link: islandstaymv.com/r/<code>/")
    label = models.CharField(max_length=60, help_text="e.g. 'Instagram bio' or 'Airport flyer'")
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default="instagram")
    to_form = models.BooleanField("Open the request form", default=False,
                                  help_text="Take visitors straight to the booking request form instead of the top of the page")
    is_active = models.BooleanField(default=True)
    clicks = models.PositiveIntegerField(default=0, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"/r/{self.code}/ · {self.label}"

    def get_absolute_url(self):
        return f"/r/{self.code}/"


class LinkVisit(models.Model):
    link = models.ForeignKey(TrackedLink, on_delete=models.CASCADE, related_name="visits")
    device = models.CharField(max_length=10, blank=True)
    referrer = models.CharField(max_length=80, blank=True, help_text="Website the visitor came from, when the browser says")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]


class LinkLead(models.Model):
    """A booking request made within 14 days of visiting through a tracked link."""
    link = models.ForeignKey(TrackedLink, on_delete=models.CASCADE, related_name="leads")
    enquiry = models.OneToOneField(Enquiry, on_delete=models.CASCADE, related_name="tracked_lead")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
