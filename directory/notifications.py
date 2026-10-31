"""Outgoing emails. Every booking request goes straight to the property / service owner."""
import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

log = logging.getLogger(__name__)
NOT_CONFIGURED = "Not sent: email isn't set up (see Settings, Email in the back office)"


def deliver(message):
    """Send one email. Returns None when it went out, or a short reason when it didn't."""
    if not getattr(settings, "EMAIL_CONFIGURED", False):
        log.warning("Email not configured; not delivered: %s -> %s", message.subject, message.to)
        message.send(fail_silently=True)  # still written to the log by the console backend
        return NOT_CONFIGURED
    try:
        message.send()
        return None
    except Exception as exc:  # network, login or provider errors
        log.exception("Email failed: %s -> %s", message.subject, message.to)
        return f"Failed: {type(exc).__name__}: {exc}"[:240]


def send_mail(subject, body, from_email, to, fail_silently=True):
    return deliver(EmailMessage(subject=subject, body=body, from_email=from_email, to=to))


def _abs(request, path):
    return request.build_absolute_uri(path) if request else path


def enquiry_created(enquiry, request=None):
    listing = enquiry.listing
    ctx = {
        "e": enquiry, "listing": listing, "site_name": settings.SITE_NAME,
        "dashboard_url": _abs(request, f"/dashboard/enquiries/{enquiry.reference}/"),
        "listing_url": _abs(request, listing.get_absolute_url()),
    }
    # To the owner, with Reply-To set to the guest so they can answer directly.
    owner_error = deliver(EmailMessage(
        subject=f"New booking request {enquiry.reference} — {listing.name}",
        body=render_to_string("emails/enquiry_owner.txt", ctx),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[listing.contact_email],
        reply_to=[enquiry.guest_email],
    ))
    # Confirmation to the guest, with Reply-To set to the owner.
    guest_error = deliver(EmailMessage(
        subject=f"Your request to {listing.name} was sent ({enquiry.reference})",
        body=render_to_string("emails/enquiry_guest.txt", ctx),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[enquiry.guest_email],
        reply_to=[listing.contact_email],
    ))
    if owner_error:
        status = f"Owner: {owner_error}"
    elif guest_error:
        status = f"Sent to owner ({listing.contact_email}). Guest copy: {guest_error}"
    else:
        status = f"Sent to owner ({listing.contact_email}) and guest"
    type(enquiry).objects.filter(pk=enquiry.pk).update(email_status=status[:255])
    enquiry.email_status = status[:255]


def listing_submitted(listing, request=None):
    if not settings.ADMIN_NOTIFY_EMAILS:
        return
    send_mail(
        f"New listing awaiting review: {listing.name} ({listing.island.name})",
        f"{listing.owner.get_full_name() or listing.owner.email} submitted '{listing.name}' "
        f"({listing.get_kind_display()}) on {listing.island}.\n\nReview: {_abs(request, f'/admin/directory/listing/{listing.pk}/change/')}",
        settings.DEFAULT_FROM_EMAIL,
        settings.ADMIN_NOTIFY_EMAILS,
        fail_silently=True,
    )


def listing_status_changed(listing):
    owner_email = listing.owner.email or listing.contact_email
    if listing.status == listing.STATUS_APPROVED:
        subject = f"{listing.name} is now live on {settings.SITE_NAME}"
        body = f"Good news! Your listing '{listing.name}' on {listing.island.name} has been approved and is now visible to travellers.\n\nBooking requests will be emailed to {listing.contact_email} and appear in your dashboard."
    elif listing.status == listing.STATUS_REJECTED:
        subject = f"Your listing {listing.name} needs changes"
        body = f"Your listing '{listing.name}' was not approved yet.\n\nNote from our team:\n{listing.admin_note or '(no note)'}\n\nYou can edit it from your dashboard and it will be re-submitted for review."
    else:
        return
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [owner_email], fail_silently=True)


def verification_requested(listing, request=None):
    if not settings.ADMIN_NOTIFY_EMAILS:
        return
    send_mail(
        f"Verification requested: {listing.name} ({listing.island.name})",
        f"Licence no. {listing.registration_number}. Review the document: "
        f"{_abs(request, f'/admin/directory/listing/{listing.pk}/change/')}",
        settings.DEFAULT_FROM_EMAIL, settings.ADMIN_NOTIFY_EMAILS, fail_silently=True,
    )
