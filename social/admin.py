import calendar
import datetime as dt
import urllib.parse
import urllib.request

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import ChoicesDropdownFilter
from unfold.decorators import action, display

from directory.models import Island

from .models import SocialPost
from .planner import generate_plan

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
    list_display = ("post", "when", "template_badge", "format", "platform_names", "status_badge", "design_link")
    list_filter = (("status", ChoicesDropdownFilter), ("template", ChoicesDropdownFilter), ("pillar", ChoicesDropdownFilter), "format")
    search_fields = ("title", "headline", "caption", "island__name", "listing__name")
    autocomplete_fields = ("island", "listing", "activity")
    date_hierarchy = "publish_at"
    actions = ["mark_ready", "mark_scheduled", "mark_posted"]
    actions_list = ["open_calendar", "open_templates", "open_playbook"]
    actions_detail = ["open_design"]
    actions_row = ["row_design"]
    fieldsets = (
        ("Plan", {"classes": ["tab"], "fields": ("title", ("status", "publish_at"), ("pillar", "platforms"), "posted_url", "notes")}),
        ("Design", {"classes": ["tab"], "fields": (("template", "format"), "eyebrow", ("headline", "accent_word"), "body",
                                                    "attribution", ("island", "listing", "activity"), "image", "image_url", "photo_credit")}),
        ("Caption", {"classes": ["tab"], "fields": ("caption", "hashtags", "link")}),
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
        post = get_object_or_404(SocialPost.objects.select_related("island", "island__atoll", "listing", "activity"), pk=pk)
        fmt = request.GET.get("format")
        if fmt in SocialPost.FORMAT_SIZES:
            post.format = fmt
        siblings = list(SocialPost.objects.filter(publish_at__isnull=False).order_by("publish_at", "id").values_list("pk", flat=True))
        idx = siblings.index(post.pk) if post.pk in siblings else -1
        return TemplateResponse(request, "admin/social/design.html", self._context(
            request, title=post.title, post=post, photo=proxied(post.photo), formats=SocialPost.FORMAT_CHOICES,
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
            samples.append({"key": key, "label": label, "help": SocialPost.TEMPLATE_HELP[key], "post": post, "photo": proxied(post.photo)})
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
