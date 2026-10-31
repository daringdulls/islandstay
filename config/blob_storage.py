"""Django file storage on Vercel Blob, for hosts without a permanent disk (Vercel).

Enabled automatically when BLOB_READ_WRITE_TOKEN is set (Vercel adds it when you connect a Blob store).
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
    def __init__(self, token=None):
        self.token = token or os.environ.get("BLOB_READ_WRITE_TOKEN", "")
        if not self.token.startswith(TOKEN_PREFIX):
            raise ValueError("BLOB_READ_WRITE_TOKEN is missing or not a Vercel Blob read-write token.")
        # Token format: vercel_blob_rw_<storeId>_<secret>
        self.store_id = self.token[len(TOKEN_PREFIX):].split("_", 1)[0].lower()
        self.base_url = f"https://{self.store_id}.public.blob.vercel-storage.com/"
        self.private_base_url = f"https://{self.store_id}.private.blob.vercel-storage.com/"

    # The store's access level; shared by all instances once known.
    access = os.environ.get("BLOB_ACCESS", "").lower() or None

    def _request(self, method, url, data=None, headers=None):
        req = urllib.request.Request(url, data=data, method=method, headers={
            "authorization": f"Bearer {self.token}", "x-api-version": API_VERSION, **(headers or {})})
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
        if name.startswith(PRIVATE_MARK):
            return "/media/blob/" + urllib.parse.quote(name[len(PRIVATE_MARK):], safe="/")
        return self._blob_url(name)

    def delete(self, name):
        if name:
            self._request("POST", f"{API_URL}/delete", data=json.dumps({"urls": [self._blob_url(name)]}).encode(),
                          headers={"content-type": "application/json"})

    def fetch_private(self, path):
        """Download a private blob with the store token. Returns (bytes, content_type)."""
        req = urllib.request.Request(self.private_base_url + urllib.parse.quote(path, safe="/"), headers={
            "authorization": f"Bearer {self.token}", "x-api-version": API_VERSION})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read(), r.headers.get("content-type", "application/octet-stream")

    def exists(self, name):
        return False  # Vercel adds a random suffix, so names never clash

    def get_available_name(self, name, max_length=None):
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


def blob_proxy(request, path):
    """Serve a file from a private Vercel Blob store (photos must be viewable by visitors)."""
    from django.core.files.storage import default_storage
    from django.http import Http404, HttpResponse

    if not isinstance(default_storage, VercelBlobStorage) or ".." in path:
        raise Http404
    # Only serve files the site itself uploads (photos and verification documents to staff).
    if path.startswith("verification/") and not (request.user.is_authenticated and request.user.is_staff):
        raise Http404
    try:
        data, content_type = default_storage.fetch_private(path)
    except Exception:
        raise Http404
    response = HttpResponse(data, content_type=content_type)
    response["Cache-Control"] = "public, max-age=86400" if not path.startswith("verification/") else "private, no-store"
    return response
