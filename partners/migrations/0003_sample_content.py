from django.db import migrations


def add(apps, schema_editor):
    from partners.samples import create_samples
    Island = apps.get_model("directory", "Island")
    if not Island.objects.exists():
        return  # empty database (tests, new installs)
    create_samples(apps.get_model("partners", "Sponsor"), apps.get_model("partners", "Placement"),
                   apps.get_model("partners", "AffiliateOffer"), Island)


class Migration(migrations.Migration):
    dependencies = [("partners", "0002_samples"), ("directory", "0029_home_banner")]
    operations = [migrations.RunPython(add, migrations.RunPython.noop)]
