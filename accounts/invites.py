"""Owner accounts created by the team: find or create a user for an email, and a link to set their password."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def owner_for_email(email, business_name=""):
    """The account for this email, created (without a password) if there isn't one. Returns (user, created)."""
    from .models import Profile

    User = get_user_model()
    email = email.strip().lower()
    user = User.objects.filter(username__iexact=email).first() or User.objects.filter(email__iexact=email).first()
    if user:
        return user, False
    user = User(username=email, email=email)
    user.set_unusable_password()  # they choose one with the invite link
    user.save()
    Profile.objects.get_or_create(user=user, defaults={"business_name": business_name[:120]})
    return user, True


def site_url(request=None):
    if request is not None:
        return f"https://{request.get_host()}" if not settings.DEBUG else request.build_absolute_uri("/").rstrip("/")
    host = (getattr(settings, "CANONICAL_HOST", "") or "www.islandstaymv.com").removeprefix("www.")
    return f"https://www.{host}"


def invite_link(user, request=None):
    """A personal link where the owner sets a password and signs in. It stops working once used, or after
    PASSWORD_RESET_TIMEOUT."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return site_url(request) + reverse("accounts:welcome", args=[uid, token])
