"""Instant photo manager for islands and listings in the back office.

Every action (upload, remove, set as cover, reorder, caption) is saved straight away through small JSON
endpoints, so editors never have to press Save and upload again. The photo fields are kept out of the main
form, so saving the form can't undo a change made here.
"""
import json

from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.views.decorators.http import require_POST
from PIL import Image

from .models import Island, IslandPhoto, Listing, ListingPhoto

MAX_BYTES = 15 * 1024 * 1024


try:  # iPhone photos (HEIC/HEIF) and AVIF
    import pillow_heif
    pillow_heif.register_heif_opener()
    try:
        pillow_heif.register_avif_opener()
    except Exception:
        pass
except Exception:
    pillow_heif = None

KEEP_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}


def _prepare_image(f, max_side=2600):
    """Check an uploaded photo and return (file, error). Photos in other formats (iPhone HEIC, AVIF, TIFF,
    BMP…) are converted to JPG, very large ones are scaled down, and phone rotation is applied."""
    import io
    import os

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import ImageOps

    if not f:
        return None, "Choose a photo."
    if f.size > MAX_BYTES:
        return None, f"That photo is {f.size / 1048576:.0f} MB. Use one under 15 MB."
    try:
        img = Image.open(f)
        img.load()
    except Exception:
        name = (f.name or "").lower()
        if name.endswith((".heic", ".heif")):
            return None, "This iPhone photo (HEIC) couldn't be read. Export it as JPG and try again."
        return None, "That file isn't a photo we can read. Use a JPG, PNG or WebP photo."
    fmt = (img.format or "").upper()
    too_big = max(img.size) > max_side
    if fmt == "GIF" or (fmt in KEEP_FORMATS and not too_big):
        f.seek(0)
        return f, None
    img = ImageOps.exif_transpose(img)
    keep_png = fmt == "PNG" and img.mode in ("RGBA", "LA", "P")
    if too_big:
        img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    base = os.path.splitext(os.path.basename(f.name or "photo"))[0] or "photo"
    if keep_png:
        img.save(buf, "PNG", optimize=True)
        return SimpleUploadedFile(base + ".png", buf.getvalue(), content_type="image/png"), None
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.save(buf, "JPEG", quality=86, optimize=True, progressive=True)
    return SimpleUploadedFile(base + ".jpg", buf.getvalue(), content_type="image/jpeg"), None


def _check_image(f):
    """Kept for callers that only need a yes/no check."""
    return _prepare_image(f)[1]


def _safe_url(field):
    try:
        return field.url if field else ""
    except Exception:
        return ""


