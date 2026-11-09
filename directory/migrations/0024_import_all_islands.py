"""Add every inhabited island of the Maldives (see directory/island_import.py)."""
from django.db import migrations


def run(apps, schema_editor):
    from directory.island_import import import_islands
    Island, Atoll = apps.get_model("directory", "Island"), apps.get_model("directory", "Atoll")
    if not Atoll.objects.exists():
        return  # empty database (tests): the seed command adds atolls later
    import_islands(Island, Atoll, log=lambda *a: None)


class Migration(migrations.Migration):
    dependencies = [("directory", "0023_shops_and_island_checks")]
    operations = [migrations.RunPython(run, migrations.RunPython.noop)]
