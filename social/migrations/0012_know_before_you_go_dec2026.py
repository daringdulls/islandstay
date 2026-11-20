"""Drafts December 2026: the 'Know before you go' month (routes, before-you-pack tips, late landings, island by
mood, hosts, two Reels a week). Runs once; keeps anything queued, published or marked Ready / Scheduled / Posted.
Uses the current models on purpose: a one-off content update that does nothing on an empty database."""
import datetime as dt

from django.db import migrations


def add_month(apps, schema_editor):
    from directory.models import Island
    from social.models import SocialPost
    from social.planner import know_before_you_go_month

    if not Island.objects.exists() or SocialPost.objects.filter(title="Tip: Landing after 6 pm?").exists():
        return
    know_before_you_go_month(dt.date(2026, 12, 1), dt.date(2026, 12, 31))


class Migration(migrations.Migration):
    dependencies = [("social", "0011_popular_islands_nov2026"), ("directory", "0033_route_timing_from_schedule")]
    operations = [migrations.RunPython(add_month, migrations.RunPython.noop)]
