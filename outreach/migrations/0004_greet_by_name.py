from django.db import migrations


def greet(apps, schema_editor):
    Message = apps.get_model("outreach", "OutreachMessage")
    for m in Message.objects.filter(text__startswith="Hello <business> team! We love your photos of <something specific>"):
        m.text = m.text.replace("Hello <business> team! We love your photos of <something specific>",
                                "Hello <name>! We love <something specific>", 1)
        m.save(update_fields=["text"])


class Migration(migrations.Migration):
    dependencies = [("outreach", "0003_lead_messages")]
    operations = [migrations.RunPython(greet, migrations.RunPython.noop)]
