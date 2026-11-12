"""Income from partners: sponsored placements on island and guide pages, and affiliate links in a 'Before you go' box.

Every click goes through /go/... so it is counted before the visitor is sent on (see views.go).
"""
from django.db import models
from django.urls import reverse
from django.utils import timezone

from directory.models import Island


class Sponsor(models.Model):
    name = models.CharField(max_length=120)
    is_sample = models.BooleanField("Sample", default=False)
    logo = models.ImageField(upload_to="sponsors/", blank=True, help_text="Square or wide logo, PNG or SVG-like on a light background")
    website = models.URLField(blank=True)
    contact_name = models.CharField(max_length=100, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=40, blank=True)
    notes = models.TextField(blank=True, help_text="Agreement, rates, invoices: internal only")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Placement(models.Model):
    """A sponsored card shown on chosen pages and islands between two dates. Always labelled 'Sponsored'."""
    WHERE_ISLAND, WHERE_GUIDE, WHERE_ISLANDS, WHERE_TRANSPORT = "island", "guide", "islands", "transport"
    WHERE_CHOICES = [
        (WHERE_ISLAND, "Island pages (sidebar)"),
        (WHERE_GUIDE, "Travel guides (sidebar)"),
        (WHERE_ISLANDS, "Islands list (above the list)"),
        (WHERE_TRANSPORT, "Transport page (sidebar)"),
    ]
    sponsor = models.ForeignKey(Sponsor, on_delete=models.CASCADE, related_name="placements")
    where = models.CharField("Shown on", max_length=12, choices=WHERE_CHOICES, default=WHERE_ISLAND)
    islands = models.ManyToManyField(Island, blank=True, related_name="sponsored_placements",
                                     help_text="Island pages only: leave empty to show on every island")
    headline = models.CharField(max_length=80, help_text="e.g. 'Stay connected from the moment you land'")
    text = models.CharField(max_length=160, blank=True, help_text="One short line")
    image = models.ImageField(upload_to="sponsors/", blank=True, help_text="Optional wide photo (1200 × 630)")
    image_url = models.URLField("Or photo link", max_length=500, blank=True)
    link = models.URLField(max_length=500, help_text="Where the button goes (the sponsor's page, with their tracking code if they have one)")
    button = models.CharField(max_length=30, default="Learn more")
    starts = models.DateField(default=timezone.localdate)
    ends = models.DateField(help_text="Last day it shows")
    is_active = models.BooleanField(default=True)
    price = models.DecimalField("Price agreed", max_digits=10, decimal_places=2, null=True, blank=True, help_text="For your records")
    currency = models.CharField(max_length=3, default="USD", choices=[("USD", "USD"), ("MVR", "MVR")])
    is_sample = models.BooleanField("Sample", default=False, help_text="Samples only appear in the admin preview, never on the site")
    views = models.PositiveIntegerField(default=0, editable=False)
    clicks = models.PositiveIntegerField(default=0, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-starts"]
        verbose_name = "sponsored placement"

    def __str__(self):
        return f"{self.sponsor}: {self.headline}"

    @property
    def is_live(self):
        today = timezone.localdate()
        return self.is_active and self.starts <= today <= self.ends

    @property
    def ctr(self):
        return (self.clicks / self.views) if self.views else 0

    @property
    def image_src(self):
        if self.image:
            try:
                return self.image.url
            except Exception:
                pass
        return self.image_url

    @property
    def ctr_label(self):
        return f"{self.ctr:.1%}" if self.views else "–"

    def get_click_url(self):
        return reverse("partners:go_sponsor", args=[self.pk])


class AffiliateOffer(models.Model):
    """A partner product travellers need anyway (insurance, eSIM, flights, transfers, tours). We may earn a commission."""
    CATEGORY_CHOICES = [
        ("insurance", "Travel insurance"), ("esim", "eSIM / mobile data"), ("flights", "Flights"),
        ("transfers", "Airport transfers"), ("tours", "Tours & activities"), ("money", "Money & cards"), ("other", "Other"),
    ]
    ICONS = {"insurance": "shield-check", "esim": "signal", "flights": "plane", "transfers": "sailboat", "tours": "compass",
             "money": "banknote", "other": "sparkles"}
    WHERE_CHOICES = [("all", "Island pages, guides and transport"), ("islands", "Island pages only"),
                     ("guides", "Travel guides only"), ("transport", "Transport page only")]
    name = models.CharField("Partner", max_length=80, help_text="e.g. the insurance or eSIM company")
    slug = models.SlugField(unique=True, help_text="Used in the link: islandstaymv.com/go/<slug>/")
    category = models.CharField(max_length=12, choices=CATEGORY_CHOICES)
    title = models.CharField(max_length=70, help_text="e.g. 'Travel insurance that covers diving'")
    blurb = models.CharField(max_length=140, blank=True)
    url = models.URLField("Affiliate link", max_length=600, help_text="The link from the affiliate programme, with your partner ID")
    button = models.CharField(max_length=30, default="See prices")
    where = models.CharField("Shown on", max_length=10, choices=WHERE_CHOICES, default="all")
    is_active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)
    network = models.CharField("Programme / network", max_length=80, blank=True, help_text="Where to see earnings, e.g. the partner dashboard")
    commission = models.CharField("Commission", max_length=80, blank=True, help_text="For your records, e.g. '10% of each policy'")
    is_sample = models.BooleanField("Sample", default=False, help_text="Samples only appear in the admin preview, never on the site")
    clicks = models.PositiveIntegerField(default=0, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "category", "name"]
        verbose_name = "affiliate link"

    def __str__(self):
        return f"{self.name}: {self.title}"

    @property
    def icon(self):
        return self.ICONS.get(self.category, "sparkles")

    def get_click_url(self):
        return reverse("partners:go_affiliate", args=[self.slug])


class Click(models.Model):
    """One click on a sponsored card or affiliate link (for date reports). No personal data."""
    placement = models.ForeignKey(Placement, on_delete=models.CASCADE, null=True, blank=True, related_name="click_log")
    offer = models.ForeignKey(AffiliateOffer, on_delete=models.CASCADE, null=True, blank=True, related_name="click_log")
    page = models.CharField(max_length=300, blank=True)
    island = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]


class AdEnquiry(models.Model):
    """'Advertise with us' form."""
    STATUS_CHOICES = [("new", "New"), ("talking", "In discussion"), ("won", "Became a sponsor"), ("lost", "Not going ahead")]
    name = models.CharField("Your name", max_length=100)
    company = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField("Phone / WhatsApp", max_length=40, blank=True)
    interest = models.CharField("Interested in", max_length=20, blank=True, choices=[
        ("island", "Sponsoring island pages"), ("guide", "Sponsoring travel guides"), ("affiliate", "Affiliate partnership"), ("other", "Something else")])
    message = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="new")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "advertising enquiry"
        verbose_name_plural = "advertising enquiries"

    def __str__(self):
        return f"{self.company} ({self.name})"
