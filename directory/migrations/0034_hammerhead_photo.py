"""The hammerhead dive photo showed dead sharks at a fish market. Clear it and search for a living shark instead;
the daily photo job fills it in again."""
from django.db import migrations


def fix(apps, schema_editor):
    A = apps.get_model("directory", "ActivityType")
    A.objects.filter(slug="hammerhead-dive", image_url__icontains="Sphyrna_lewini_01").update(
        image_url="", image_credit="", image_license="", image_source_url="")
    A.objects.filter(slug="hammerhead-dive").update(photo_search="Scalloped hammerhead shark underwater")


class Migration(migrations.Migration):
    dependencies = [("directory", "0033_route_timing_from_schedule")]
    operations = [migrations.RunPython(fix, migrations.RunPython.noop)]
