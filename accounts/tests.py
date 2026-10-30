import os
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase


class AdminSetupTests(TestCase):
    def test_ensure_admin_creates_once_and_login_ignores_case(self):
        with mock.patch.dict(os.environ, {"ADMIN_EMAIL": "Owner@Example.com", "ADMIN_PASSWORD": "Secret-pass-123"}):
            call_command("ensure_admin", stdout=open(os.devnull, "w"))
            call_command("ensure_admin", stdout=open(os.devnull, "w"))
        User = get_user_model()
        self.assertEqual(User.objects.filter(is_superuser=True).count(), 1)
        self.assertTrue(self.client.login(username="OWNER@example.com", password="Secret-pass-123"))
