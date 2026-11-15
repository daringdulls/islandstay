"""Partner programme pages: the property's Partners page, the public 'Become a partner' page, partner sign-up
and the partner's own dashboard."""
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from directory.models import Enquiry

from . import programme as rules
from .forms import InviteForm, PartnerProfileForm, PartnerSignupForm, ProgrammeForm
from .models import Commission, LinkPlan, Membership, Partner, Programme
from .views import _full, _own


def _plan_live(listing):
    plan = LinkPlan.objects.filter(listing=listing).first()
    return plan, bool(plan and plan.is_live)


def open_programmes():
    today = timezone.localdate()
    return (Programme.objects.filter(is_active=True, joining=Programme.JOIN_OPEN, listing__status="approved",
                                     listing__link_plan__is_active=True, listing__link_plan__starts__lte=today)
            .filter(Q(listing__link_plan__ends__isnull=True) | Q(listing__link_plan__ends__gte=today))
            .select_related("listing", "listing__island").order_by("listing__name"))


# ------------------------------------------------------------------ property side
@login_required
def manage(request, pk):
    listing = _own(request, pk)
    plan, live = _plan_live(listing)
    if not live:
        return redirect("links:manage", pk=listing.pk)  # the Pro offer page
    prog = Programme.objects.filter(listing=listing).first()
    form = ProgrammeForm(request.POST if request.POST.get("action") == "settings" else None, instance=prog)
    invite = InviteForm(request.POST if request.POST.get("action") == "invite" else None)
    here = reverse("links:partners", args=[listing.pk])

    if request.method == "POST":
        action = request.POST.get("action")
        back = request.POST.get("next") if (request.POST.get("next") or "").startswith("/dashboard/") else here
        if action == "settings" and form.is_valid():
            p = form.save(commit=False)
            p.listing = listing
            p.save()
            messages.success(request, "Partner programme saved.")
            return redirect(here)
        if prog and action == "invite" and invite.is_valid():
            from accounts.invites import invite_link, owner_for_email

            user, created = owner_for_email(invite.cleaned_data["email"])
            partner, _ = Partner.objects.get_or_create(user=user, defaults={"name": invite.cleaned_data["name"]})
            m, _ = Membership.objects.get_or_create(programme=prog, partner=partner)
            rules.activate(m)
            request.session["partner_invite"] = {
                "name": partner.name, "url": _full(request, m.link),
                "invite": invite_link(user, request) if not user.has_usable_password() else "",
            }
            return redirect(here + "#invite")
        if prog and action in ("approve", "decline", "pause", "resume"):
            m = get_object_or_404(Membership, pk=request.POST.get("id"), programme=prog)
            rules.set_status(m, {"approve": "active", "resume": "active", "decline": "declined", "pause": "paused"}[action])
            messages.success(request, f"{m.partner.name}: {m.get_status_display().lower()}.")
            return redirect(here)
        if action == "record":
            e = get_object_or_404(Enquiry, reference=request.POST.get("ref"), listing=listing)
            try:
                value = Decimal(request.POST.get("value") or 0) or None
                nights = int(request.POST.get("nights") or 0) or None
                c = rules.record_booking(e, value, nights)
                messages.success(request, f"Booking recorded. Commission of {c.currency} {c.amount} is pending until the stay is over.")
            except (InvalidOperation, ValueError) as err:
                messages.error(request, str(err) or "Check the booking value.")
            return redirect(back)
        if action in ("c_approve", "c_reject", "c_paid"):
            c = get_object_or_404(Commission, pk=request.POST.get("id"), membership__programme__listing=listing)
            if action == "c_approve" and c.status == Commission.PENDING:
                c.status = Commission.APPROVED
            elif action == "c_reject" and c.status in (Commission.PENDING, Commission.APPROVED):
                c.status, c.note = Commission.REJECTED, (request.POST.get("note") or "")[:200]
            elif action == "c_paid" and c.status in (Commission.PENDING, Commission.APPROVED):
                c.status, c.paid_at = Commission.PAID, timezone.now()
                c.paid_reference = (request.POST.get("reference") or "")[:80]
            c.save()
            return redirect(back)

    ctx = {"listing": listing, "plan": plan, "prog": prog, "form": form, "invite": invite,
           "sent": request.session.pop("partner_invite", None)}
    if prog:
        ms = list(prog.memberships.select_related("partner", "link").annotate(n_leads=Count("link__leads", distinct=True)))
        sums = {row["membership"]: row for row in Commission.objects.filter(membership__programme=prog).values("membership").annotate(
            n_booked=Count("id", filter=~Q(status=Commission.REJECTED)),
            owed=Sum("amount", filter=Q(status__in=[Commission.PENDING, Commission.APPROVED])),
            paid=Sum("amount", filter=Q(status=Commission.PAID)))}
        for m in ms:
            m.url = _full(request, m.link) if m.link else ""
            row = sums.get(m.pk, {})
            m.n_booked, m.owed, m.paid = row.get("n_booked", 0), row.get("owed") or 0, row.get("paid") or 0
        ctx["applications"] = [m for m in ms if m.status == "applied"]
        ctx["partners"] = [m for m in ms if m.status in ("active", "paused")]
        comms = Commission.objects.filter(membership__programme=prog).select_related("enquiry", "membership__partner")
        ctx["awaiting"] = (Enquiry.objects.filter(listing=listing, tracked_lead__link__membership__programme=prog, commission__isnull=True)
                           .exclude(status="declined").select_related("tracked_lead__link__membership__partner").order_by("-created_at")[:20])
        ctx["open_comms"] = comms.filter(status__in=[Commission.PENDING, Commission.APPROVED])
        ctx["done_comms"] = comms.filter(status__in=[Commission.PAID, Commission.REJECTED])[:15]
        totals = comms.aggregate(owed=Sum("amount", filter=Q(status=Commission.APPROVED)), pending=Sum("amount", filter=Q(status=Commission.PENDING)),
                                 paid=Sum("amount", filter=Q(status=Commission.PAID)))
        ctx["totals"] = {k: v or 0 for k, v in totals.items()}
        ctx["n_active"] = sum(1 for m in ms if m.status == "active")
        ctx["join_url"] = request.build_absolute_uri(reverse("links:partner_landing")) + f"#p-{prog.pk}"
    return render(request, "links/partners_manage.html", ctx)


