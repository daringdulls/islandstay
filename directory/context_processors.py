from django.conf import settings


def site(request):
    ctx = {"SITE_NAME": settings.SITE_NAME}
    if request.user.is_authenticated:
        from .models import Enquiry

        ctx["new_enquiry_count"] = Enquiry.objects.filter(listing__owner=request.user, status=Enquiry.STATUS_NEW).count()
    return ctx
