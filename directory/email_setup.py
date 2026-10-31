"""Back-office page: is email set up, and a button to send a test message."""
from django.conf import settings
from django.contrib import admin, messages
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.shortcuts import redirect
from django.template.response import TemplateResponse

from . import notifications


def email_setup(request):
    if not request.user.is_staff:
        return redirect("admin:login")
    if request.method == "POST":
        to = request.POST.get("to", "").strip()
        try:
            validate_email(to)
        except Exception:
            messages.error(request, "Enter a valid email address to send the test to.")
            return redirect("email_setup")
        error = notifications.deliver(EmailMessage(
            subject="Island Stay test email",
            body="This is a test from the Island Stay back office. If you can read this, booking request emails are working.",
            from_email=settings.DEFAULT_FROM_EMAIL, to=[to]))
        if error:
            messages.error(request, error)
        else:
            messages.success(request, f"Test email sent to {to}. Check the inbox and the spam folder.")
        return redirect("email_setup")
    user = settings.EMAIL_HOST_USER
    masked = (user[:2] + "…" + user[user.index("@"):]) if "@" in user else (user[:3] + "…" if user else "")
    return TemplateResponse(request, "admin/email_setup.html", {
        **admin.site.each_context(request), "title": "Email",
        "configured": settings.EMAIL_CONFIGURED, "host": settings.EMAIL_HOST, "port": settings.EMAIL_PORT,
        "user": masked, "has_password": bool(settings.EMAIL_HOST_PASSWORD), "from_email": settings.DEFAULT_FROM_EMAIL,
        "admin_emails": settings.ADMIN_NOTIFY_EMAILS,
    })
