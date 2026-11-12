"""Replace the first DM and the two follow-ups with the professional invitation (only where still the old default)."""
from django.db import migrations

OLD_MARKERS = {
    "First DM": "We love <something specific>",
    "Follow-up 1": "Hello again from Island Stay!",
    "Follow-up 2 (last)": "One last note from Island Stay",
}


def update(apps, schema_editor):
    from outreach.messages import FIRST_DM, FOLLOW_UP_1, FOLLOW_UP_2
    Message = apps.get_model("outreach", "OutreachMessage")
    new = {"First DM": (FIRST_DM, "Day 1"), "Follow-up 1": (FOLLOW_UP_1, None), "Follow-up 2 (last)": (FOLLOW_UP_2, None)}
    for use, marker in OLD_MARKERS.items():
        text, when = new[use]
        for m in Message.objects.filter(use=use, text__contains=marker):
            m.text = text
            if when:
                m.when = when
            m.save()
    # customised copies of the old first message mention the removed compliment: drop them so leads get the new text
    LeadMessage = apps.get_model("outreach", "LeadMessage")
    LeadMessage.objects.filter(text__contains="<something specific>").delete()


class Migration(migrations.Migration):
    dependencies = [("outreach", "0007_professional_invitation")]
    operations = [migrations.RunPython(update, migrations.RunPython.noop)]
