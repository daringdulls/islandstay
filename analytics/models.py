"""First-party visitor analytics. Full tracking only for visitors who accept analytics cookies."""
import uuid

from django.db import models


class Visitor(models.Model):
    """One browser, identified by the first-party is_vid cookie (set only after consent)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_seen = models.DateTimeField(db_index=True)
    last_seen = models.DateTimeField(db_index=True)
    country = models.CharField(max_length=2, blank=True, db_index=True)
    region = models.CharField(max_length=60, blank=True)
    city = models.CharField(max_length=80, blank=True)
    device = models.CharField(max_length=10, blank=True)
    browser = models.CharField(max_length=30, blank=True)
    os = models.CharField(max_length=20, blank=True)
    language = models.CharField(max_length=20, blank=True)
    screen = models.CharField(max_length=15, blank=True)
    first_source = models.CharField("Source", max_length=60, blank=True, db_index=True)
    first_referrer = models.CharField(max_length=300, blank=True)
    first_campaign = models.CharField("Campaign", max_length=100, blank=True)
    landing_path = models.CharField(max_length=300, blank=True)
    visits = models.PositiveIntegerField(default=0)
    pageviews = models.PositiveIntegerField(default=0)
    enquiries = models.PositiveIntegerField("Booking requests", default=0)

    class Meta:
        ordering = ["-last_seen"]

    def __str__(self):
        return f"Visitor {str(self.id)[:8]}"

    @property
    def short_id(self):
        return str(self.id)[:8]


class Visit(models.Model):
    """One browsing session: ends after 30 minutes without activity."""
    id = models.UUIDField(primary_key=True, editable=False)
    visitor = models.ForeignKey(Visitor, on_delete=models.CASCADE, related_name="visit_set")
    started_at = models.DateTimeField(db_index=True)
    last_at = models.DateTimeField()
    entry_path = models.CharField(max_length=300, blank=True)
    exit_path = models.CharField(max_length=300, blank=True)
    referrer = models.CharField(max_length=300, blank=True)
    source = models.CharField(max_length=60, blank=True, db_index=True)
    medium = models.CharField(max_length=60, blank=True)
    campaign = models.CharField(max_length=100, blank=True)
    pageviews = models.PositiveIntegerField(default=0)
    events = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-started_at"]

    @property
    def seconds(self):
        return int((self.last_at - self.started_at).total_seconds())


class Event(models.Model):
    TYPES = [
        ("pageview", "Page view"), ("click", "Click"), ("outbound", "Outbound link"), ("search", "Search"),
        ("filter", "Filter"), ("scroll", "Scroll depth"), ("leave", "Left page"), ("request_start", "Started request form"),
        ("request_submit", "Pressed Send request"), ("request_error", "Request form error"), ("request_saved", "Request saved"),
        ("send_to_host", "Sent request to host"), ("copy", "Copied"), ("gallery", "Opened photo"),
    ]
    visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name="event_set")
    visitor = models.ForeignKey(Visitor, on_delete=models.CASCADE, related_name="event_set")
    ts = models.DateTimeField(db_index=True)
    type = models.CharField(max_length=20, choices=TYPES, db_index=True)
    path = models.CharField(max_length=300, db_index=True)
    label = models.CharField(max_length=200, blank=True)
    value = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["ts", "id"]
        indexes = [models.Index(fields=["type", "ts"])]


class AnonymousPageview(models.Model):
    """Page counts from visitors who declined analytics cookies: no identifiers, just a daily tally."""
    date = models.DateField()
    path = models.CharField(max_length=300)
    views = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("date", "path")]
