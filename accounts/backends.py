import datetime as dt

from django.contrib.auth.backends import ModelBackend
from django.db.models import F
from django.utils import timezone

WINDOW = dt.timedelta(minutes=15)
LIMITS = {"user": 8, "ip": 40}  # failed attempts allowed per window, per account and per IP address


def client_ip(request):
    if request is None:
        return ""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")  # Vercel puts the visitor's address first
    return (forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR", ""))[:64]


def _keys(request, username):
    keys = {"user": f"user:{username}"}
    ip = client_ip(request)
    if ip:
        keys["ip"] = f"ip:{ip}"
    return keys


def is_locked(request, username):
    from .models import LoginFailure

    since = timezone.now() - WINDOW
    for kind, key in _keys(request, username).items():
        row = LoginFailure.objects.filter(key=key, first_at__gte=since).first()
        if row and row.count >= LIMITS[kind]:
            return True
    return False


def record_failure(request, username):
    from .models import LoginFailure

    now = timezone.now()
    for key in _keys(request, username).values():
        row, created = LoginFailure.objects.get_or_create(key=key, defaults={"count": 1, "first_at": now})
        if created:
            continue
        if row.first_at < now - WINDOW:
            LoginFailure.objects.filter(pk=row.pk).update(count=1, first_at=now)
        else:
            LoginFailure.objects.filter(pk=row.pk).update(count=F("count") + 1)


def clear_failures(request, username):
    from .models import LoginFailure

    LoginFailure.objects.filter(key=f"user:{username}").delete()


class CaseInsensitiveEmailBackend(ModelBackend):
    """Usernames are stored as lower-case email addresses, so ignore capitalisation when logging in.

    After too many wrong passwords for one account (or from one address) within 15 minutes, sign-in is
    refused until the window passes, even with the right password.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username:
            username = username.strip().lower()
        if username and is_locked(request, username):
            if request is not None:
                request.login_locked = True
            return None
        user = super().authenticate(request, username=username, password=password, **kwargs)
        if username and password is not None:
            if user is None:
                record_failure(request, username)
            else:
                clear_failures(request, username)
        return user
