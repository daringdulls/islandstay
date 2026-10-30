from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


def card_size(url):
    """Smaller Wikimedia thumbnail for cards (the stored URL is the 1920px version)."""
    return url.replace("/1920px-", "/960px-") if url else url


def unique_slug(instance, value, field="slug"):
    base = slugify(value)[:60] or "item"
    slug, n = base, 2
    Model = type(instance)
    while Model.objects.filter(**{field: slug}).exclude(pk=instance.pk).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


class Atoll(models.Model):
    name = models.CharField(max_length=80, help_text="Common name, e.g. South Malé Atoll")
    official_name = models.CharField(max_length=80, blank=True, help_text="Administrative name, e.g. Kaafu")
    code = models.CharField(max_length=10, blank=True, help_text="Administrative code letter, e.g. K")
    slug = models.SlugField(unique=True, blank=True)
    region = models.CharField(
        max_length=10,
        choices=[("north", "North"), ("central", "Central"), ("south", "South")],
        default="central",
    )
    description = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(default=0, help_text="North-to-south ordering")
    map_lat = models.FloatField("Map centre latitude", null=True, blank=True)
    map_lng = models.FloatField("Map centre longitude", null=True, blank=True)
    map_rlat = models.FloatField("Map half-height (degrees)", null=True, blank=True, help_text="Size of the clickable atoll outline")
    map_rlng = models.FloatField("Map half-width (degrees)", null=True, blank=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.name} ({self.official_name})" if self.official_name else self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("directory:atoll_detail", args=[self.slug])


class ActivityType(models.Model):
    """A kind of experience: snorkeling, sandbank trip, whale shark excursion, etc."""

    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    icon = models.CharField(max_length=30, blank=True, default="waves", help_text="Icon name from the site icon set, e.g. fish, sailboat, anchor")
    description = models.CharField(max_length=240, blank=True)
    photo_search = models.CharField(
        max_length=120, blank=True, help_text="Wikimedia Commons search used to find a photo, e.g. whale shark Maldives"
    )
    image_url = models.URLField(max_length=500, blank=True)
    image_credit = models.CharField(max_length=200, blank=True)
    image_license = models.CharField(max_length=60, blank=True)
    image_source_url = models.URLField(max_length=500, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*args, **kwargs)

    @property
    def thumb_url(self):
        return card_size(self.image_url)


class Amenity(models.Model):
    name = models.CharField(max_length=60, unique=True)
    icon = models.CharField(max_length=30, blank=True, default="check", help_text="Icon name from the site icon set")

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "amenities"

    def __str__(self):
        return self.name


