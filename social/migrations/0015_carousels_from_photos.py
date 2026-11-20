"""Turns December's place posts (Before you visit, Meet the host, Pick your island by mood) and any unposted Popular
islands drafts into carousels when there are photos to add. Posts already queued or published are left alone."""
from django.db import migrations


def run(apps, schema_editor):
    from social.models import SocialPost
    from social.planner import carouselize

    for post in SocialPost.objects.filter(post_type="feed", ig_state="", status__in=["idea", "draft"]).exclude(format="story"):
        carouselize(post)


class Migration(migrations.Migration):
    dependencies = [("social", "0014_december_eight_islands")]
    operations = [migrations.RunPython(run, migrations.RunPython.noop)]
