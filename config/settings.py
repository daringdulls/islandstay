"""Django settings for the Maldives local OTA (IslandStay)."""
import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me")
# Production by default on Vercel and Render; development mode locally.
_HOSTED = os.environ.get("VERCEL") == "1" or bool(os.environ.get("RENDER"))
DEBUG = os.environ.get("DJANGO_DEBUG", "0" if _HOSTED else "1") == "1"
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "*" if DEBUG else "").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o]

# Render sets RENDER_EXTERNAL_HOSTNAME (e.g. islandstay.onrender.com); allow it automatically.
RENDER_HOST = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if RENDER_HOST:
    ALLOWED_HOSTS.append(RENDER_HOST)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_HOST}")

# Vercel sets VERCEL=1 plus the deployment and production hostnames; allow them automatically.
ON_VERCEL = os.environ.get("VERCEL") == "1"
if ON_VERCEL:
    for host in {os.environ.get("VERCEL_URL"), os.environ.get("VERCEL_BRANCH_URL"),
                 os.environ.get("VERCEL_PROJECT_PRODUCTION_URL")} - {None, ""}:
        ALLOWED_HOSTS.append(host)
        CSRF_TRUSTED_ORIGINS.append(f"https://{host}")
    ALLOWED_HOSTS.append(".vercel.app")

INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.sitemaps",
    "accounts",
    "directory",
    "social",
    "analytics",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "config.request_context.RequestContextMiddleware",
    "config.setup_check.SetupCheckMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "config.error_details.AdminErrorDetailsMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "directory.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# DATABASE_URL (e.g. Render Postgres) in production; a local SQLite file otherwise.
# Vercel's Postgres (Neon) integration provides DATABASE_URL / POSTGRES_URL, possibly with a custom prefix
# (e.g. STORAGE_DATABASE_URL). Use the first Postgres URL found.
DATABASE_URL_SOURCE = None
for _name in ["DATABASE_URL", "POSTGRES_URL"] + sorted(
    k for k in os.environ if k.endswith(("_DATABASE_URL", "_POSTGRES_URL")) and "UNPOOLED" not in k and "NON_POOLING" not in k
):
    if os.environ.get(_name, "").startswith(("postgres://", "postgresql://")):
        DATABASE_URL_SOURCE = _name
        os.environ["DATABASE_URL"] = os.environ[_name]
        break

# Without DJANGO_SECRET_KEY on a hosted site, derive a stable secret from the (secret) database URL.
if SECRET_KEY.startswith("dev-only") and _HOSTED and os.environ.get("DATABASE_URL"):
    import hashlib

    SECRET_KEY = hashlib.sha256(("islandstay-secret:" + os.environ["DATABASE_URL"]).encode()).hexdigest()
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=0 if ON_VERCEL else 600,  # serverless instances shouldn't hold connections open
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Indian/Maldives"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", BASE_DIR / "media"))
# Serve uploaded photos through Django in production (fine for a site of this size).
SERVE_MEDIA = os.environ.get("SERVE_MEDIA", "1") == "1"

# Vercel Blob's key is BLOB_READ_WRITE_TOKEN, or <PREFIX>_READ_WRITE_TOKEN when connected with a custom prefix.
BLOB_TOKEN_SOURCE = "BLOB_READ_WRITE_TOKEN" if os.environ.get("BLOB_READ_WRITE_TOKEN") else None
if not BLOB_TOKEN_SOURCE:
    for _name in sorted(os.environ):
        if os.environ[_name].startswith("vercel_blob_rw_"):
            BLOB_TOKEN_SOURCE = _name
            os.environ["BLOB_READ_WRITE_TOKEN"] = os.environ[_name]
            break
# Newer Blob connections give BLOB_STORE_ID (or <PREFIX>_STORE_ID) and sign requests with Vercel OIDC instead.
if not BLOB_TOKEN_SOURCE:
    for _name in ["BLOB_STORE_ID"] + sorted(k for k in os.environ if k.endswith("_STORE_ID")):
        if os.environ.get(_name, "").startswith("store_"):
            BLOB_TOKEN_SOURCE = _name
            os.environ["BLOB_STORE_ID"] = os.environ[_name]
            break

