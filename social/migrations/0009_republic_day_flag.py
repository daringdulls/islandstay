"""Switch the Republic Day 2026 post to the National day (flag) design, unless it has already gone out."""
from django.db import migrations


def use_flag_design(apps, schema_editor):
    SocialPost = apps.get_model("social", "SocialPost")
    SocialPost.objects.filter(title="Republic Day 2026").exclude(ig_state__in=["published", "processing"]).exclude(status="posted").update(
        template="national", eyebrow="Jumhooree Dhuvas · 11 November", headline="Happy Republic Day", accent_word="Republic",
        body="58 years since the Maldives became a republic on 11 November 1968.", attribution="ޖުމްހޫރީ ދުވަސް",
        layout={}, ig_image_url="", ig_state="", status="ready",
    )


class Migration(migrations.Migration):
    dependencies = [("social", "0008_national_template")]
    operations = [migrations.RunPython(use_flag_design, migrations.RunPython.noop)]
