"""Per-request values that code outside views needs, such as Vercel's OIDC token for Blob uploads."""
import contextvars
import os

vercel_oidc_token = contextvars.ContextVar("vercel_oidc_token", default=None)


def current_oidc_token():
    """Vercel sends a short-lived OIDC token with each request; fall back to the environment."""
    token = vercel_oidc_token.get() or os.environ.get("VERCEL_OIDC_TOKEN")
    if not token and os.environ.get("VERCEL_OIDC_TOKEN_FILE"):
        try:
            with open(os.environ["VERCEL_OIDC_TOKEN_FILE"]) as f:
                token = f.read().strip()
        except OSError:
            token = None
    return token


class RequestContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        reset = vercel_oidc_token.set(request.META.get("HTTP_X_VERCEL_OIDC_TOKEN"))
        try:
            return self.get_response(request)
        finally:
            vercel_oidc_token.reset(reset)
