"""WSGI entry point. On serverless hosts (Vercel) it also prepares the database on each cold start."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()

if os.environ.get("VERCEL") == "1":
    from config import startup

    startup.run()

app = application  # some serverless runtimes look for `app`
