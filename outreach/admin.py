import datetime as dt
import urllib.parse

from django import forms
from django.contrib import admin, messages
from django.db.models import Count, Q
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from unfold.decorators import action, display

from directory.admin import BaseAdmin

from .messages import fill, island_views
from .models import HostLead, LeadMessage, OutreachMessage, OutreachPlan

STATUS_COLORS = {"to_contact": "info", "engaged": "info", "messaged": "warning", "followup1": "warning", "followup2": "warning",
                 "replied": "primary", "interested": "primary", "listed": "success", "verified": "success",
                 "no_reply": "danger", "not_interested": "danger"}


class FollowUpFilter(admin.SimpleListFilter):
    title = "follow-up"
    parameter_name = "due"

    def lookups(self, request, model_admin):
        return [("yes", "Due today or earlier"), ("week", "Due in the next 7 days")]

    def queryset(self, request, qs):
        today = timezone.localdate()
        if self.value() == "yes":
            return qs.filter(next_follow_up__lte=today)
        if self.value() == "week":
            return qs.filter(next_follow_up__gt=today, next_follow_up__lte=today + dt.timedelta(days=7))
        return qs


@admin.register(OutreachMessage)
class OutreachMessageAdmin(BaseAdmin):
    list_display = ("use", "when", "message", "sets_status", "order")
    list_editable = ("order",)
    search_fields = ("use", "text")
    fieldsets = ((None, {"fields": (("use", "when"), "text", "text_dv", ("sets_status", "order"))}),)

    class Media:
        js = ("js/outreach.js",)

    @display(description="Message")
    def message(self, obj):
        return format_html('<div class="om-text">{}</div><button type="button" class="om-copy" data-copy="{}">Copy</button>',
                           obj.text, obj.text)


def _handle(value, domain):
    """'https://www.instagram.com/coral.view/?hl=en' or 'coral.view' -> '@coral.view'."""
    v = (value or "").strip()
    if not v:
        return ""
    if domain in v:
        v = v.split(domain, 1)[1].strip("/").split("/")[0].split("?")[0]
    return "@" + v.lstrip("@")


class LeadForm(forms.ModelForm):
    class Meta:
        model = HostLead
        fields = "__all__"

    def clean_instagram(self):
        return _handle(self.cleaned_data.get("instagram"), "instagram.com/")

    def clean_tiktok(self):
        return _handle(self.cleaned_data.get("tiktok"), "tiktok.com/")

    def clean_whatsapp(self):
        v = (self.cleaned_data.get("whatsapp") or "").strip()
        digits = "".join(ch for ch in v if ch.isdigit())
        if digits and len(digits) == 7:  # a local Maldivian number: add the country code
            return f"+960 {digits[:3]} {digits[3:]}"
        return v


