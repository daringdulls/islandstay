from django.conf import settings


def site(request):
    ctx = {
        "SITE_NAME": settings.SITE_NAME, "SHOW_PRICES": settings.SHOW_PRICES,
        "CONTACT_EMAIL": getattr(settings, "CONTACT_EMAIL", ""),
    }
    if request.user.is_authenticated:
        from .models import Enquiry

        ctx["new_enquiry_count"] = Enquiry.objects.filter(listing__owner=request.user, status=Enquiry.STATUS_NEW).count()
    return ctx
