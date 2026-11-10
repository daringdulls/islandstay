from django.conf import settings
from django.db import models


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    business_name = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    island_of_operation = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.business_name or self.user.get_username()


class LoginFailure(models.Model):
    """Failed sign-ins per account and per IP address, to slow down password guessing."""
    key = models.CharField(max_length=200, unique=True)
    count = models.PositiveIntegerField(default=0)
    first_at = models.DateTimeField()

    def __str__(self):
        return f"{self.key}: {self.count}"