@admin.register(HostLead)
class HostLeadAdmin(BaseAdmin):
    form = LeadForm
    change_form_template = "admin/outreach/lead_change_form.html"
    list_display = ("business_col", "kind", "channel", "status_label", "last_contact", "follow_up_col", "links_col")
    list_display_links = ("business_col",)
    list_filter = ("status", FollowUpFilter, "channel", "kind", ("island__atoll", admin.RelatedOnlyFieldListFilter))
    search_fields = ("business", "instagram", "contact_name", "island__name", "notes")
    autocomplete_fields = ("island", "listing")
    readonly_fields = ("next_follow_up", "created_at", "updated_at")
    actions = ["mark_messaged", "mark_followup1", "mark_replied", "mark_listed", "mark_no_reply"]
    actions_row = ["row_messaged", "row_followup1", "row_replied", "row_listed"]
    actions_list = ["open_dashboard"]
    list_per_page = 50
    fieldsets = (
        ("Business", {"fields": (("business", "kind"), ("island", "contact_name"))}),
        ("How to reach them", {"fields": (("instagram", "facebook"), ("tiktok", "whatsapp"), ("channel", "found_via"))}),
        ("Progress", {"fields": ("status", ("first_contact", "last_contact", "next_follow_up"), ("date_listed", "listing"), "referred_by", "notes")}),
    )

    def get_fieldsets(self, request, obj=None):
        if obj is None:  # a new lead: keep the form short, Progress folded away
            return (self.fieldsets[0], self.fieldsets[1],
                    ("Progress", {"classes": ["collapse"], "fields": self.fieldsets[2][1]["fields"]}))
        return self.fieldsets

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        from unfold.widgets import UnfoldAdminRadioSelectWidget, UnfoldAdminTextInputWidget

        icons = {
            "business": ("storefront", "e.g. Coral View Guest House"),
            "contact_name": ("person", "Owner or manager, if you know it"),
            "instagram": ("photo_camera", "@handle, or paste their profile link"),
            "tiktok": ("music_note", "@handle, or paste their profile link"),
            "facebook": ("thumb_up", "facebook.com/their-page"),
            "whatsapp": ("chat", "+960 7xx xxxx"),
            "found_via": ("travel_explore", "e.g. #maafushi, location tag, Facebook group"),
            "referred_by": ("handshake", "Business that recommended them"),
        }
        if db_field.name in icons:
            icon, placeholder = icons[db_field.name]
            kwargs["widget"] = UnfoldAdminTextInputWidget(attrs={"prefix_icon": icon, "placeholder": placeholder})
        if db_field.name == "status":
            kwargs["widget"] = UnfoldAdminRadioSelectWidget(attrs={"class": "lead-status"})
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if field is not None and db_field.name in icons:
            field.help_text = ""
        if field is not None and db_field.name == "tiktok":
            field.label = "TikTok"
        if db_field.name == "notes" and field is not None:
            field.widget.attrs.update({"rows": 3, "placeholder": "Anything useful: what they offer, who you spoke to, what they asked"})
        if db_field.name == "status" and field is not None:
            field.help_text = ""
            field.choices = [c for c in field.choices if c[0] != ""]
        return field

    def save_model(self, request, obj, form, change):
        # Choosing a 'sent' status fills in today's dates, so the follow-up date works without typing dates.
        today = timezone.localdate()
        if obj.status in ("messaged", "followup1", "followup2") and "status" in form.changed_data:
            obj.first_contact = obj.first_contact or today
            if "last_contact" not in form.changed_data:
                obj.last_contact = today
        super().save_model(request, obj, form, change)
    list_tabs = [
        ("All", {}, None),
        ("To contact", {"status__exact": "to_contact"}, Q(status__in=["to_contact", "engaged"])),
        ("Follow-ups due", {"due": "yes"}, None),
        ("Waiting for a reply", {"status__in": "messaged,followup1,followup2"}, Q(status__in=["messaged", "followup1", "followup2"])),
        ("Replied / interested", {"status__in": "replied,interested"}, Q(status__in=["replied", "interested"])),
        ("Listed", {"status__in": "listed,verified"}, Q(status__in=["listed", "verified"])),
        ("Closed", {"status__in": "no_reply,not_interested"}, Q(status__in=["no_reply", "not_interested"])),
    ]

    class Media:
        js = ("js/outreach.js",)

    def changelist_view(self, request, extra_context=None):
        # the 'Follow-ups due' tab count needs today's date
        self.list_tabs[2] = ("Follow-ups due", {"due": "yes"}, Q(next_follow_up__lte=timezone.localdate()))
        return super().changelist_view(request, extra_context)

    @display(description="Business", ordering="business", header=True)
    def business_col(self, obj):
        return [obj.business, f"{obj.island.name}, {obj.island.atoll.name}" if obj.island else "Island not set"]

    @display(description="Status", ordering="status", label=STATUS_COLORS)
    def status_label(self, obj):
        return obj.status, obj.get_status_display()

    @display(description="Next follow-up", ordering="next_follow_up")
    def follow_up_col(self, obj):
        if not obj.next_follow_up:
            return "–"
        due = obj.next_follow_up <= timezone.localdate()
        return format_html('<span style="white-space:nowrap;{}">{}{}</span>', "color:#B9442C;font-weight:700" if due else "",
                           obj.next_follow_up.strftime("%d %b"), " · due" if due else "")

    @display(description="Open")
    def links_col(self, obj):
        links = [(u, label) for u, label in ((obj.instagram_url, "Instagram"), (obj.facebook, "Facebook"), (obj.tiktok_url, "TikTok"),
                                             (f"https://wa.me/{obj.whatsapp_number}" if obj.whatsapp_number else "", "WhatsApp")) if u]
        return format_html_join(" · ", '<a href="{}" target="_blank" rel="noopener" style="color:#0B6E8A;font-weight:600">{}</a>', links) or "–"

    # ---------------------------------------------------------------- quick updates
    def _mark(self, request, queryset, status, label):
        for lead in queryset:
            lead.mark(status)
        messages.success(request, f"{queryset.count()} lead{'s' if queryset.count() != 1 else ''} marked '{label}'.")

    @admin.action(description="Mark: messaged today")
    def mark_messaged(self, request, queryset):
        self._mark(request, queryset, "messaged", "messaged today")

    @admin.action(description="Mark: follow-up 1 sent today")
    def mark_followup1(self, request, queryset):
        self._mark(request, queryset, "followup1", "follow-up 1 sent")

    @admin.action(description="Mark: replied")
    def mark_replied(self, request, queryset):
        self._mark(request, queryset, "replied", "replied")

    @admin.action(description="Mark: listed")
    def mark_listed(self, request, queryset):
        self._mark(request, queryset, "listed", "listed")

    @admin.action(description="Mark: no reply (close)")
    def mark_no_reply(self, request, queryset):
        self._mark(request, queryset, "no_reply", "no reply")

    def _row(self, request, object_id, status, label):
        lead = get_object_or_404(HostLead, pk=object_id)
        lead.mark(status)
        messages.success(request, f"{lead.business}: {label}.")
        return redirect(request.META.get("HTTP_REFERER") or reverse("admin:outreach_hostlead_changelist"))

    @action(description="Messaged today", url_path="row-messaged")
    def row_messaged(self, request, object_id):
        return self._row(request, object_id, "messaged", "messaged today")

    @action(description="Follow-up 1 sent", url_path="row-followup1")
    def row_followup1(self, request, object_id):
        return self._row(request, object_id, "followup1", "follow-up 1 sent")

    @action(description="Replied", url_path="row-replied")
    def row_replied(self, request, object_id):
        return self._row(request, object_id, "replied", "replied")

    @action(description="Listed", url_path="row-listed")
    def row_listed(self, request, object_id):
        return self._row(request, object_id, "listed", "listed")

    @action(description="Outreach dashboard", icon="monitoring", url_path="go-dashboard")
    def open_dashboard(self, request):
        return redirect("admin:outreach_dashboard")

    # ---------------------------------------------------------------- lead page: ready-made messages
    def _island_options(self):
        import re
        from directory.models import Island
        return [{"id": i.pk, "label": f"{i.name}, {i.atoll.name}", "key": re.sub(r"[^a-z]", "", i.name.lower())}
                for i in Island.objects.filter(is_published=True).select_related("atoll")]

    def add_view(self, request, form_url="", extra_context=None):
        extra = extra_context or {}
        extra["island_options"] = self._island_options()
        return super().add_view(request, form_url, extra)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        lead = HostLead.objects.select_related("island", "listing").filter(pk=object_id).first()
        extra = extra_context or {}
        if lead:
            views = island_views(lead.island)
            text = lambda m: fill(m.text, lead, views)  # noqa: E731
            import re
            custom = {c.message_id: c.text for c in lead.custom_messages.all()}
            msgs = []
            for m in OutreachMessage.objects.all():
                t = custom.get(m.pk) or text(m)
                msgs.append({"m": m, "text": t, "custom": m.pk in custom,
                             "missing": sorted(set(re.findall(r"<[^<>]{1,40}>", t))),
                             "text_dv": fill(m.text_dv, lead, views) if m.text_dv else ""})
            extra.update(lead_msgs=msgs, lead_views=views, lead=lead)
        extra["island_options"] = self._island_options()
        return super().change_view(request, object_id, form_url, extra)

    def get_urls(self):
        view = self.admin_site.admin_view
        return [
            path("<int:pk>/sent/", view(self.sent_view), name="outreach_lead_sent"),
            path("<int:pk>/message/", view(self.custom_message_view), name="outreach_lead_message"),
            path("dashboard/", view(self.dashboard_view), name="outreach_dashboard"),
        ] + super().get_urls()

    def custom_message_view(self, request, pk):
        """Save a message rewritten for this lead (action=save), or go back to the template (action=reset)."""
        if request.method != "POST" or not self.has_change_permission(request):
            raise PermissionDenied
        lead = get_object_or_404(HostLead, pk=pk)
        m = get_object_or_404(OutreachMessage, pk=request.POST.get("message"))
        if request.POST.get("action") == "reset":
            LeadMessage.objects.filter(lead=lead, message=m).delete()
            return JsonResponse({"ok": True, "text": fill(m.text, lead, island_views(lead.island)), "custom": False})
        text = (request.POST.get("text") or "").strip()
        if not text:
            return JsonResponse({"ok": False, "error": "The message is empty."}, status=400)
        LeadMessage.objects.update_or_create(lead=lead, message=m, defaults={"text": text[:5000]})
        return JsonResponse({"ok": True, "text": text, "custom": True})

    def sent_view(self, request, pk):
        """Pressed 'Sent' under a message on the lead page: update the status and dates."""
        if request.method != "POST" or not self.has_change_permission(request):
            raise PermissionDenied
        lead = get_object_or_404(HostLead, pk=pk)
        m = get_object_or_404(OutreachMessage, pk=request.POST.get("message"))
        if m.sets_status:
            lead.mark(m.sets_status)
        else:
            lead.last_contact = timezone.localdate()
            lead.save()
        return JsonResponse({"ok": True, "status": lead.get_status_display(),
                             "next": lead.next_follow_up.strftime("%d %b") if lead.next_follow_up else ""})

    # ---------------------------------------------------------------- dashboard
    def dashboard_view(self, request):
        plan = OutreachPlan.get()
        if request.method == "POST" and self.has_change_permission(request):
            try:
                plan.start_date = dt.date.fromisoformat(request.POST.get("start_date", ""))
                plan.save()
                messages.success(request, "Plan start date saved.")
            except ValueError:
                messages.error(request, "Enter a date.")
            return redirect("admin:outreach_dashboard")
        today = timezone.localdate()
        qs = HostLead.objects.all()
        total = qs.count()
        contacted = qs.filter(status__in=HostLead.CONTACTED).count()
        replied = qs.filter(status__in=HostLead.REPLIED).count()
        listed = qs.filter(status__in=HostLead.LISTED).count()
        verified = qs.filter(status="verified").count()

        def pct(a, b):
            return f"{a / b:.0%}" if b else "–"
        funnel = [("Leads", total, ""), ("Messaged", contacted, pct(contacted, total) + " of leads"),
                  ("Replied", replied, pct(replied, contacted) + " reply rate"), ("Listed", listed, pct(listed, contacted) + " of messaged"),
                  ("Verified", verified, pct(verified, listed) + " of listed")]
        listed_t, msg_t = plan.targets("listed_targets"), plan.targets("message_targets")
        weeks = []
        for w in range(12):
            start = plan.start_date + dt.timedelta(weeks=w)
            end = start + dt.timedelta(days=7)
            actual_l = qs.filter(date_listed__lt=end).count()
            actual_m = qs.filter(first_contact__lt=end).count()
            tl = listed_t[w] if w < len(listed_t) else 0
            weeks.append({"n": w + 1, "start": start, "target_l": tl, "actual_l": actual_l, "gap": actual_l - tl,
                          "target_m": msg_t[w] if w < len(msg_t) else 0, "actual_m": actual_m,
                          "current": start <= today < end, "future": start > today})
        islands = (qs.exclude(island=None).values("island__name").annotate(
            leads=Count("id"), listed=Count("id", filter=Q(status__in=HostLead.LISTED))).order_by("-leads")[:15])
        channels = (qs.filter(status__in=HostLead.CONTACTED).values("channel").annotate(
            n=Count("id"), replied=Count("id", filter=Q(status__in=HostLead.REPLIED))).order_by("-n"))
        channel_names = dict(HostLead.CHANNEL_CHOICES)
        due = qs.filter(next_follow_up__lte=today).select_related("island").order_by("next_follow_up")[:20]
        return TemplateResponse(request, "admin/outreach/dashboard.html", {
            **self.admin_site.each_context(request), "opts": self.model._meta, "title": "Host outreach",
            "plan": plan, "funnel": funnel, "weeks": weeks, "islands": islands, "due": due, "today": today,
            "channels": [{"name": channel_names.get(c["channel"], c["channel"]), "n": c["n"], "replied": c["replied"],
                          "rate": pct(c["replied"], c["n"])} for c in channels],
            "messaged_today": qs.filter(last_contact=today).count()})