class PhotoManagerMixin:
    """Add to an admin class. Subclasses set photo_kind = "island" or "listing"."""
    photo_kind = None
    change_form_after_template = None

    # ------------------------------------------------------------------ state
    def photo_state(self, obj):
        if self.photo_kind == "island":
            cover = obj.photo_url
            gallery = [{"id": p.pk, "url": p.thumb_url, "caption": p.caption, "credit": p.credit, "visible": p.is_visible,
                        "is_cover": bool(cover) and p.image_url == cover}
                       for p in obj.photos.all()]
            return {"cover": cover and obj.card_photo_url, "cover_full": cover, "cover_credit": obj.cover_credit,
                    "cover_is_link": bool(obj.cover_image_url and not obj.cover_image), "gallery": gallery,
                    "logo": None}
        cover = _safe_url(obj.cover_image)
        gallery = []
        for p in obj.photos.all():
            url = _safe_url(p.image)
            gallery.append({"id": p.pk, "url": url, "caption": p.caption, "visible": True,
                            "is_cover": bool(obj.cover_image) and p.image.name == obj.cover_image.name})
        return {"cover": cover, "cover_full": cover, "cover_credit": "", "cover_is_link": False,
                "gallery": gallery, "logo": _safe_url(obj.logo), "has_logo": True,
                "fallback": "" if cover else obj.island.card_photo_url}

    def _obj(self, request, object_id):
        model = Island if self.photo_kind == "island" else Listing
        obj = get_object_or_404(model, pk=object_id)
        if not self.has_change_permission(request, obj):
            return None
        return obj

    def _reply(self, obj, **extra):
        obj.refresh_from_db()
        return JsonResponse({"ok": True, "state": self.photo_state(obj), **extra})

    # ------------------------------------------------------------------ endpoints
    def get_urls(self):
        name = f"directory_{self.photo_kind}"
        wrap = self.admin_site.admin_view
        return [
            path("<int:object_id>/photos/", wrap(self.photos_view), name=f"{name}_photos"),
        ] + super().get_urls()

    def photos_view(self, request, object_id):
        obj = self._obj(request, object_id)
        if obj is None:
            return JsonResponse({"error": "You don't have permission to change these photos."}, status=403)
        if request.method == "GET":
            return JsonResponse({"ok": True, "state": self.photo_state(obj)})
        if request.method != "POST":
            return JsonResponse({"error": "POST only"}, status=405)
        act = request.POST.get("action", "")
        handler = getattr(self, f"_photo_{act}", None)
        if not handler:
            return JsonResponse({"error": "Unknown action."}, status=400)
        try:
            return handler(request, obj)
        except Exception as exc:  # show a readable message in the panel instead of a broken page
            return JsonResponse({"error": f"Couldn't save: {exc}"[:300]}, status=400)

    # cover
    def _photo_cover_upload(self, request, obj):
        f, err = _prepare_image(request.FILES.get("file"))
        if err:
            return JsonResponse({"error": err}, status=400)
        folder = "islands" if self.photo_kind == "island" else "listings"
        old = obj.cover_image.name if obj.cover_image else ""
        obj.cover_image.save(f"{folder}/{f.name}", f, save=False)
        fields = ["cover_image"]
        if self.photo_kind == "island":
            obj.cover_image_url, obj.cover_credit, obj.cover_license, obj.cover_source_url = "", request.POST.get("credit", ""), "", ""
            fields += ["cover_image_url", "cover_credit", "cover_license", "cover_source_url"]
        obj.save(update_fields=fields)
        self._maybe_delete_file(old, obj)
        return self._reply(obj)

    def _photo_cover_link(self, request, obj):
        url = request.POST.get("url", "").strip()
        if self.photo_kind != "island" or not url.startswith(("https://", "http://")):
            return JsonResponse({"error": "Paste a full photo link starting with https://"}, status=400)
        old = obj.cover_image.name if obj.cover_image else ""
        obj.cover_image = ""
        obj.cover_image_url = url
        obj.cover_credit = request.POST.get("credit", "")[:200]
        obj.save(update_fields=["cover_image", "cover_image_url", "cover_credit"])
        self._maybe_delete_file(old, obj)
        return self._reply(obj)

    def _photo_cover_remove(self, request, obj):
        old = obj.cover_image.name if obj.cover_image else ""
        obj.cover_image = ""
        fields = ["cover_image"]
        if self.photo_kind == "island":
            obj.cover_image_url, obj.cover_credit, obj.cover_license, obj.cover_source_url = "", "", "", ""
            fields += ["cover_image_url", "cover_credit", "cover_license", "cover_source_url"]
        obj.save(update_fields=fields)
        self._maybe_delete_file(old, obj)
        return self._reply(obj)

    def _photo_cover_credit(self, request, obj):
        if self.photo_kind != "island":
            return JsonResponse({"error": "Not available."}, status=400)
        obj.cover_credit = request.POST.get("credit", "")[:200]
        obj.save(update_fields=["cover_credit"])
        return self._reply(obj)

    # logo (listings)
    def _photo_logo_upload(self, request, obj):
        f, err = _prepare_image(request.FILES.get("file"), max_side=1000)
        if err or self.photo_kind != "listing":
            return JsonResponse({"error": err or "Logos are for listings."}, status=400)
        old = obj.logo.name if obj.logo else ""
        obj.logo.save(f"logos/{f.name}", f, save=False)
        obj.save(update_fields=["logo"])
        self._maybe_delete_file(old, obj)
        return self._reply(obj)

    def _photo_logo_remove(self, request, obj):
        old = obj.logo.name if obj.logo else ""
        obj.logo = ""
        obj.save(update_fields=["logo"])
        self._maybe_delete_file(old, obj)
        return self._reply(obj)

    # gallery
    def _photo_gallery_upload(self, request, obj):
        files = request.FILES.getlist("files")
        if not files:
            return JsonResponse({"error": "Choose one or more photos."}, status=400)
        errors, added = [], 0
        start = (obj.photos.order_by("-order").values_list("order", flat=True).first() or 0) + 1
        for n, original in enumerate(files[:30]):
            f, err = _prepare_image(original)
            if err:
                errors.append(f"{original.name}: {err}")
                continue
            if self.photo_kind == "island":
                name = default_storage.save(f"islands/gallery/{f.name}", f)
                IslandPhoto.objects.create(island=obj, image_url=default_storage.url(name), order=start + n,
                                           credit=request.POST.get("credit", "")[:200])
            else:
                p = ListingPhoto(listing=obj, order=start + n)
                p.image.save(f"listings/gallery/{f.name}", f, save=True)
            added += 1
        # The first photo becomes the cover when there is none yet.
        if added and request.POST.get("auto_cover") == "1" and not (obj.cover_image or getattr(obj, "cover_image_url", "")):
            first = obj.photos.order_by("-order", "-id")[added - 1] if added else None
            if first:
                self._set_cover(obj, first)
        return self._reply(obj, added=added, errors=errors)

    def _photo_gallery_delete(self, request, obj):
        p = get_object_or_404(obj.photos, pk=request.POST.get("id"))
        if self.photo_kind == "listing":
            name = p.image.name
            was_cover = bool(obj.cover_image) and obj.cover_image.name == name
            p.delete()
            if not was_cover:
                self._maybe_delete_file(name, obj)
        else:
            p.delete()
        return self._reply(obj)

    def _set_cover(self, obj, p):
        if self.photo_kind == "island":
            obj.cover_image = ""
            obj.cover_image_url = p.image_url
            obj.cover_credit, obj.cover_license, obj.cover_source_url = p.credit, p.license, p.source_url
            obj.save(update_fields=["cover_image", "cover_image_url", "cover_credit", "cover_license", "cover_source_url"])
        else:
            obj.cover_image = p.image.name  # the same stored file, no copy needed
            obj.save(update_fields=["cover_image"])

    def _photo_gallery_cover(self, request, obj):
        self._set_cover(obj, get_object_or_404(obj.photos, pk=request.POST.get("id")))
        return self._reply(obj)

    def _photo_gallery_caption(self, request, obj):
        p = get_object_or_404(obj.photos, pk=request.POST.get("id"))
        p.caption = request.POST.get("caption", "")[:120 if self.photo_kind == "listing" else 200]
        p.save(update_fields=["caption"])
        return self._reply(obj)

    def _photo_gallery_visible(self, request, obj):
        if self.photo_kind != "island":
            return JsonResponse({"error": "Not available."}, status=400)
        p = get_object_or_404(obj.photos, pk=request.POST.get("id"))
        p.is_visible = request.POST.get("visible") == "1"
        p.save(update_fields=["is_visible"])
        return self._reply(obj)

    def _photo_gallery_order(self, request, obj):
        try:
            ids = [int(x) for x in json.loads(request.POST.get("ids", "[]"))]
        except (ValueError, TypeError):
            return JsonResponse({"error": "Couldn't read the new order."}, status=400)
        photos = {p.pk: p for p in obj.photos.all()}
        for n, pid in enumerate(ids):
            if pid in photos and photos[pid].order != n:
                photos[pid].order = n
                photos[pid].save(update_fields=["order"])
        return self._reply(obj)

    # ------------------------------------------------------------------ helpers
    def _maybe_delete_file(self, name, obj):
        """Remove a replaced file from storage unless something else still uses it."""
        if not name:
            return
        in_use = False
        if self.photo_kind == "listing":
            in_use = (obj.cover_image and obj.cover_image.name == name) or (obj.logo and obj.logo.name == name) \
                or ListingPhoto.objects.filter(image=name).exists()
        if not in_use:
            try:
                default_storage.delete(name)
            except Exception:
                pass

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        if object_id:
            obj = self.get_object(request, object_id)
            if obj is not None:
                extra_context["photo_manager"] = {
                    "kind": self.photo_kind,
                    "url": reverse(f"admin:directory_{self.photo_kind}_photos", args=[obj.pk]),
                    "state": self.photo_state(obj),
                    "public_url": obj.get_absolute_url(),
                }
        else:
            extra_context["photo_manager"] = {"kind": self.photo_kind, "new": True}
        return super().changeform_view(request, object_id, form_url, extra_context)