class Island(models.Model):
    TYPE_LOCAL = "local"
    TYPE_RESORT = "resort"
    TYPE_CAPITAL = "capital"
    TYPE_CHOICES = [
        (TYPE_LOCAL, "Local inhabited island"),
        (TYPE_RESORT, "Private resort island"),
        (TYPE_CAPITAL, "Capital / urban island"),
    ]
    TRANSFER_CHOICES = [
        ("speedboat", "Speedboat"),
        ("ferry", "Public ferry"),
        ("seaplane", "Seaplane"),
        ("domestic_flight", "Domestic flight"),
        ("road", "Road / causeway"),
    ]

    atoll = models.ForeignKey(Atoll, on_delete=models.PROTECT, related_name="islands")
    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True, blank=True)
    island_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_LOCAL)
    tagline = models.CharField(max_length=140, blank=True, help_text="One-line hook shown on cards")
    overview = models.TextField(blank=True, help_text="General introduction to the island")
    famous_for = models.TextField(blank=True, help_text="What the island is known for. One item per line.")
    what_to_expect = models.TextField(
        blank=True, help_text="Practical expectations: dress code, bikini beach, alcohol, pace of life. One per line."
    )
    getting_there = models.TextField(blank=True, help_text="How to reach the island from Velana Airport / Malé")
    best_time_to_visit = models.CharField(max_length=140, blank=True)
    activities = models.ManyToManyField(
        ActivityType, blank=True, related_name="islands", help_text="Activities possible on / around this island"
    )
    transfer_types = models.CharField(
        max_length=120, blank=True, help_text="Comma separated: speedboat, ferry, seaplane, domestic_flight, road"
    )
    distance_from_airport_km = models.PositiveIntegerField(null=True, blank=True)
    transfer_time = models.CharField(max_length=60, blank=True, help_text="e.g. 45 min by speedboat")
    population = models.PositiveIntegerField(null=True, blank=True)
    has_bikini_beach = models.BooleanField(default=False)
    has_atm = models.BooleanField(default=False)
    has_hospital = models.BooleanField("Clinic / health centre", default=False, help_text="Health centre, clinic or hospital on the island")
    has_pharmacy = models.BooleanField(default=False)
    has_police = models.BooleanField("Police station", default=False)
    has_supermarket = models.BooleanField("Shops / supermarket", default=False)
    has_4g = models.BooleanField("4G mobile data", default=True)
    nearest_airport = models.CharField(max_length=80, blank=True, help_text="Nearest airport, e.g. Velana International (MLE) or Maamigili (VAM)")
    nearest_airport_km = models.PositiveIntegerField(null=True, blank=True)
    facilities_notes = models.TextField(blank=True, help_text="Other facilities: mosques, sports ground, water sports centre… One per line.")
    local_rules = models.TextField("Local regulations", blank=True, help_text="Rules visitors must follow (dress code, alcohol, drones…). One per line.")
    accessibility = models.TextField(blank=True, help_text="Accessibility for visitors with reduced mobility, families with prams, etc. One per line.")
    area_km2 = models.DecimalField("Area (km²)", max_digits=7, decimal_places=3, null=True, blank=True)
    population_year = models.PositiveSmallIntegerField(default=2022, help_text="Census year of the population figure")
    sources = models.TextField(blank=True, help_text="Where the facts come from. One URL per line; shown on the island page.")
    wikipedia_title = models.CharField(
        max_length=120, blank=True,
        help_text="English Wikipedia article title, e.g. Maafushi_(Kaafu_Atoll). Used by the fetch_island_photos command.",
    )
    cover_image = models.ImageField(upload_to="islands/", blank=True, help_text="Upload a photo, or leave empty and use the link below")
    cover_image_url = models.URLField(
        max_length=500, blank=True, help_text="Photo link, e.g. from Wikimedia Commons. Used when no photo is uploaded."
    )
    cover_credit = models.CharField(max_length=200, blank=True, help_text="Photographer / author of the cover photo")
    cover_license = models.CharField(max_length=60, blank=True, help_text="e.g. CC BY-SA 4.0")
    cover_source_url = models.URLField(blank=True, help_text="Where the photo comes from (e.g. its Wikimedia Commons page)")
    cover_color = models.CharField(
        max_length=7, default="#0e7c86", help_text="Fallback colour when there is no cover photo"
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_published = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        unique_together = [("atoll", "name")]

    def __str__(self):
        return f"{self.name}, {self.atoll.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("directory:island_detail", args=[self.slug])

    @property
    def famous_for_list(self):
        return [line.strip("-• ").strip() for line in self.famous_for.splitlines() if line.strip()]

    @property
    def what_to_expect_list(self):
        return [line.strip("-• ").strip() for line in self.what_to_expect.splitlines() if line.strip()]

    @property
    def sources_list(self):
        return [line.strip() for line in self.sources.splitlines() if line.strip().startswith("http")]

    @property
    def chart_style(self):
        """Deterministic position for the drawn chart cover used when there is no photo."""
        seed = sum(ord(c) * (i + 1) for i, c in enumerate(self.slug or self.name))
        return f"--x:{30 + seed % 45}%;--y:{38 + (seed // 7) % 30}%;--rot:{seed % 360}deg"

    @property
    def photo_url(self):
        """Large cover photo: an uploaded file wins over a linked Wikimedia photo."""
        if self.cover_image:
            return self.cover_image.url
        return self.cover_image_url

    @property
    def card_photo_url(self):
        return self.cover_image.url if self.cover_image else card_size(self.cover_image_url)

    @property
    def local_rules_list(self):
        return [line.strip("-• ").strip() for line in self.local_rules.splitlines() if line.strip()]

    @property
    def accessibility_list(self):
        return [line.strip("-• ").strip() for line in self.accessibility.splitlines() if line.strip()]

    @property
    def facilities_list(self):
        return [line.strip("-• ").strip() for line in self.facilities_notes.splitlines() if line.strip()]

    @property
    def facility_flags(self):
        return [
            ("banknote", "ATM", self.has_atm), ("cross", "Clinic / health centre", self.has_hospital),
            ("pill", "Pharmacy", self.has_pharmacy), ("siren", "Police station", self.has_police),
            ("store", "Shops", self.has_supermarket), ("signal", "4G mobile data", self.has_4g),
            ("umbrella", "Bikini beach", self.has_bikini_beach),
        ]

    @property
    def transfer_labels(self):
        labels = dict(self.TRANSFER_CHOICES)
        return [labels.get(t.strip(), t.strip()) for t in self.transfer_types.split(",") if t.strip()]

    def approved_listings(self):
        return self.listings.filter(status=Listing.STATUS_APPROVED)


class Listing(models.Model):
    """Anything a local business can list: a place to stay or a service/experience."""

    KIND_GUESTHOUSE = "guesthouse"
    KIND_HOTEL = "hotel"
    KIND_RESORT = "resort"
    KIND_VILLA = "villa"
    KIND_ACTIVITY = "activity"
    KIND_DIVE = "dive"
    KIND_TRANSFER = "transfer"
    KIND_RESTAURANT = "restaurant"
    KIND_OTHER = "other"
    STAY_KINDS = [KIND_GUESTHOUSE, KIND_HOTEL, KIND_RESORT, KIND_VILLA]
    EXPERIENCE_KINDS = [KIND_ACTIVITY, KIND_DIVE, KIND_OTHER]
    TRANSPORT_KINDS = [KIND_TRANSFER]
    FOOD_KINDS = [KIND_RESTAURANT]
    SERVICE_KINDS = EXPERIENCE_KINDS + TRANSPORT_KINDS + FOOD_KINDS
    KIND_CHOICES = [
        ("Places to stay", [
            (KIND_GUESTHOUSE, "Guest house"),
            (KIND_HOTEL, "City / island hotel"),
            (KIND_RESORT, "Resort"),
            (KIND_VILLA, "Private villa / home stay"),
        ]),
        ("Experiences", [
            (KIND_ACTIVITY, "Excursion / activity operator"),
            (KIND_DIVE, "Dive centre"),
            (KIND_OTHER, "Other service (spa, photography…)"),
        ]),
        ("Transport", [
            (KIND_TRANSFER, "Speedboat / transfer service"),
        ]),
        ("Food", [
            (KIND_RESTAURANT, "Restaurant / café"),
        ]),
    ]

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_SUSPENDED = "suspended"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending review"),
        (STATUS_APPROVED, "Approved (live)"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_SUSPENDED, "Suspended"),
    ]

    PRICE_UNIT_CHOICES = [
        ("night", "per night"),
        ("person", "per person"),
        ("trip", "per trip"),
        ("hour", "per hour"),
        ("dive", "per dive"),
    ]

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="listings")
    island = models.ForeignKey(Island, on_delete=models.PROTECT, related_name="listings")
    kind = models.CharField(max_length=12, choices=KIND_CHOICES)
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True, blank=True)
    short_description = models.CharField(max_length=200)
    description = models.TextField()
    activity_types = models.ManyToManyField(
        ActivityType, blank=True, related_name="listings", help_text="For operators: which experiences you offer"
    )
    amenities = models.ManyToManyField(Amenity, blank=True, related_name="listings")

    # Stay details (optional for services)
    room_count = models.PositiveSmallIntegerField(null=True, blank=True)
    max_guests = models.PositiveSmallIntegerField(null=True, blank=True)
    star_rating = models.PositiveSmallIntegerField(null=True, blank=True, help_text="1–5, if officially rated")
    distance_to_beach_m = models.PositiveIntegerField(null=True, blank=True)
    check_in_time = models.CharField(max_length=20, blank=True)
    check_out_time = models.CharField(max_length=20, blank=True)
    house_rules = models.TextField(blank=True)

    # Indicative pricing only — no availability or payment is handled here.
    price_from = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, choices=[("USD", "USD"), ("MVR", "MVR")], default="USD")
    price_unit = models.CharField(max_length=10, choices=PRICE_UNIT_CHOICES, default="night")

    # Direct contact details — enquiries are delivered here.
    contact_name = models.CharField(max_length=80)
    contact_email = models.EmailField(help_text="Booking requests are emailed here")
    contact_phone = models.CharField(max_length=30, blank=True)
    whatsapp = models.CharField(max_length=30, blank=True, help_text="International format, e.g. +9607771234")
    viber = models.CharField(max_length=30, blank=True)
    website = models.URLField(blank=True)
    facebook = models.URLField(blank=True)
    instagram = models.URLField(blank=True)
    address = models.CharField(max_length=160, blank=True)
    registration_number = models.CharField(
        max_length=60, blank=True, help_text="Ministry of Tourism / business registration no. (shown to admins only)"
    )

    # Food
    cuisine = models.CharField(max_length=120, blank=True, help_text="Restaurants: e.g. Maldivian, seafood, Italian")
    opening_hours = models.CharField(max_length=120, blank=True, help_text="e.g. Daily 7:00–23:00, closed Friday until 14:00")
    serves_breakfast = models.BooleanField(default=False)
    delivery = models.BooleanField("Delivers to guest houses", default=False)

    cover_image = models.ImageField(upload_to="listings/", blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    admin_note = models.TextField(blank=True, help_text="Feedback to the owner (e.g. reason for rejection)")
    is_featured = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False, help_text="Licence checked by the Island Stay team")
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_document = models.FileField(
        upload_to="verification/", blank=True,
        help_text="Tourism licence / business registration certificate (PDF or photo). Only visible to admins.",
    )
    verification_requested_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_featured", "name"]

    def __str__(self):
        return f"{self.name} ({self.island.name})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, f"{self.name} {self.island.name}")
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("directory:listing_detail", args=[self.slug])

    @property
    def is_stay(self):
        return self.kind in self.STAY_KINDS

    @property
    def photo_url(self):
        """The business's own photo, or the island's photo so every card has an image."""
        return self.cover_image.url if self.cover_image else self.island.card_photo_url

    @property
    def has_own_photo(self):
        return bool(self.cover_image)

    @property
    def is_food(self):
        return self.kind in self.FOOD_KINDS

    @property
    def is_transport(self):
        return self.kind in self.TRANSPORT_KINDS

    @property
    def section(self):
        if self.is_stay:
            return "stays"
        if self.is_food:
            return "food"
        if self.is_transport:
            return "transport"
        return "experiences"

    @property
    def verification_pending(self):
        return bool(self.verification_requested_at) and not self.is_verified

    @property
    def is_live(self):
        return self.status == self.STATUS_APPROVED

    @property
    def whatsapp_digits(self):
        return "".join(c for c in self.whatsapp if c.isdigit())

    @property
    def kind_icon(self):
        return {
            "guesthouse": "house", "hotel": "hotel", "resort": "tree-palm", "villa": "bed-double", "activity": "sailboat",
            "dive": "anchor", "transfer": "ship", "restaurant": "utensils", "other": "sparkles",
        }.get(self.kind, "sparkles")


