"""Django settings for the Maldives local OTA (IslandStay)."""
import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "*" if DEBUG else "").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o]

# Render sets RENDER_EXTERNAL_HOSTNAME (e.g. islandstay.onrender.com); allow it automatically.
RENDER_HOST = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if RENDER_HOST:
    ALLOWED_HOSTS.append(RENDER_HOST)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_HOST}")

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
    "accounts",
    "directory",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
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
DATABASES = {
    "default": dj_database_url.config(default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}", conn_max_age=600)
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

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "1") == "1"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_CONTENT_TYPE_NOSNIFF = True
    if SECRET_KEY.startswith("dev-only"):
        raise RuntimeError("Set DJANGO_SECRET_KEY in production.")

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
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "IslandStay Maldives <no-reply@islandstay.mv>")
# With SMTP details filled in, send real email even if DJANGO_EMAIL_BACKEND wasn't set.
if EMAIL_HOST and "DJANGO_EMAIL_BACKEND" not in os.environ:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

SITE_NAME = "IslandStay Maldives"
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
    "SITE_TITLE": "IslandStay Back Office",
    "SITE_HEADER": "IslandStay",
    "SITE_SUBHEADER": "Back office",
    "SITE_URL": "/",
    "SITE_SYMBOL": "sailing",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "SHOW_BACK_BUTTON": True,
    "ENVIRONMENT": "directory.admin_ui.environment_callback",
    "DASHBOARD_CALLBACK": "directory.admin_ui.dashboard_callback",
    "STYLES": [
        lambda request: "https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap",
        lambda request: static("css/admin.css"),
    ],
    "COLORS": {
        "primary": {
            "50": "oklch(98.4% .014 180.72)", "100": "oklch(95.3% .051 180.801)", "200": "oklch(91% .096 180.426)",
            "300": "oklch(85.5% .138 181.071)", "400": "oklch(77.7% .152 181.912)", "500": "oklch(70.4% .14 182.503)",
            "600": "oklch(60% .118 184.704)", "700": "oklch(51.1% .096 186.391)", "800": "oklch(43.7% .078 188.216)",
            "900": "oklch(38.6% .063 188.416)", "950": "oklch(27.7% .046 192.524)",
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
                    {"title": "Atolls", "icon": "public", "link": reverse_lazy("admin:directory_atoll_changelist")},
                    {"title": "Transport routes", "icon": "directions_boat", "link": reverse_lazy("admin:directory_transportroute_changelist")},
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