# ------------------------------------------------------------------ public and partner side
def landing(request):
    partner = getattr(request.user, "partner", None) if request.user.is_authenticated else None
    joined = set(partner.memberships.values_list("programme_id", flat=True)) if partner else set()
    return render(request, "links/partner_landing.html", {"programmes": open_programmes(), "partner": partner, "joined": joined})


def join(request):
    if request.user.is_authenticated:
        if hasattr(request.user, "partner"):
            return redirect("links:partner_dashboard")
        form = PartnerProfileForm(request.POST or None, initial={"name": request.user.get_full_name()})
        if request.method == "POST" and form.is_valid():
            p = form.save(commit=False)
            p.user = request.user
            p.save()
            messages.success(request, "You're a partner now. Pick properties to promote below.")
            return redirect("links:partner_dashboard")
    else:
        form = PartnerSignupForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            partner = form.save()
            login(request, partner.user, backend="accounts.backends.CaseInsensitiveEmailBackend")
            messages.success(request, "Welcome! Pick properties to promote below.")
            return redirect("links:partner_dashboard")
    return render(request, "links/partner_join.html", {"form": form})


@login_required
def dashboard(request):
    partner = getattr(request.user, "partner", None)
    if not partner:
        return redirect("links:partner_join")
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "apply":
            prog = get_object_or_404(open_programmes(), pk=request.POST.get("programme"))
            m, created = Membership.objects.get_or_create(programme=prog, partner=partner,
                                                          defaults={"message": (request.POST.get("message") or "")[:1000]})
            messages.success(request, f"Applied to {prog.listing.name}. You'll get your link as soon as they approve you."
                             if created else "You've already applied to this property.")
        elif action == "received":
            c = get_object_or_404(Commission, pk=request.POST.get("id"), membership__partner=partner, status=Commission.PAID)
            c.received_at = timezone.now()
            c.save(update_fields=["received_at"])
        return redirect("links:partner_dashboard")

    ms = list(partner.memberships.select_related("programme__listing", "programme__listing__island", "link").annotate(
        n_leads=Count("link__leads", distinct=True)))
    for m in ms:
        m.url = _full(request, m.link) if m.link else ""
    comms = Commission.objects.filter(membership__partner=partner).select_related("enquiry", "membership__programme__listing")
    totals = comms.aggregate(pending=Sum("amount", filter=Q(status=Commission.PENDING)), owed=Sum("amount", filter=Q(status=Commission.APPROVED)),
                             paid=Sum("amount", filter=Q(status=Commission.PAID)))
    joined = {m.programme_id for m in ms}
    currencies = set(comms.values_list("currency", flat=True)) or {m.programme.currency for m in ms} or {"USD"}
    return render(request, "links/partner_dashboard.html", {
        "partner": partner, "active": [m for m in ms if m.status == "active"], "waiting": [m for m in ms if m.status == "applied"],
        "inactive": [m for m in ms if m.status in ("paused", "declined")], "comms": comms[:50],
        "totals": {k: v or 0 for k, v in totals.items()}, "due": (totals["pending"] or 0) + (totals["owed"] or 0), "more": [p for p in open_programmes() if p.pk not in joined][:12],
        "visits": sum((m.link.clicks if m.link else 0) for m in ms), "leads": sum(m.n_leads for m in ms),
        "cur": " / ".join(sorted(currencies)) if len(currencies) > 1 else next(iter(currencies)),
    })


@login_required
def profile(request):
    partner = getattr(request.user, "partner", None)
    if not partner:
        return redirect("links:partner_join")
    form = PartnerProfileForm(request.POST or None, instance=partner)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile saved.")
        return redirect("links:partner_dashboard")
    return render(request, "links/partner_join.html", {"form": form, "editing": True})
