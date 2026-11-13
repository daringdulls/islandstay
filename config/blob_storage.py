"""Django file storage on Vercel Blob, for hosts without a permanent disk (Vercel).

Enabled automatically when a Blob store is connected. Newer stores give the project BLOB_STORE_ID and sign each
request with a short-lived Vercel OIDC token (x-vercel-oidc-token header); older ones give BLOB_READ_WRITE_TOKEN.
Both are supported.
Works with both public and private stores (detected on the first upload, or set BLOB_ACCESS=public|private).
Public files are linked directly; private files are stored with a "~p/" marker in their name and served
through the site at /media/blob/<path> (see blob_proxy). Names get a random suffix so links can't be guessed. Uses Vercel's Blob HTTP API
directly (the same calls as the official SDK) so no extra packages are needed.
"""
import json
import os
import urllib.parse
import urllib.request
from urllib.error import HTTPError

from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible

API_URL = os.environ.get("VERCEL_BLOB_API_URL", "https://vercel.com/api/blob").rstrip("/")
API_VERSION = "12"
TOKEN_PREFIX = "vercel_blob_rw_"
PRIVATE_MARK = "~p/"


@deconstructible
class VercelBlobStorage(Storage):
    def __init__(self, token=None, store_id=None):
        self.token = token or os.environ.get("BLOB_READ_WRITE_TOKEN", "")
        if self.token.startswith(TOKEN_PREFIX):
            # Read-write token format: vercel_blob_rw_<storeId>_<secret>
            self.store_id = self.token[len(TOKEN_PREFIX):].split("_", 1)[0]
            self.oidc = False
        else:
            raw = (store_id or os.environ.get("BLOB_STORE_ID", "")).strip()
            if not raw:
                raise ValueError("No Vercel Blob credentials: set BLOB_READ_WRITE_TOKEN or BLOB_STORE_ID.")
            self.store_id = raw.removeprefix("store_")
            self.oidc = True
        host_id = self.store_id.lower()
        self.base_url = f"https://{host_id}.public.blob.vercel-storage.com/"
        self.private_base_url = f"https://{host_id}.private.blob.vercel-storage.com/"

    def _auth_headers(self):
        if not self.oidc:
            return {"authorization": f"Bearer {self.token}", "x-api-version": API_VERSION}
        from config.request_context import current_oidc_token

        oidc_token = current_oidc_token()
        if not oidc_token:
            raise OSError("Vercel did not provide a sign-in (OIDC) token for this request, so the photo "
                          "can't be stored. In Vercel: Settings, Security, make sure Secure backend access "
                          "with OIDC federation is enabled, then redeploy.")
        return {"authorization": f"Bearer {oidc_token}", "x-api-version": API_VERSION,
                "x-vercel-blob-store-id": self.store_id}

    # The store's access level; shared by all instances once known.
    access = os.environ.get("BLOB_ACCESS", "").lower() or None

    def _request(self, method, url, data=None, headers=None):
        req = urllib.request.Request(url, data=data, method=method, headers={**self._auth_headers(), **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read()
        except HTTPError as exc:
            raise OSError(f"Vercel Blob {method} failed ({exc.code}): {exc.read()[:300]!r}") from exc
        return json.loads(body) if body else {}

    def _put(self, name, data, content_type, access):
        return self._request(
            "PUT", f"{API_URL}?{urllib.parse.urlencode({'pathname': name})}", data=data,
            headers={"x-vercel-blob-access": access, "x-add-random-suffix": "1", "x-allow-overwrite": "0",
                     "x-content-type": content_type, "content-length": str(len(data))},
        )

    def _save(self, name, content):
        content.seek(0)
        data = content.read()
        content_type = getattr(content, "content_type", None) or "application/octet-stream"
        access = type(self).access or "public"
        try:
            result = self._put(name, data, content_type, access)
        except OSError:
            if type(self).access:  # access was known, so this is a real failure
                raise
            access = "private"  # a private store refuses public uploads: try again as private
            result = self._put(name, data, content_type, access)
        type(self).access = access
        # The stored name is the pathname Vercel assigned (with its random suffix).
        stored = result.get("pathname") or urllib.parse.unquote(urllib.parse.urlparse(result["url"]).path.lstrip("/"))
        return (PRIVATE_MARK + stored) if access == "private" else stored

    def _blob_url(self, name):
        if name.startswith(PRIVATE_MARK):
            return self.private_base_url + urllib.parse.quote(name[len(PRIVATE_MARK):], safe="/")
        return self.base_url + urllib.parse.quote(name, safe="/")

    def url(self, name):
        # Photos are served through the site (/media/blob/...), which reads them with the store's credentials.
        # That works for private stores and for files saved before the store's access level was known.
        # Set BLOB_ACCESS=public to link a public store's files directly instead.
        if os.environ.get("BLOB_ACCESS", "").lower() == "public" and not name.startswith(PRIVATE_MARK):
            return self._blob_url(name)
        return "/media/blob/" + urllib.parse.quote(name.removeprefix(PRIVATE_MARK), safe="/")

    def delete(self, name):
        if name:
            self._request("POST", f"{API_URL}/delete", data=json.dumps({"urls": [self._blob_url(name)]}).encode(),
                          headers={"content-type": "application/json"})

    def fetch_private(self, path):
        """Download a private blob with the store token. Returns (bytes, content_type)."""
        req = urllib.request.Request(self.private_base_url + urllib.parse.quote(path, safe="/"),
                                     headers=self._auth_headers())
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read(), r.headers.get("content-type", "application/octet-stream")

    def exists(self, name):
        return False  # Vercel adds a random suffix, so names never clash

    def get_available_name(self, name, max_length=None):
        # Vercel adds "-<random 30 chars>" before the extension and private files get "~p/": keep room for both.
        limit = (max_length or 255) - 40
        if len(name) > limit:
            folder, _, base = name.rpartition("/")
            stem, dot, ext = base.rpartition(".")
            if not dot:
                stem, ext = base, ""
            ext = ext[:10]
            keep = max(8, limit - len(folder) - 1 - len(ext) - 1)
            name = (folder + "/" if folder else "") + stem[:keep] + ("." + ext if ext else "")
        return name

    def size(self, name):
        return 0

    def _open(self, name, mode="rb"):
        from django.core.files.base import ContentFile

        if name.startswith(PRIVATE_MARK):
            return ContentFile(self.fetch_private(name[len(PRIVATE_MARK):])[0], name=name)
        with urllib.request.urlopen(self._blob_url(name), timeout=60) as r:
            return ContentFile(r.read(), name=name)


@deconstructible
class UploadsNotConfigured(Storage):
    """Used on Vercel when no Blob store is connected: explain instead of failing on the read-only disk."""

    MESSAGE = ("Photo uploads need a Vercel Blob store connected to this project: in Vercel open Storage, "
               "click your Blob store, choose Connect Project, pick this project (Production and Preview), "
               "then redeploy.")

    def _save(self, name, content):
        raise OSError(self.MESSAGE)

    def url(self, name):
        return "/media/" + urllib.parse.quote(name or "", safe="/")

    def exists(self, name):
        return False

    def delete(self, name):
        pass


def _describe(exc):
    """Short, secret-free description of a failed Blob request."""
    if isinstance(exc, HTTPError):
        try:
            body = exc.read()[:120].decode("utf-8", "replace")
        except Exception:
            body = ""
        return f"HTTP {exc.code} {body}".replace("\n", " ")
    return f"{type(exc).__name__}: {str(exc)[:160]}".replace("\n", " ")


SAFE_MEDIA_TYPES = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp", "gif": "image/gif",
    "avif": "image/avif", "heic": "image/heic", "heif": "image/heif", "pdf": "application/pdf",
    "mp4": "video/mp4", "mov": "video/quicktime", "webm": "video/webm",
}


def blob_proxy(request, path):
    """Serve a file from a private Vercel Blob store (photos must be viewable by visitors)."""
    from django.core.files.storage import default_storage
    from django.http import Http404, HttpResponse

    if not isinstance(default_storage, VercelBlobStorage) or ".." in path:
        raise Http404
    # Only serve files the site itself uploads (photos and verification documents to staff).
    if path.startswith("verification/") and not (request.user.is_authenticated and request.user.is_staff):
        raise Http404
    errors = []  # kept for debugging with a breakpoint; never shown to visitors
    try:
        data, content_type = default_storage.fetch_private(path)
    except Exception as exc:
        errors.append(f"private: {_describe(exc)}")
        public_url = default_storage.base_url + urllib.parse.quote(path, safe="/")
        data = None
        for label, headers in (("public+auth", default_storage._auth_headers), ("public", dict)):
            try:  # a file saved as public (in a store that may now require sign-in)
                with urllib.request.urlopen(urllib.request.Request(public_url, headers=headers()), timeout=60) as r:
                    data, content_type = r.read(), r.headers.get("content-type", "application/octet-stream")
                break
            except Exception as exc2:
                errors.append(f"{label}: {_describe(exc2)}")
        if data is None:
            raise Http404
    # Never trust the type the uploader's browser sent: serve only known media types, as files that can't run
    # scripts on this domain (a valid image can also be HTML, so anything else is a plain download).
    ext = path.rsplit(".", 1)[-1].lower() if "." in path.rsplit("/", 1)[-1] else ""
    safe_type = SAFE_MEDIA_TYPES.get(ext)
    response = HttpResponse(data, content_type=safe_type or "application/octet-stream")
    response["X-Content-Type-Options"] = "nosniff"
    if ext != "pdf":  # the browser's PDF viewer doesn't run inside a sandbox
        response["Content-Security-Policy"] = "default-src 'none'; img-src 'self' data:; media-src 'self'; style-src 'unsafe-inline'; sandbox"
    if not safe_type:
        response["Content-Disposition"] = "attachment"
    if path.startswith("verification/"):
        response["Cache-Control"] = "private, no-store"
    else:
        # File names carry a random suffix and never change, so browsers and Vercel's CDN can keep them.
        response["Cache-Control"] = "public, max-age=31536000, immutable"
        response["CDN-Cache-Control"] = "public, max-age=31536000, immutable"
    return response


class BlobLinkMiddleware:
    """Rewrite direct links to the store (saved in older content) to the site's photo route."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.prefix = None
        try:
            from django.core.files.storage import default_storage
            if isinstance(default_storage, VercelBlobStorage) and os.environ.get("BLOB_ACCESS", "").lower() != "public":
                self.prefix = default_storage.base_url.encode()
        except Exception:
            self.prefix = None

    def __call__(self, request):
        response = self.get_response(request)
        if self.prefix and not getattr(response, "streaming", False) and \
                response.get("Content-Type", "").startswith(("text/html", "application/json")) and self.prefix in response.content:
            response.content = response.content.replace(self.prefix, b"/media/blob/")
        return response
