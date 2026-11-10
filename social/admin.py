import calendar
import datetime as dt
import urllib.parse
import urllib.request

from django.conf import settings
from django.contrib import admin, messages
from django.core.files.storage import default_storage
from django.db.models import Max
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import ChoicesDropdownFilter
from unfold.decorators import action, display

from directory.models import Island

from . import instagram as ig
from .models import InstagramAccount, SocialAsset, SocialPost
from .planner import generate_month, generate_plan

STATUS_COLORS = {"idea": "info", "draft": "warning", "ready": "primary", "scheduled": "info", "posted": "success"}
PROXY_HOSTS = ("upload.wikimedia.org", ".blob.vercel-storage.com")


def proxied(url):
    """Serve remote photos through the site so the design can be saved as PNG (browsers block cross-site pixels)."""
    if url and url.startswith("http"):
        return reverse("admin:social_image_proxy") + "?" + urllib.parse.urlencode({"u": url})
    return url


def sample_post(template, fmt="portrait"):
    """An unsaved post filled with real directory data, for the template gallery."""
    from .planner import FACTS, TIPS, experience_post, fact_post, host_post, island_post, tip_post
    from directory.models import ActivityType, Listing

    island = Island.objects.filter(is_published=True).order_by("-is_featured", "name").first()
    data = None
    if template == "island" and island:
        data = island_post(island)
    elif template == "experience":
        act = ActivityType.objects.exclude(image_url="").first() or ActivityType.objects.first()
        if act:
            data = experience_post(act, list(Island.objects.filter(activities=act)[:3]))
    elif template == "host":
        listing = Listing.objects.filter(status=Listing.STATUS_APPROVED).order_by("-is_verified").first()
        if listing:
            data = host_post(listing)
    elif template == "tip":
        data = tip_post(TIPS[0])
    elif template == "fact":
        data = fact_post(FACTS[1])
    if template == "quote":
        data = dict(title="Quote", pillar="hosts", template="quote", eyebrow="From a guest", headline="Guest review",
                    body="We messaged the host on Monday, and by Friday we were eating breakfast on the jetty with his family.",
                    attribution="A guest on Dhangethi")
    stay = Listing.objects.filter(status=Listing.STATUS_APPROVED, kind__in=Listing.STAY_KINDS).order_by("-is_verified", "price_from").first()
    if template == "stay" and stay:
        data = dict(title=f"Stay: {stay.name}", pillar="hosts", template="stay", listing=stay, island=stay.island,
                    eyebrow=f"Stay · {stay.island.name}, {stay.island.atoll.name}", headline=stay.name,
                    accent_word="", body=stay.short_description, attribution="Send a request")
    elif template == "toplist":
        names = list(Island.objects.filter(is_published=True).order_by("-is_featured", "name").values_list("name", flat=True)[:5])
        data = dict(title="Top five", pillar="islands", template="toplist", island=island, eyebrow="Save this list",
                    headline="Five islands for your first trip", accent_word="first",
                    body="\n".join(names or ["Maafushi", "Dhangethi", "Thoddoo", "Fulidhoo", "Ukulhas"]),
                    attribution="Swipe for each island")
    elif template == "route" and island:
        route = island.routes.filter(is_active=True).order_by("order").first()
        steps = ["Arrive | Velana International Airport (MLE)"]
        if route:
            steps.append(f"{route.get_mode_display()} | {route.duration}" + (f" · {route.schedule}" if route.schedule else ""))
        elif island.transfer_time:
            steps.append(f"Transfer | {island.transfer_time}")
        steps.append(f"Jetty | Your host meets you on {island.name}")
        data = dict(title=f"Getting to {island.name}", pillar="practical", template="route", island=island,
                    eyebrow="Getting there", headline=f"Malé to {island.name}", accent_word=island.name,
                    body="\n".join(steps), attribution="Transfer times in the island guide")
    elif template == "word":
        data = dict(title="Dhivehi word: kandu", pillar="culture", template="word", eyebrow="Dhivehi word of the week",
                    headline="Kandu", accent_word="", body="A channel through the reef: the way boats come into an atoll, and the gap in our logo.",
                    attribution="ކަނޑު")
    elif template == "compare":
        pair = list(Island.objects.filter(is_published=True).order_by("-is_featured", "name")[:2])
        if len(pair) == 2:
            data = dict(title=f"{pair[0].name} or {pair[1].name}", pillar="islands", template="compare", island=pair[0],
                        island_b=pair[1], eyebrow="This or that", headline="Which island would you pick?", accent_word="island",
                        attribution="Tell us in the comments")
    elif template == "season":
        data = dict(title="When to go", pillar="practical", template="season", eyebrow="When to go",
                    headline="The Maldives, month by month", accent_word="month",
                    body="Dec – Apr | Dry season: calm seas, clear water\nMay – Nov | Wet season: surf, quieter islands, lower prices\nJun – Nov | Manta rays gather at Hanifaru Bay\nAll year | Whale sharks in South Ari",
                    attribution="Plan with the island guides")
    elif template == "brand":
        data = dict(title="Our story", pillar="culture", template="brand", eyebrow="Why the cowrie",
                    headline="An atoll, a channel and a cowrie", accent_word="cowrie",
                    body="The ring is an atoll: atholhu, the one Dhivehi word the world borrowed.\nThe gap is the kandu, the channel boats sail through.\nThe cowrie was once money across Asia and Africa. Now it points out to you.",
                    attribution="Local to you.")
    elif template == "hostcall":
        data = dict(title="List with us", pillar="news", template="hostcall", island=island, eyebrow="For island hosts",
                    headline="Run a guest house? List it free", accent_word="free",
                    body="Guests message you directly\nNo booking fees for you or your guests\nYour island, your photos, your prices",
                    attribution="islandstaymv.com/list-your-business")
    if template == "announce" or data is None:
        data = dict(title="Announcement", pillar="news", template=template, eyebrow="New on Island Stay",
                    headline="Message a local, then book", accent_word="local", island=island,
                    body="Every inhabited island now has its own guide, with the hosts who live there.",
                    attribution="Send a request")
    data["format"] = fmt
    data.pop("hashtags", None)
    return SocialPost(**{k: v for k, v in data.items() if k in {f.name for f in SocialPost._meta.fields}})


