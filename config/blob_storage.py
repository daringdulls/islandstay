"""Django file storage on Vercel Blob, for hosts without a permanent disk (Vercel).

Enabled automatically when BLOB_READ_WRITE_TOKEN is set (Vercel adds it when you connect a Blob store).
Files are public, with a random suffix in the name so links can't be guessed. Uses Vercel's Blob HTTP API
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


@deconstructible
class VercelBlobStorage(Storage):
    def __init__(self, token=None):
        self.token = token or os.environ.get("BLOB_READ_WRITE_TOKEN", "")
        if not self.token.startswith(TOKEN_PREFIX):
            raise ValueError("BLOB_READ_WRITE_TOKEN is missing or not a Vercel Blob read-write token.")
        # Token format: vercel_blob_rw_<storeId>_<secret>
        self.store_id = self.token[len(TOKEN_PREFIX):].split("_", 1)[0].lower()
        self.base_url = f"https://{self.store_id}.public.blob.vercel-storage.com/"

    def _request(self, method, url, data=None, headers=None):
        req = urllib.request.Request(url, data=data, method=method, headers={
            "authorization": f"Bearer {self.token}", "x-api-version": API_VERSION, **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read()
        except HTTPError as exc:
            raise OSError(f"Vercel Blob {method} failed ({exc.code}): {exc.read()[:300]!r}") from exc
        return json.loads(body) if body else {}

    def _save(self, name, content):
        content.seek(0)
        data = content.read()
        content_type = getattr(content, "content_type", None) or "application/octet-stream"
        result = self._request(
            "PUT", f"{API_URL}?{urllib.parse.urlencode({'pathname': name})}", data=data,
            headers={"x-vercel-blob-access": "public", "x-add-random-suffix": "1", "x-allow-overwrite": "0",
                     "x-content-type": content_type, "content-length": str(len(data))},
        )
        # The stored name is the pathname Vercel assigned (with its random suffix).
        return result.get("pathname") or urllib.parse.unquote(urllib.parse.urlparse(result["url"]).path.lstrip("/"))

    def url(self, name):
        return self.base_url + urllib.parse.quote(name, safe="/")

    def delete(self, name):
        if name:
            self._request("POST", f"{API_URL}/delete", data=json.dumps({"urls": [self.url(name)]}).encode(),
                          headers={"content-type": "application/json"})

    def exists(self, name):
        return False  # Vercel adds a random suffix, so names never clash

    def get_available_name(self, name, max_length=None):
        return name

    def size(self, name):
        return 0

    def _open(self, name, mode="rb"):
        from django.core.files.base import ContentFile

        with urllib.request.urlopen(self.url(name), timeout=60) as r:
            return ContentFile(r.read(), name=name)
