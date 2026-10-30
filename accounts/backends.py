from django.contrib.auth.backends import ModelBackend


class CaseInsensitiveEmailBackend(ModelBackend):
    """Usernames are stored as lower-case email addresses, so ignore capitalisation when logging in."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username:
            username = username.strip().lower()
        return super().authenticate(request, username=username, password=password, **kwargs)
