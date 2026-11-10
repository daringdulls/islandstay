from django.conf import settings
from django.http import HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def cron_instagram(request):
    """Publish queued Instagram posts that are due. Call every 5-10 minutes from cron-job.org or Vercel Cron,
    with the header Authorization: Bearer CRON_SECRET, or ?key=CRON_SECRET."""
    from .instagram import run

    secret = settings.CRON_SECRET
    given = request.headers.get("Authorization", "").removeprefix("Bearer ").strip() or request.GET.get("key", "")
    if not secret or given != secret:
        return HttpResponseForbidden("Forbidden")
    return JsonResponse({"log": run()})
