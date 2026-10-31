"""Island Stay doesn't send email itself.

Guests send their request to the host directly (WhatsApp, Viber, email or phone) from the
confirmation page, and every request is also saved to the host's dashboard and the back office.
These hooks are kept so the places that call them stay simple; they do nothing.
"""


def enquiry_created(enquiry, request=None):
    pass


def listing_submitted(listing, request=None):
    pass


def listing_status_changed(listing):
    pass


def verification_requested(listing, request=None):
    pass