class TransportRoute(models.Model):
    """How to reach an island: public ferry, scheduled speedboat, domestic flight or seaplane.

    Routes are either general information maintained by admins (public ferries, flights) or offered by
    a transfer operator's listing, in which case travellers can send that operator a request.
    """

    MODE_CHOICES = [
        ("ferry", "Public ferry"),
        ("speedboat", "Shared speedboat"),
        ("private", "Private speedboat"),
        ("flight", "Domestic flight"),
        ("seaplane", "Seaplane"),
    ]
    MODE_ICONS = {"ferry": "ship", "speedboat": "sailboat", "private": "ship-wheel", "flight": "plane", "seaplane": "plane-landing"}

    island = models.ForeignKey(Island, on_delete=models.CASCADE, related_name="routes", help_text="Destination island")
    mode = models.CharField(max_length=10, choices=MODE_CHOICES)
    origin = models.CharField(max_length=80, default="Velana International Airport (MLE)")
    via = models.CharField(max_length=80, blank=True, help_text="e.g. 'Maamigili airport, then 20 min speedboat'")
    operator = models.ForeignKey(
        Listing, on_delete=models.CASCADE, null=True, blank=True, related_name="routes",
        limit_choices_to={"kind__in": Listing.TRANSPORT_KINDS}, help_text="Transfer operator listing (optional)",
    )
    operator_name = models.CharField(max_length=80, blank=True, help_text="If not a listing, e.g. 'MTCC / RTL public ferry'")
    duration = models.CharField(max_length=40, help_text="e.g. 1 hr 30 min")
    schedule = models.CharField(max_length=160, blank=True, help_text="e.g. Daily 10:00 & 16:00 from the airport; no Friday service")
    price_from = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, choices=[("USD", "USD"), ("MVR", "MVR")], default="USD")
    price_note = models.CharField(max_length=60, blank=True, help_text="e.g. per person one way")
    notes = models.CharField(max_length=240, blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "mode"]

    def __str__(self):
        return f"{self.get_mode_display()} {self.origin} → {self.island.name}"

    @property
    def mode_icon(self):
        return self.MODE_ICONS.get(self.mode, "ship")

    @property
    def mode_label(self):
        return self.get_mode_display()

    @property
    def provider(self):
        return self.operator.name if self.operator_id else self.operator_name


