"""Partner programme rules: approving partners (which gives them a link) and recording commissions."""
from django.utils.text import slugify

from .models import Commission, Programme, TrackedLink


def _short(slug, n):
    """Cut a slug to n characters without breaking a word: 'ari-reef-view-guest-house' -> 'ari-reef-view-guest'."""
    if len(slug) <= n:
        return slug
    cut = slug[:n + 1].rsplit("-", 1)[0]
    return cut if len(cut) >= 4 else slug[:n].strip("-")


def link_code(listing, partner):
    base = f"{_short(slugify(listing.name), 20)}-{_short(slugify(partner.name), 16) or 'partner'}"
    code, n = base, 2
    while TrackedLink.objects.filter(code=code).exists():
        code, n = f"{base}-{n}", n + 1
    return code


def activate(membership):
    """Approve a partner: they get (or get back) their personal link."""
    listing = membership.programme.listing
    if not membership.link:
        membership.link = TrackedLink.objects.create(listing=listing, code=link_code(listing, membership.partner),
                                                     label=f"Partner: {membership.partner.name}", channel="partner")
    else:
        TrackedLink.objects.filter(pk=membership.link_id).update(is_active=True)
    membership.status = "active"
    membership.save()
    return membership


def set_status(membership, status):
    if status == "active":
        return activate(membership)
    membership.status = status
    membership.save(update_fields=["status"])
    if membership.link_id:
        TrackedLink.objects.filter(pk=membership.link_id).update(is_active=False)
    return membership


def partner_membership(enquiry):
    """The partner membership a booking request was credited to, if any."""
    lead = getattr(enquiry, "tracked_lead", None)
    return getattr(lead.link, "membership", None) if lead else None


def record_booking(enquiry, value=None, nights=None):
    """The property confirms the booking and its value: the commission starts as Pending."""
    membership = partner_membership(enquiry)
    if not membership:
        raise ValueError("This request didn't come through a partner link.")
    if Commission.objects.filter(enquiry=enquiry).exists():
        raise ValueError("A commission is already recorded for this booking.")
    programme = membership.programme
    nights = nights or enquiry.nights
    if programme.commission_type == Programme.TYPE_PERCENT and not value:
        raise ValueError("Enter the booking value to work out the commission.")
    return Commission.objects.create(membership=membership, enquiry=enquiry, booking_value=value or None, nights=nights,
                                     amount=programme.commission_for(value, nights), currency=programme.currency)
