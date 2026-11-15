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


# ================================================================== partner programme
# Influencers, group leaders and agents promote a property with a personal tracked link. When a booking
# they brought is confirmed and the guest has stayed, the property pays them a commission directly.
# Island Stay only tracks and records it; money never passes through us.

def _num(d):
    """10.00 -> '10', 12.50 -> '12.5'"""
    return f"{d.normalize():f}"


class Programme(models.Model):
    JOIN_INVITE, JOIN_OPEN = "invite", "open"
    TYPE_PERCENT, TYPE_BOOKING, TYPE_NIGHT = "percent", "booking", "night"
    listing = models.OneToOneField(Listing, on_delete=models.CASCADE, related_name="partner_programme")
    is_active = models.BooleanField("Programme on", default=True)
    joining = models.CharField("Who can join", max_length=6, default=JOIN_OPEN, choices=[
        (JOIN_OPEN, "Anyone can apply, we approve"), (JOIN_INVITE, "Invite only")])
    commission_type = models.CharField(max_length=8, default=TYPE_PERCENT, choices=[
        (TYPE_PERCENT, "% of the booking value"), (TYPE_BOOKING, "Fixed amount per booking"), (TYPE_NIGHT, "Fixed amount per night")])
    rate = models.DecimalField("Commission", max_digits=8, decimal_places=2, default=10)
    currency = models.CharField(max_length=3, default="USD", choices=[("USD", "USD"), ("MVR", "MVR")])
    terms = models.TextField(blank=True, help_text="Shown to partners, e.g. paid within 14 days of check-out by bank transfer")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Partner programme · {self.listing.name}"

    @property
    def offer(self):
        if self.commission_type == self.TYPE_PERCENT:
            return f"{_num(self.rate)}% of each booking"
        per = "booking" if self.commission_type == self.TYPE_BOOKING else "night"
        return f"{self.currency} {_num(self.rate)} per {per}"

    def commission_for(self, value=None, nights=None):
        from decimal import Decimal, ROUND_HALF_UP
        if self.commission_type == self.TYPE_PERCENT:
            amount = (Decimal(value or 0) * self.rate / 100)
        elif self.commission_type == self.TYPE_NIGHT:
            amount = self.rate * (nights or 1)
        else:
            amount = self.rate
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class Partner(models.Model):
    AUDIENCE_CHOICES = [("", "–"), ("1k", "Under 1,000"), ("10k", "1,000 – 10,000"), ("50k", "10,000 – 50,000"),
                        ("100k", "50,000 – 100,000"), ("100k+", "Over 100,000"), ("groups", "I organise group trips")]
    user = models.OneToOneField("auth.User", on_delete=models.CASCADE, related_name="partner")
    name = models.CharField("Name or brand", max_length=80)
    instagram = models.CharField(max_length=80, blank=True, help_text="@handle or link")
    tiktok = models.CharField(max_length=80, blank=True)
    other_link = models.URLField("Website / YouTube / other", blank=True)
    audience = models.CharField("Audience size", max_length=8, blank=True, choices=AUDIENCE_CHOICES)
    country = models.CharField(max_length=60, blank=True)
    phone = models.CharField("Phone / WhatsApp", max_length=30, blank=True)
    payout = models.TextField("How you'd like to be paid", blank=True,
                              help_text="e.g. BML transfer, account name and number. Shared only with properties you work with.")
    is_active = models.BooleanField(default=True, help_text="Turn off to block this partner everywhere")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Membership(models.Model):
    STATUS_CHOICES = [("applied", "Applied"), ("active", "Active"), ("paused", "Paused"), ("declined", "Declined")]
    programme = models.ForeignKey(Programme, on_delete=models.CASCADE, related_name="memberships")
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name="memberships")
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default="applied")
    message = models.TextField(blank=True, help_text="The partner's note when applying")
    link = models.OneToOneField(TrackedLink, on_delete=models.SET_NULL, null=True, blank=True, related_name="membership")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("programme", "partner")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.partner} → {self.programme.listing.name}"


class Commission(models.Model):
    PENDING, APPROVED, PAID, REJECTED = "pending", "approved", "paid", "rejected"
    STATUS_CHOICES = [(PENDING, "Pending: booking confirmed"), (APPROVED, "Approved: owed to partner"),
                      (PAID, "Paid"), (REJECTED, "Rejected")]
    membership = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name="commissions")
    enquiry = models.OneToOneField(Enquiry, on_delete=models.CASCADE, related_name="commission")
    booking_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    nights = models.PositiveSmallIntegerField(null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default=PENDING)
    note = models.CharField("Reason / note", max_length=200, blank=True)
    paid_reference = models.CharField("Payment reference", max_length=80, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField("Partner confirmed receipt", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.currency} {self.amount} · {self.membership}"

    @property
    def guest_short(self):
        """What a partner may see of the guest: first name and initial."""
        parts = (self.enquiry.guest_name or "").split()
        return (parts[0] + (f" {parts[-1][0]}." if len(parts) > 1 else "")) if parts else "Guest"
