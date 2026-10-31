"""Create the first admin account from environment variables, if it doesn't exist yet.

    ADMIN_EMAIL=you@example.com ADMIN_PASSWORD=... python manage.py ensure_admin

Safe to run on every deploy: an existing account is left untouched (its password is not reset).

Forgotten password: set ADMIN_RESET_PASSWORD=1 together with a new ADMIN_PASSWORD, redeploy and open the
site once. The account's password is set to ADMIN_PASSWORD (and it is made an active administrator again).
Remove ADMIN_RESET_PASSWORD afterwards.
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create an admin user from ADMIN_EMAIL / ADMIN_PASSWORD if it doesn't exist."

    def handle(self, *args, **opts):
        email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
        password = os.environ.get("ADMIN_PASSWORD", "")
        if not email or not password:
            self.stdout.write("ADMIN_EMAIL / ADMIN_PASSWORD not set; skipping admin creation.")
            return
        User = get_user_model()
        existing = User.objects.filter(username__iexact=email).first()
        if existing:
            if os.environ.get("ADMIN_RESET_PASSWORD") == "1":
                existing.set_password(password)
                existing.is_active = existing.is_staff = existing.is_superuser = True
                existing.save()
                self.stdout.write(self.style.WARNING(
                    f"Password reset for {email}. Remove ADMIN_RESET_PASSWORD from the environment now."))
            else:
                self.stdout.write(f"Admin {email} already exists.")
            return
        User.objects.create_superuser(username=email, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Created admin {email}."))
