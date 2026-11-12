from django.db import migrations


def add(apps, schema_editor):
    from outreach.messages import DEFAULT_MESSAGES
    Message = apps.get_model("outreach", "OutreachMessage")
    if Message.objects.exists():
        return
    for i, (use, when, status, text) in enumerate(DEFAULT_MESSAGES):
        Message.objects.create(use=use, when=when, sets_status=status, text=text, order=i)


class Migration(migrations.Migration):
    dependencies = [("outreach", "0001_initial")]
    operations = [migrations.RunPython(add, migrations.RunPython.noop)]
