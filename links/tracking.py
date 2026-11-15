"""Remembering which tracked link brought a visitor, so a later booking request can be credited to it."""
import time

from .models import LinkLead, TrackedLink

WINDOW = 14 * 24 * 3600  # a request within 14 days of the visit counts (the session cookie lasts 2 weeks)
KEY = "ref_links"


def remember(request, link):
    refs = request.session.get(KEY) or {}
    refs[str(link.listing_id)] = [link.pk, int(time.time())]
    request.session[KEY] = refs


def credit(request, enquiry):
    """Called after a booking request is saved."""
    try:
        refs = request.session.get(KEY) or {}
        pk, at = refs.get(str(enquiry.listing_id)) or (None, 0)
        if not pk or time.time() - at > WINDOW:
            return None
        link = TrackedLink.objects.filter(pk=pk, listing_id=enquiry.listing_id).first()
        if link:
            return LinkLead.objects.get_or_create(enquiry=enquiry, defaults={"link": link})[0]
    except Exception:  # never let tracking break a booking request
        return None