STORAGES = {
    # Uploaded photos: Vercel Blob when connected (no permanent disk on Vercel), otherwise the local disk.
    "default": {"BACKEND": "config.blob_storage.VercelBlobStorage" if BLOB_TOKEN_SOURCE
                else "config.blob_storage.UploadsNotConfigured" if ON_VERCEL
                else "django.core.files.storage.FileSystemStorage"},
    # Vercel serves collected static files from its CDN; hashed file names are only used elsewhere.
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage" if DEBUG or ON_VERCEL
        else "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "1") == "1"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_CONTENT_TYPE_NOSNIFF = True

# Settings a hosted site can't run without. Builds still succeed without them (Vercel builds as soon as a
# project is imported), but every page shows a setup checklist until they are added. See config/setup_check.py.
SETUP_MISSING = []
if not DEBUG and SECRET_KEY.startswith("dev-only"):
    SETUP_MISSING.append(("DJANGO_SECRET_KEY", "Settings → Environment Variables: add DJANGO_SECRET_KEY with a long random value."))
if ON_VERCEL and not os.environ.get("DATABASE_URL"):
    SETUP_MISSING.append(("Database", "Storage → Create → Neon (Postgres), then Connect Project → tick Production, Preview and Development."))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "directory:dashboard"
LOGOUT_REDIRECT_URL = "directory:home"

# Email: printed to the console in development. Set EMAIL_HOST etc. for production SMTP.
def env(name, default=""):
    """Environment variable, treating an empty value as unset (Render can create empty variables)."""
    return os.environ.get(name) or default


EMAIL_BACKEND = env("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD").replace(" ", "")  # Gmail shows app passwords in groups of four
EMAIL_USE_SSL = EMAIL_PORT == 465
EMAIL_USE_TLS = not EMAIL_USE_SSL
EMAIL_TIMEOUT = 15
# Gmail and most providers only send "from" the signed-in address, so default to it.
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL") or (
    f"Island Stay <{EMAIL_HOST_USER}>" if "@" in EMAIL_HOST_USER else "Island Stay <no-reply@islandstay.mv>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL
# With SMTP details filled in, send real email even if DJANGO_EMAIL_BACKEND wasn't set.
if EMAIL_HOST and "DJANGO_EMAIL_BACKEND" not in os.environ:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
# False means emails are only written to the server log, not delivered.
EMAIL_CONFIGURED = EMAIL_BACKEND.endswith("smtp.EmailBackend") and bool(EMAIL_HOST)

SITE_NAME = "Island Stay"
# Shown on the privacy and cookie pages as the address for data requests.
CONTACT_EMAIL = env("CONTACT_EMAIL")
ADMIN_NOTIFY_EMAILS = [e.strip() for e in env("ADMIN_NOTIFY_EMAILS").split(",") if e.strip()]

# Prices are hidden on the public site by default; owners still confirm rates directly with guests.
# Set SHOW_PRICES=1 to display the indicative "from" prices again.
SHOW_PRICES = os.environ.get("SHOW_PRICES", "0") == "1"

AUTHENTICATION_BACKENDS = ["accounts.backends.CaseInsensitiveEmailBackend"]


# ---------------------------------------------------------------- back office (django-unfold)
from django.templatetags.static import static  # noqa: E402
from django.urls import reverse_lazy  # noqa: E402


def _admin_link(name, query=""):
    return lambda request: str(reverse_lazy(name)) + query


UNFOLD = {
    "SITE_TITLE": "Island Stay back office",
    "SITE_HEADER": "Island Stay",
    "SITE_SUBHEADER": "Back office",
    "SITE_URL": "/",
    "SITE_ICON": lambda request: static("img/brand/islandstay-symbol-simple-light.svg"),
    "SITE_FAVICONS": [{"rel": "icon", "type": "image/svg+xml", "href": lambda request: static("img/brand/favicon.svg")}],
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "SHOW_BACK_BUTTON": True,
    "ENVIRONMENT": "directory.admin_ui.environment_callback",
    "DASHBOARD_CALLBACK": "directory.admin_ui.dashboard_callback",
    "STYLES": [
        lambda request: "https://fonts.googleapis.com/css2?family=Outfit:wght@400;600&family=Plus+Jakarta+Sans:wght@400;600;800&family=Noto+Sans:wght@400;600&display=swap",
        lambda request: static("css/admin.css"),
    ],
    "SCRIPTS": [
        lambda request: static("js/admin.js"),
    ],
    "COLORS": {
        "primary": {
            "50": "oklch(98.4% .019 200.873)", "100": "oklch(95.6% .045 203.388)", "200": "oklch(91.7% .08 205.041)",
            "300": "oklch(86.5% .127 207.078)", "400": "oklch(78.9% .154 211.53)", "500": "oklch(71.5% .143 215.221)",
            "600": "oklch(52% .105 223.128)", "700": "oklch(45% .085 224.283)", "800": "oklch(39.8% .07 227.392)",
            "900": "oklch(34% .06 228)", "950": "oklch(30.2% .056 229.695)",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Overview",
                "items": [
                    {"title": "Dashboard", "icon": "space_dashboard", "link": reverse_lazy("admin:index")},
                ],
            },
            {
                "title": "Needs attention",
                "items": [
                    {"title": "Listings to review", "icon": "pending_actions",
                     "link": _admin_link("admin:directory_listing_changelist", "?status__exact=pending"),
                     "badge": "directory.admin_ui.badge_pending_listings"},
                    {"title": "Verification requests", "icon": "verified_user",
                     "link": _admin_link("admin:directory_listing_changelist", "?verification=requested"),
                     "badge": "directory.admin_ui.badge_verification"},
                    {"title": "New booking requests", "icon": "mark_email_unread",
                     "link": _admin_link("admin:directory_enquiry_changelist", "?status__exact=new"),
                     "badge": "directory.admin_ui.badge_new_enquiries"},
                    {"title": "Listing claims", "icon": "how_to_reg",
                     "link": _admin_link("admin:directory_listingclaim_changelist", "?status__exact=pending"),
                     "badge": "directory.admin_ui.badge_claims"},
                    {"title": "Reviews to check", "icon": "reviews",
                     "link": _admin_link("admin:directory_review_changelist", "?status__exact=pending"),
                     "badge": "directory.admin_ui.badge_reviews"},
                    {"title": "Island suggestions", "icon": "add_location_alt",
                     "link": _admin_link("admin:directory_islandsuggestion_changelist", "?handled__exact=0"),
                     "badge": "directory.admin_ui.badge_suggestions"},
                ],
            },
            {
                "title": "Directory",
                "items": [
                    {"title": "All listings", "icon": "storefront", "link": reverse_lazy("admin:directory_listing_changelist")},
                    {"title": "Booking requests", "icon": "inbox", "link": reverse_lazy("admin:directory_enquiry_changelist")},
                    {"title": "Islands", "icon": "landscape", "link": reverse_lazy("admin:directory_island_changelist")},
                    {"title": "Home page islands", "icon": "home", "link": reverse_lazy("admin:directory_homefeature_changelist")},
                    {"title": "Travel guides", "icon": "menu_book", "link": reverse_lazy("admin:directory_guide_changelist")},
                    {"title": "Page banners", "icon": "wallpaper", "link": reverse_lazy("admin:directory_pagebanner_changelist")},
                    {"title": "Atolls", "icon": "public", "link": reverse_lazy("admin:directory_atoll_changelist")},
                    {"title": "Transport routes", "icon": "directions_boat", "link": reverse_lazy("admin:directory_transportroute_changelist")},
                ],
            },
            {
                "title": "Insights",
                "items": [
                    {"title": "Analytics", "icon": "insights", "link": reverse_lazy("admin:analytics_dashboard")},
                    {"title": "Visitors", "icon": "person_search", "link": reverse_lazy("admin:analytics_visitor_changelist")},
                ],
            },
            {
                "title": "Social media",
                "items": [
                    {"title": "Calendar", "icon": "calendar_month", "link": reverse_lazy("admin:social_calendar")},
                    {"title": "All posts", "icon": "photo_library", "link": reverse_lazy("admin:social_socialpost_changelist")},
                    {"title": "Design templates", "icon": "palette", "link": reverse_lazy("admin:social_templates")},
                    {"title": "Playbook", "icon": "menu_book", "link": reverse_lazy("admin:social_playbook")},
                ],
            },
            {
                "title": "Settings",
                "collapsible": True,
                "items": [
                    {"title": "Activity types", "icon": "scuba_diving", "link": reverse_lazy("admin:directory_activitytype_changelist")},
                    {"title": "Amenities", "icon": "checklist", "link": reverse_lazy("admin:directory_amenity_changelist")},
                    {"title": "Users & businesses", "icon": "group", "link": reverse_lazy("admin:auth_user_changelist")},
                    {"title": "Staff groups", "icon": "admin_panel_settings", "link": reverse_lazy("admin:auth_group_changelist")},
                ],
            },
        ],
    },
}



# Vercel Cron calls /cron/photos/ with this secret to link missing Wikimedia photos.
CRON_SECRET = os.environ.get("CRON_SECRET", "")
