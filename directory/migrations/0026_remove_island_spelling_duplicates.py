"""Remove islands the import added twice under another spelling (e.g. Maduvvari / Maduvvaree)."""
from django.db import migrations


def run(apps, schema_editor):
    from directory.island_import import remove_spelling_duplicates
    remove_spelling_duplicates(apps.get_model("directory", "Island"), log=lambda *a: None)


class Migration(migrations.Migration):
    dependencies = [("directory", "0025_shops_banner")]
    operations = [migrations.RunPython(run, migrations.RunPython.noop)]
