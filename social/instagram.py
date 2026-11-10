"""Publishing to Instagram with the Instagram API with Instagram Login (graph.instagram.com).

Setup: a Meta developer app with the "Instagram API with Instagram Login" product. Its Instagram app ID and
secret go in INSTAGRAM_APP_ID / INSTAGRAM_APP_SECRET. Instagram can't schedule API posts itself, so
/cron/instagram/ is called every few minutes (cron-job.org or Vercel Cron) and publishes posts that are due.

Flow per post: create a media container (image, story, carousel or Reel), wait until Instagram has processed
it (Reels take a minute or more, so it continues on the next run), then publish it.
"""
import datetime as dt
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.utils import timezone

from .models import InstagramAccount, SocialAsset, SocialPost

GRAPH = "https://graph.instagram.com/v21.0"
AUTHORIZE_URL = "https://www.instagram.com/oauth/authorize"
TOKEN_URL = "https://api.instagram.com/oauth/access_token"
SCOPES = "instagram_business_basic,instagram_business_content_publish"
MAX_ATTEMPTS = 3


class InstagramError(Exception):
    pass


def configured():
    return bool(settings.INSTAGRAM_APP_ID and settings.INSTAGRAM_APP_SECRET)


def _call(method, url, params=None, data=None, headers=None, timeout=60):
    """Make a request and return the JSON body. Instagram errors become InstagramError with its message."""
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    body = data
    if isinstance(data, dict):
        body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            err = json.loads(raw).get("error", {})
            msg = err.get("error_user_msg") or err.get("message") or raw[:300].decode("utf-8", "replace")
        except (ValueError, AttributeError):
            msg = raw[:300].decode("utf-8", "replace")
        raise InstagramError(f"Instagram said ({exc.code}): {msg}") from exc
    except urllib.error.URLError as exc:
        raise InstagramError(f"Could not reach Instagram: {exc.reason}") from exc
    return json.loads(raw) if raw else {}


# ------------------------------------------------------------------ connecting the account
def authorize_url(redirect_uri, state):
    return AUTHORIZE_URL + "?" + urllib.parse.urlencode({
        "client_id": settings.INSTAGRAM_APP_ID, "redirect_uri": redirect_uri, "response_type": "code",
        "scope": SCOPES, "state": state, "enable_fb_login": "0", "force_authentication": "1",
    })


def new_state():
    return secrets.token_urlsafe(24)


def connect(code, redirect_uri):
    """Swap the code from Instagram's login page for a 60-day token and save the account."""
    short = _call("POST", TOKEN_URL, data={
        "client_id": settings.INSTAGRAM_APP_ID, "client_secret": settings.INSTAGRAM_APP_SECRET,
        "grant_type": "authorization_code", "redirect_uri": redirect_uri, "code": code.split("#")[0],
    })
    long = _call("GET", "https://graph.instagram.com/access_token", params={
        "grant_type": "ig_exchange_token", "client_secret": settings.INSTAGRAM_APP_SECRET,
        "access_token": short["access_token"],
    })
    token = long["access_token"]
    me = _call("GET", f"{GRAPH}/me", params={"fields": "user_id,username", "access_token": token})
    InstagramAccount.objects.all().delete()
    return InstagramAccount.objects.create(
        ig_user_id=str(me.get("user_id") or me.get("id") or short.get("user_id")), username=me.get("username", ""),
        access_token=token, token_refreshed_at=timezone.now(),
        token_expires_at=timezone.now() + dt.timedelta(seconds=int(long.get("expires_in", 5184000))),
    )


def connect_with_token(token):
    """Save a token generated in the Meta app dashboard (API setup -> Generate access tokens)."""
    token = token.strip()
    me = _call("GET", f"{GRAPH}/me", params={"fields": "user_id,username", "access_token": token})
    InstagramAccount.objects.all().delete()
    return InstagramAccount.objects.create(
        ig_user_id=str(me.get("user_id") or me.get("id")), username=me.get("username", ""), access_token=token,
        token_refreshed_at=timezone.now() - dt.timedelta(days=1),  # dashboard tokens are long-lived (60 days)
        token_expires_at=timezone.now() + dt.timedelta(days=55),
    )