class IslandPhoto(models.Model):
    """Gallery photo for an island, usually linked from Wikimedia Commons with its credit and licence."""

    island = models.ForeignKey(Island, on_delete=models.CASCADE, related_name="photos")
    image_url = models.URLField(max_length=500)
    caption = models.CharField(max_length=200, blank=True)
    credit = models.CharField(max_length=200, blank=True)
    license = models.CharField(max_length=60, blank=True)
    source_url = models.URLField(max_length=500, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    is_visible = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]
        unique_together = [("island", "image_url")]

    def __str__(self):
        return self.caption or self.image_url.rsplit("/", 1)[-1]

    @property
    def thumb_url(self):
        return card_size(self.image_url)


class ListingPhoto(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="listings/gallery/")
    caption = models.CharField(max_length=120, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]


class RoomType(models.Model):
    """Optional room / package details for stays and services. Informational only."""

    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="rooms")
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=240, blank=True)
    max_guests = models.PositiveSmallIntegerField(null=True, blank=True)
    price_from = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return self.name


class Enquiry(models.Model):
    """A booking / service request sent from a guest directly to the listing owner."""

    STATUS_NEW = "new"
    STATUS_CHOICES = [
        (STATUS_NEW, "New"),
        ("replied", "Replied"),
        ("confirmed", "Confirmed by owner"),
        ("declined", "Declined / unavailable"),
        ("closed", "Closed"),
    ]
    CONTACT_CHOICES = [("email", "Email"), ("whatsapp", "WhatsApp"), ("phone", "Phone call"), ("viber", "Viber")]

    reference = models.CharField(max_length=12, unique=True, editable=False)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="enquiries")
    guest_name = models.CharField(max_length=100)
    guest_email = models.EmailField()
    guest_phone = models.CharField(max_length=30, blank=True)
    guest_country = models.CharField(max_length=60, blank=True)
    preferred_contact = models.CharField(max_length=10, choices=CONTACT_CHOICES, default="email")
    check_in = models.DateField(null=True, blank=True, help_text="Arrival / service date")
    check_out = models.DateField(null=True, blank=True)
    adults = models.PositiveSmallIntegerField(default=2)
    children = models.PositiveSmallIntegerField(default=0)
    rooms = models.PositiveSmallIntegerField(null=True, blank=True)
    room_type = models.CharField(max_length=80, blank=True)
    needs_transfer = models.BooleanField(default=False, help_text="Guest would like help arranging a transfer")
    message = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_NEW)
    owner_notes = models.TextField(blank=True, help_text="Private notes for the owner")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "booking request"
        verbose_name_plural = "booking requests"

    def __str__(self):
        return f"{self.reference} — {self.guest_name} → {self.listing.name}"

    def save(self, *args, **kwargs):
        if not self.reference:
            import secrets

            alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
            while True:
                ref = "IS-" + "".join(secrets.choice(alphabet) for _ in range(6))
                if not Enquiry.objects.filter(reference=ref).exists():
                    break
            self.reference = ref
        super().save(*args, **kwargs)

    @property
    def nights(self):
        if self.check_in and self.check_out and self.check_out > self.check_in:
            return (self.check_out - self.check_in).days
        return None


class IslandSuggestion(models.Model):
    """Business owners can ask for an island that isn't listed yet to be added."""

    island_name = models.CharField(max_length=80)
    atoll = models.ForeignKey(Atoll, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    contact_email = models.EmailField(blank=True)
    handled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["handled", "-created_at"]

    def __str__(self):
        return f"{self.island_name} ({self.atoll or 'atoll unknown'})"
