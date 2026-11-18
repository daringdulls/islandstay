"""Replaces the drafts for 19–30 November 2026 with the 'Popular islands' series (one island a day).

Runs once. Posts already queued for or published on Instagram, or marked Ready / Scheduled / Posted, are kept.
Uses the current models on purpose: it is a one-off content update for the live site, and it does nothing on an
empty database (tests, new installs).
"""
import datetime as dt

from django.db import migrations


def add_series(apps, schema_editor):
    from directory.models import Island
    from social.models import SocialPost
    from social.planner import popular_islands_series

    if not Island.objects.exists() or SocialPost.objects.filter(title="Popular islands: the series").exists():
        return
    popular_islands_series(dt.date(2026, 11, 19))


class Migration(migrations.Migration):
    dependencies = [("social", "0010_alter_socialpost_image"), ("directory", "0030_alter_contributionphoto_image_and_more")]
    operations = [migrations.RunPython(add_series, migrations.RunPython.noop)]