def refresh_if_needed(account):
    """Long-lived tokens last 60 days; refresh once they are more than a day old and within 20 days of expiry."""
    if not account.token_expires_at or account.token_expires_at - timezone.now() > dt.timedelta(days=20):
        return False
    if account.token_refreshed_at and timezone.now() - account.token_refreshed_at < dt.timedelta(days=1):
        return False
    data = _call("GET", "https://graph.instagram.com/refresh_access_token",
                 params={"grant_type": "ig_refresh_token", "access_token": account.access_token})
    account.access_token = data["access_token"]
    account.token_refreshed_at = timezone.now()
    account.token_expires_at = timezone.now() + dt.timedelta(seconds=int(data.get("expires_in", 5184000)))
    account.save(update_fields=["access_token", "token_refreshed_at", "token_expires_at"])
    return True


# ------------------------------------------------------------------ what a post needs before it can be queued
def problems(post):
    """Reasons a post can't go to Instagram yet (empty when it can)."""
    out = []
    if not post.publish_at:
        out.append("Set a date and time (Post on).")
    if post.post_type == SocialPost.TYPE_REEL and not post.assets.filter(kind=SocialAsset.KIND_VIDEO).exists():
        out.append("Upload the Reel video (MP4).")
    if post.post_type == SocialPost.TYPE_CAROUSEL and not post.assets.filter(kind=SocialAsset.KIND_SLIDE).exists():
        out.append("Add at least one more slide: a carousel needs 2 to 10 images.")
    if post.post_type in (SocialPost.TYPE_FEED, SocialPost.TYPE_CAROUSEL) and post.format == "story":
        out.append("Feed images must be Portrait, Square or Landscape: change the format, or make it a Story or Reel.")
    if post.post_type in (SocialPost.TYPE_STORY, SocialPost.TYPE_REEL) and post.format != "story":
        out.append("Stories and Reel covers use the Story format (1080 × 1920): change the format.")
    if len(post.full_caption) > 2200:
        out.append("The caption is longer than Instagram's 2,200 characters.")
    if post.hashtags.count("#") > 30:
        out.append("Instagram allows at most 30 hashtags.")
    return out


# ------------------------------------------------------------------ publishing
def _container(account, **fields):
    return _call("POST", f"{GRAPH}/{account.ig_user_id}/media", data={**fields, "access_token": account.access_token})["id"]


def _status(account, container_id):
    data = _call("GET", f"{GRAPH}/{container_id}", params={"fields": "status_code,status", "access_token": account.access_token})
    return data.get("status_code", ""), data.get("status", "")


def _wait(account, container_id, tries=4, pause=2.0):
    for _ in range(tries):
        code, detail = _status(account, container_id)
        if code in ("FINISHED", "PUBLISHED"):
            return "FINISHED", detail
        if code in ("ERROR", "EXPIRED"):
            return code, detail
        time.sleep(pause)
    return "IN_PROGRESS", ""


def _video_bytes(post):
    parts = list(post.assets.filter(kind=SocialAsset.KIND_VIDEO).order_by("order"))
    chunks = []
    for part in parts:
        with part.file.open("rb") as fh:
            chunks.append(fh.read())
    return b"".join(chunks)