@admin.register(SocialPost)
class SocialPostAdmin(ModelAdmin):
    compressed_fields = True
    warn_unsaved_form = True
    list_filter_submit = True
    list_per_page = 50
    list_display = ("post", "when", "post_type", "template_badge", "format", "platform_names", "status_badge", "design_link")
    list_filter = (("status", ChoicesDropdownFilter), "post_type", ("template", ChoicesDropdownFilter), ("pillar", ChoicesDropdownFilter), "format")
    search_fields = ("title", "headline", "caption", "island__name", "listing__name")
    autocomplete_fields = ("island", "listing", "activity", "island_b")
    date_hierarchy = "publish_at"
    actions = ["mark_ready", "mark_scheduled", "mark_posted"]
    actions_list = ["open_calendar", "open_feed", "open_instagram", "open_templates", "open_playbook"]
    actions_detail = ["open_design"]
    actions_row = ["row_design"]
    fieldsets = (
        ("Plan", {"classes": ["tab"], "fields": ("title", ("post_type", "status", "publish_at"), ("pillar", "platforms"), "posted_url", "notes")}),
        ("Design", {"classes": ["tab"], "fields": (("template", "format"), "eyebrow", ("headline", "accent_word"), "body",
                                                    "attribution", ("island", "listing", "activity"), "island_b", "image", "image_url", "photo_credit")}),
        ("Caption", {"classes": ["tab"], "fields": ("caption", "hashtags", "link")}),
        ("Reel / story", {"classes": ["tab"], "fields": ("script",)}),
    )

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        initial.setdefault("publish_at", timezone.now().replace(hour=18, minute=0, second=0, microsecond=0) + dt.timedelta(days=1))
        return initial

    @display(description="Post", header=True)
    def post(self, obj):
        return obj.title, obj.headline

    @display(description="Post on", ordering="publish_at")
    def when(self, obj):
        if not obj.publish_at:
            return "Not scheduled"
        local = timezone.localtime(obj.publish_at)
        return format_html('<span class="{}">{}</span>', "text-red-600" if obj.is_overdue else "", local.strftime("%a %d %b, %H:%M"))

    @display(description="Template", label=True)
    def template_badge(self, obj):
        return obj.get_template_display()

    @display(description="Platforms")
    def platform_names(self, obj):
        return ", ".join(obj.platform_list)

    @display(description="Status", label=STATUS_COLORS)
    def status_badge(self, obj):
        return obj.status, obj.get_status_display()

    @display(description="Design")
    def design_link(self, obj):
        return format_html('<a class="text-primary-600 font-semibold" href="{}">Open design</a>', obj.get_design_url())

    def _set_status(self, request, queryset, status):
        n = queryset.update(status=status)
        self.message_user(request, f"{n} post{'s' if n != 1 else ''} updated.", messages.SUCCESS)

    @admin.action(description="Mark as ready to post")
    def mark_ready(self, request, queryset):
        self._set_status(request, queryset, SocialPost.STATUS_READY)

    @admin.action(description="Mark as scheduled")
    def mark_scheduled(self, request, queryset):
        self._set_status(request, queryset, SocialPost.STATUS_SCHEDULED)

    @admin.action(description="Mark as posted")
    def mark_posted(self, request, queryset):
        self._set_status(request, queryset, SocialPost.STATUS_POSTED)

    @action(description="Calendar", icon="calendar_month", url_path="go-calendar")
    def open_calendar(self, request):
        return redirect("admin:social_calendar")

    @action(description="Feed preview", icon="grid_view", url_path="go-feed")
    def open_feed(self, request):
        return redirect("admin:social_feed")

    @action(description="Instagram", icon="photo_camera", url_path="go-instagram")
    def open_instagram(self, request):
        return redirect("admin:social_instagram")

    @action(description="Design templates", icon="palette", url_path="go-templates")
    def open_templates(self, request):
        return redirect("admin:social_templates")

    @action(description="Playbook", icon="menu_book", url_path="go-playbook")
    def open_playbook(self, request):
        return redirect("admin:social_playbook")

    @action(description="Open design", icon="image", url_path="open-design")
    def open_design(self, request, object_id):
        return redirect("admin:social_socialpost_design", object_id)

    @action(description="Design", icon="image", url_path="row-design")
    def row_design(self, request, object_id):
        return redirect("admin:social_socialpost_design", object_id)

    # ------------------------------------------------------------------ custom pages
    def get_urls(self):
        view = self.admin_site.admin_view
        return [
            path("calendar/", view(self.calendar_view), name="social_calendar"),
            path("feed/", view(self.feed_view), name="social_feed"),
            path("instagram/", view(self.instagram_view), name="social_instagram"),
            path("instagram/connect/", view(self.instagram_connect), name="social_instagram_connect"),
            path("instagram/callback/", view(self.instagram_callback), name="social_instagram_callback"),
            path("<int:pk>/instagram/queue/", view(self.instagram_queue), name="social_instagram_queue"),
            path("<int:pk>/instagram/asset/", view(self.instagram_asset), name="social_instagram_asset"),
            path("feed/swap/", view(self.feed_swap), name="social_feed_swap"),
            path("templates/", view(self.templates_view), name="social_templates"),
            path("playbook/", view(self.playbook_view), name="social_playbook"),
            path("image/", view(self.image_proxy), name="social_image_proxy"),
            path("<int:pk>/design/", view(self.design_view), name="social_socialpost_design"),
        ] + super().get_urls()

    def _context(self, request, **extra):
        return {**self.admin_site.each_context(request), "opts": self.model._meta, **extra}

    def design_view(self, request, pk):
        if not self.has_view_permission(request):
            raise PermissionDenied
        post = get_object_or_404(SocialPost.objects.select_related("island", "island__atoll", "listing", "activity", "island_b", "island_b__atoll"), pk=pk)
        fmt = request.GET.get("format")
        saved_format = post.format
        issues = ig.problems(post)
        if fmt in SocialPost.FORMAT_SIZES:
            post.format = fmt
        siblings = list(SocialPost.objects.filter(publish_at__isnull=False).order_by("publish_at", "id").values_list("pk", flat=True))
        idx = siblings.index(post.pk) if post.pk in siblings else -1
        return TemplateResponse(request, "admin/social/design.html", self._context(
            request, title=post.title, post=post, photo=proxied(post.photo), photo_b=proxied(post.photo_b), formats=SocialPost.FORMAT_CHOICES,
            ig_account=InstagramAccount.current(), ig_problems=issues,
            slides=post.assets.filter(kind=SocialAsset.KIND_SLIDE), video_parts=list(post.assets.filter(kind=SocialAsset.KIND_VIDEO)),
            video_size=sum(a.size for a in post.assets.filter(kind=SocialAsset.KIND_VIDEO)),
            format_override=bool(fmt and fmt != saved_format),
            prev_id=siblings[idx - 1] if idx > 0 else None,
            next_id=siblings[idx + 1] if 0 <= idx < len(siblings) - 1 else None,
        ))

    def templates_view(self, request):
        fmt = request.GET.get("format", "portrait")
        if fmt not in SocialPost.FORMAT_SIZES:
            fmt = "portrait"
        samples = []
        for key, label in SocialPost.TEMPLATE_CHOICES:
            post = sample_post(key, fmt)
            samples.append({"key": key, "label": label, "help": SocialPost.TEMPLATE_HELP[key], "post": post, "photo": proxied(post.photo), "photo_b": proxied(post.photo_b)})
        return TemplateResponse(request, "admin/social/templates.html", self._context(
            request, title="Design templates", samples=samples, fmt=fmt, formats=SocialPost.FORMAT_CHOICES,
            size=SocialPost.FORMAT_SIZES[fmt]))

    def calendar_view(self, request):
        today = timezone.localdate()
        try:
            year, month = (int(x) for x in request.GET.get("month", "").split("-"))
            first = dt.date(year, month, 1)
        except ValueError:
            first = today.replace(day=1)
        if request.method == "POST" and self.has_add_permission(request) and request.POST.get("plan_month"):
            try:
                y, m = (int(x) for x in request.POST["plan_month"].split("-"))
                target = dt.date(y, m, 1)
            except ValueError:
                target = first
            existing = SocialPost.objects.filter(publish_at__year=target.year, publish_at__month=target.month)
            if request.POST.get("replace"):
                removed, _ = existing.filter(status__in=[SocialPost.STATUS_IDEA, SocialPost.STATUS_DRAFT]).delete()
            if existing.exists() and not request.POST.get("replace"):
                messages.warning(request, f"{target:%B} already has {existing.count()} posts. Tick 'Replace drafts' to redo the month's drafts.")
            else:
                posts = generate_month(target.year, target.month)
                n_story = sum(p.post_type == "story" for p in posts)
                n_reel = sum(p.post_type == "reel" for p in posts)
                messages.success(request, f"Planned {target:%B}: {len(posts) - n_story - n_reel} feed posts, {n_reel} Reels and {n_story} Stories. "
                                          "Check the feed preview, drag tiles to reorder, then review each post.")
            return redirect(reverse("admin:social_calendar") + f"?month={target:%Y-%m}")
        if request.method == "POST" and self.has_add_permission(request):
            weeks = max(1, min(int(request.POST.get("weeks", 4) or 4), 12))
            start = SocialPost.objects.filter(publish_at__isnull=False).order_by("-publish_at").first()
            start_day = max(today, timezone.localdate(start.publish_at) + dt.timedelta(days=1)) if start else today
            posts = generate_plan(start=start_day, weeks=weeks)
            messages.success(request, f"Drafted {len(posts)} posts over {weeks} weeks from {posts[0].publish_at:%d %b}. Review each one, then mark it ready."
                             if posts else "Nothing to draft: add islands first.")
            target = timezone.localtime(posts[0].publish_at).date() if posts else first
            return redirect(reverse("admin:social_calendar") + f"?month={target:%Y-%m}")
        cal = calendar.Calendar(firstweekday=0)
        days = list(cal.itermonthdates(first.year, first.month))
        posts = SocialPost.objects.filter(publish_at__date__gte=days[0], publish_at__date__lte=days[-1]).order_by("publish_at")
        by_day = {}
        for p in posts:
            by_day.setdefault(timezone.localtime(p.publish_at).date(), []).append(p)
        weeks = [[{"date": d, "in_month": d.month == first.month, "today": d == today, "posts": by_day.get(d, [])} for d in days[i:i + 7]]
                 for i in range(0, len(days), 7)]
        prev_month = (first - dt.timedelta(days=1)).replace(day=1)
        next_month = (first + dt.timedelta(days=32)).replace(day=1)
        month_posts = [p for p in posts if timezone.localtime(p.publish_at).month == first.month]
        counts = {k: sum(1 for p in month_posts if p.status == k) for k, _ in SocialPost.STATUS_CHOICES}
        return TemplateResponse(request, "admin/social/calendar.html", self._context(
            request, title="Social calendar", weeks=weeks, month=first, prev_month=prev_month, next_month=next_month,
            counts=[(label, counts[k], k) for k, label in SocialPost.STATUS_CHOICES],
            unscheduled=SocialPost.objects.filter(publish_at__isnull=True).exclude(status=SocialPost.STATUS_POSTED)[:20],
            overdue=[p for p in posts if p.is_overdue and p.status != SocialPost.STATUS_SCHEDULED]))

    def feed_view(self, request):
        """A preview of the Instagram profile: the grid as it will look once the month's posts are out."""
        today = timezone.localdate()
        try:
            year, month = (int(x) for x in request.GET.get("month", "").split("-"))
            first = dt.date(year, month, 1)
        except ValueError:
            first = today.replace(day=1)
        end = (first + dt.timedelta(days=32)).replace(day=1)
        base = (SocialPost.objects.filter(platforms__contains="instagram", publish_at__isnull=False)
                .select_related("island", "island__atoll", "listing", "activity", "island_b", "island_b__atoll"))
        grid = list(base.filter(post_type__in=SocialPost.GRID_TYPES, publish_at__date__lt=end).order_by("-publish_at")[:45])
        stories = list(base.filter(post_type=SocialPost.TYPE_STORY, publish_at__date__gte=first, publish_at__date__lt=end).order_by("publish_at"))

        def tile(p):
            return {"post": p, "photo": proxied(p.photo), "photo_b": proxied(p.photo_b),
                    "in_month": first <= timezone.localtime(p.publish_at).date() < end,
                    "upcoming": p.status != SocialPost.STATUS_POSTED}
        tiles = [tile(p) for p in grid]
        # Same template side by side in a row reads as repetitive on the grid.
        for i, t in enumerate(tiles):
            t["clash"] = bool(i % 3 and tiles[i - 1]["post"].template == t["post"].template)
        month_grid = [t for t in tiles if t["in_month"]]
        return TemplateResponse(request, "admin/social/feed.html", self._context(
            request, title="Instagram feed preview", month=first,
            highlights=[("Islands", "map-pin"), ("Stays", "house"), ("Getting there", "route"), ("Tips", "info"), ("Dhivehi", "book-open"), ("Hosts", "heart-handshake")], tiles=tiles, stories=[tile(p) for p in stories],
            reels=[t for t in tiles if t["post"].post_type == SocialPost.TYPE_REEL],
            prev_month=(first - dt.timedelta(days=1)).replace(day=1), next_month=end,
            n_month=len(month_grid), n_reels=sum(t["post"].post_type == "reel" for t in month_grid),
            n_carousels=sum(t["post"].post_type == "carousel" for t in month_grid),
            n_total=SocialPost.objects.filter(platforms__contains="instagram", post_type__in=SocialPost.GRID_TYPES,
                                              status=SocialPost.STATUS_POSTED).count(),
            clashes=sum(t["clash"] for t in tiles if t["in_month"])))

    # ------------------------------------------------------------------ Instagram publishing
    def _callback_url(self, request):
        url = reverse("admin:social_instagram_callback")
        host = settings.CANONICAL_HOST
        return f"https://{host}{url}" if host else request.build_absolute_uri(url)

    def _public_url(self, request, name):
        url = default_storage.url(name)
        if url.startswith("http"):
            return url
        host = settings.CANONICAL_HOST
        return f"https://{host}{url}" if host else request.build_absolute_uri(url)

    def instagram_view(self, request):
        if not self.has_view_permission(request):
            raise PermissionDenied
        account = InstagramAccount.current()
        if request.method == "POST" and self.has_change_permission(request):
            if request.POST.get("disconnect"):
                InstagramAccount.objects.all().delete()
                messages.success(request, "Instagram disconnected. Queued posts stay queued until you connect again.")
            elif request.POST.get("run"):
                log = ig.run(max_seconds=200)
                messages.info(request, " · ".join(log)[:600])
            return redirect("admin:social_instagram")
        queue = (SocialPost.objects.exclude(ig_state="").exclude(ig_state=SocialPost.IG_PUBLISHED).order_by("publish_at"))
        published = SocialPost.objects.filter(ig_state=SocialPost.IG_PUBLISHED).order_by("-publish_at")[:10]
        cron_path = reverse("social_cron_instagram")
        host = settings.CANONICAL_HOST
        cron_url = f"https://{host}{cron_path}" if host else request.build_absolute_uri(cron_path)
        return TemplateResponse(request, "admin/social/instagram.html", self._context(
            request, title="Instagram publishing", account=account, configured=ig.configured(),
            callback_url=self._callback_url(request), cron_url=cron_url, has_cron_secret=bool(settings.CRON_SECRET),
            cron_secret=settings.CRON_SECRET if request.user.is_superuser else "", queue=queue, published=published,
            now=timezone.now()))

    def instagram_connect(self, request):
        if not self.has_change_permission(request):
            raise PermissionDenied
        if not ig.configured():
            messages.error(request, "Add INSTAGRAM_APP_ID and INSTAGRAM_APP_SECRET in Vercel first.")
            return redirect("admin:social_instagram")
        state = ig.new_state()
        request.session["ig_state"] = state
        return redirect(ig.authorize_url(self._callback_url(request), state))

    def instagram_callback(self, request):
        if not self.has_change_permission(request):
            raise PermissionDenied
        if request.GET.get("error"):
            messages.error(request, "Instagram didn't connect: " + (request.GET.get("error_description") or request.GET["error"]))
        elif not request.GET.get("state") or request.GET.get("state") != request.session.pop("ig_state", None):
            messages.error(request, "That Instagram sign-in link expired. Press Connect Instagram again.")
        else:
            try:
                account = ig.connect(request.GET.get("code", ""), self._callback_url(request))
                messages.success(request, f"Connected {account}. Posts you schedule will now publish by themselves.")
            except (ig.InstagramError, KeyError) as exc:
                messages.error(request, f"Couldn't connect Instagram: {exc}")
        return redirect("admin:social_instagram")

    def instagram_queue(self, request, pk):
        """POST image=<jpeg>: save the rendered design and queue the post. POST action=cancel: take it off the queue."""
        if request.method != "POST" or not self.has_change_permission(request):
            raise PermissionDenied
        post = get_object_or_404(SocialPost, pk=pk)
        if post.ig_state in (SocialPost.IG_PROCESSING, SocialPost.IG_PUBLISHED):
            return JsonResponse({"ok": False, "error": "This post is already with Instagram."}, status=400)
        if request.POST.get("action") == "cancel":
            post.ig_state, post.ig_error = "", ""
            if post.status == SocialPost.STATUS_SCHEDULED:
                post.status = SocialPost.STATUS_READY
            post.save(update_fields=["ig_state", "ig_error", "status", "updated_at"])
            return JsonResponse({"ok": True})
        issues = ig.problems(post)
        if issues:
            return JsonResponse({"ok": False, "error": " ".join(issues)}, status=400)
        image = request.FILES.get("image")
        if not image or image.size > 4_200_000:
            return JsonResponse({"ok": False, "error": "The design image didn't arrive. Try again."}, status=400)
        image.content_type = "image/jpeg"
        name = default_storage.save(f"social/ig/{post.pk}-{post.format}.jpg", image)
        post.ig_image_url = self._public_url(request, name)
        post.ig_state, post.ig_error, post.ig_attempts, post.ig_container_id = SocialPost.IG_QUEUED, "", 0, ""
        post.status = SocialPost.STATUS_SCHEDULED
        post.save()
        return JsonResponse({"ok": True, "when": timezone.localtime(post.publish_at).strftime("%a %d %b, %H:%M")})

    def instagram_asset(self, request, pk):
        """Upload a carousel slide, or one part of a Reel video; or delete one (action=delete)."""
        if request.method != "POST" or not self.has_change_permission(request):
            raise PermissionDenied
        post = get_object_or_404(SocialPost, pk=pk)
        if request.POST.get("action") == "delete":
            post.assets.filter(pk=request.POST.get("id")).delete()
            return JsonResponse({"ok": True})
        if request.POST.get("action") == "clear-video":
            post.assets.filter(kind=SocialAsset.KIND_VIDEO).delete()
            return JsonResponse({"ok": True})
        f = request.FILES.get("file")
        kind = request.POST.get("kind")
        if not f or kind not in (SocialAsset.KIND_SLIDE, SocialAsset.KIND_VIDEO) or f.size > 4_200_000:
            return JsonResponse({"ok": False, "error": "Upload failed. Try again."}, status=400)
        if kind == SocialAsset.KIND_SLIDE:
            if post.assets.filter(kind=kind).count() >= 9:
                return JsonResponse({"ok": False, "error": "A carousel holds 10 images: the design plus 9 slides."}, status=400)
            f.content_type = "image/jpeg"
            order = (post.assets.filter(kind=kind).aggregate(m=Max("order"))["m"] or 0) + 1
            name = default_storage.save(f"social/assets/{post.pk}-slide.jpg", f)
            a = SocialAsset.objects.create(post=post, kind=kind, file=name, url=self._public_url(request, name),
                                           name=request.POST.get("name", "")[:120], order=order, size=f.size)
            return JsonResponse({"ok": True, "id": a.pk, "url": a.url})
        part = int(request.POST.get("part", 0))
        if part == 0:
            post.assets.filter(kind=kind).delete()
        f.content_type = "application/octet-stream"
        name = default_storage.save(f"social/assets/{post.pk}-video-{part:03d}.part", f)
        SocialAsset.objects.create(post=post, kind=kind, file=name, name=request.POST.get("name", "")[:120], order=part, size=f.size)
        return JsonResponse({"ok": True})

    def feed_swap(self, request):
        """Swap the dates of two posts, so dragging a tile in the feed preview moves it in the schedule."""
        if request.method != "POST" or not self.has_change_permission(request):
            raise PermissionDenied
        try:
            a, b = (SocialPost.objects.get(pk=int(request.POST[k])) for k in ("a", "b"))
        except (KeyError, ValueError, SocialPost.DoesNotExist):
            raise Http404
        if SocialPost.STATUS_POSTED in (a.status, b.status):
            return JsonResponse({"ok": False, "error": "Posted posts can't be moved."}, status=400)
        a.publish_at, b.publish_at = b.publish_at, a.publish_at
        a.save(update_fields=["publish_at", "updated_at"])
        b.save(update_fields=["publish_at", "updated_at"])
        return JsonResponse({"ok": True})

    def playbook_view(self, request):
        return TemplateResponse(request, "admin/social/playbook.html", self._context(
            request, title="Social media playbook", templates=[(k, l, SocialPost.TEMPLATE_HELP[k]) for k, l in SocialPost.TEMPLATE_CHOICES]))

    def image_proxy(self, request):
        url = request.GET.get("u", "")
        host = urllib.parse.urlparse(url).hostname or ""
        if not url.startswith("https://") or not any(host == h or (h.startswith(".") and host.endswith(h)) for h in PROXY_HOSTS):
            raise Http404
        req = urllib.request.Request(url, headers={"User-Agent": "IslandStay/1.0 (social design export)"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data, ctype = r.read(), r.headers.get("content-type", "image/jpeg")
        except Exception:
            raise Http404
        if not ctype.startswith("image/"):
            raise Http404
        resp = HttpResponse(data, content_type=ctype)
        resp["Cache-Control"] = "private, max-age=86400"
        return resp
