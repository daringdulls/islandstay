"""Rebuilds the December 2026 drafts around eight islands chosen by the team: Vaavu Thinadhoo, Fuvahmulah, Maafushi,
Gulhi, Rasdhoo, Ukulhas, Kamadhoo and Fehendhoo. Keeps anything queued, published or marked Ready / Scheduled /
Posted, and the seasonal Stories (high season, Christmas, New Year's Eve)."""
import datetime as dt

from django.db import migrations

ISLANDS = ["thinadhoo-vaavu", "fuvahmulah", "maafushi", "gulhi", "rasdhoo", "ukulhas", "kamadhoo", "fehendhoo"]


def rebuild(apps, schema_editor):
    from directory.models import Island
    from social.planner import know_before_you_go_month

    if Island.objects.filter(slug__in=ISLANDS).count() < 4:
        return  # empty database (tests, new installs)
    know_before_you_go_month(dt.date(2026, 12, 1), dt.date(2026, 12, 31), only=ISLANDS)


class Migration(migrations.Migration):
    dependencies = [("social", "0013_december_moments")]
    operations = [migrations.RunPython(rebuild, migrations.RunPython.noop)]