def create_containers(account, post):
    caption = post.full_caption
    if post.post_type == SocialPost.TYPE_STORY:
        return _container(account, media_type="STORIES", image_url=post.ig_image_url)
    if post.post_type == SocialPost.TYPE_CAROUSEL:
        urls = [post.ig_image_url] + [a.url for a in post.assets.filter(kind=SocialAsset.KIND_SLIDE).order_by("order")][:9]
        children = []
        for url in urls:
            child = _container(account, image_url=url, is_carousel_item="true")
            code, detail = _wait(account, child)
            if code != "FINISHED":
                raise InstagramError(f"A carousel slide could not be processed ({code} {detail}).".strip())
            children.append(child)
        return _container(account, media_type="CAROUSEL", children=",".join(children), caption=caption)
    if post.post_type == SocialPost.TYPE_REEL:
        video = _video_bytes(post)
        container = _container(account, media_type="REELS", upload_type="resumable", caption=caption,
                               share_to_feed="true", cover_url=post.ig_image_url)
        _call("POST", f"https://rupload.facebook.com/ig-api-upload/v21.0/{container}", data=video, timeout=280, headers={
            "Authorization": f"OAuth {account.access_token}", "offset": "0", "file_size": str(len(video)),
        })
        return container
    return _container(account, image_url=post.ig_image_url, caption=caption)


def publish_post(account, post):
    """Move one post forward. Returns a short log line."""
    try:
        if not post.ig_container_id:
            post.ig_container_id = create_containers(account, post)
            post.ig_state = SocialPost.IG_PROCESSING
            post.save(update_fields=["ig_container_id", "ig_state", "updated_at"])
        code, detail = _wait(account, post.ig_container_id, tries=2 if post.post_type == SocialPost.TYPE_REEL else 5)
        if code == "IN_PROGRESS":
            return f"{post.pk} {post.title}: Instagram is still processing, will check again."
        if code != "FINISHED":
            raise InstagramError(f"Instagram could not process the media ({code}{': ' + detail if detail else ''}).")
        media = _call("POST", f"{GRAPH}/{account.ig_user_id}/media_publish",
                      data={"creation_id": post.ig_container_id, "access_token": account.access_token})
        post.ig_media_id = media["id"]
        try:
            link = _call("GET", f"{GRAPH}/{post.ig_media_id}", params={"fields": "permalink", "access_token": account.access_token})
            post.posted_url = link.get("permalink", "") or post.posted_url
        except InstagramError:
            pass
        post.ig_state, post.status, post.ig_error = SocialPost.IG_PUBLISHED, SocialPost.STATUS_POSTED, ""
        post.save(update_fields=["ig_media_id", "posted_url", "ig_state", "status", "ig_error", "updated_at"])
        return f"{post.pk} {post.title}: published {post.posted_url}"
    except InstagramError as exc:
        post.ig_attempts += 1
        post.ig_error = str(exc)[:500]
        if post.ig_attempts >= MAX_ATTEMPTS or "could not process" in str(exc):
            post.ig_state = SocialPost.IG_FAILED
        post.ig_container_id = "" if post.ig_state == SocialPost.IG_FAILED else post.ig_container_id
        post.save(update_fields=["ig_attempts", "ig_error", "ig_state", "ig_container_id", "updated_at"])
        return f"{post.pk} {post.title}: {exc}"


def run(max_seconds=240, now=None):
    """Publish every queued post that is due. Called by the cron endpoint."""
    account = InstagramAccount.current()
    if not account:
        return ["No Instagram account connected."]
    log = []
    started = time.monotonic()
    try:
        if refresh_if_needed(account):
            log.append("Refreshed the Instagram token.")
    except InstagramError as exc:
        log.append(f"Token refresh failed: {exc}")
    now = now or timezone.now()
    due = SocialPost.objects.filter(ig_state__in=[SocialPost.IG_QUEUED, SocialPost.IG_PROCESSING],
                                    publish_at__lte=now).order_by("publish_at")
    for post in due:
        if time.monotonic() - started > max_seconds:
            log.append("Out of time; the rest will go on the next run.")
            break
        log.append(publish_post(account, post))
    if not log:
        log.append("Nothing due.")
    account.last_run_at = timezone.now()
    account.last_run_log = "\n".join(log)[-4000:]
    account.save(update_fields=["last_run_at", "last_run_log"])
    return log
