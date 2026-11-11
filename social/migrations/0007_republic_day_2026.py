"""Adds the Republic Day 2026 post (11 November) as a draft, ready to post from the admin."""
import datetime as dt
import zoneinfo

from django.db import migrations

TITLE = "Republic Day 2026"

CAPTION = (
    "Republic Day mubaarak.\n\n"
    "On 11 November 1968 the Maldives became a republic. Today, 58 years on, Maldivians mark "
    "Jumhooree Dhuvas (ޖުމްހޫރީ ދުވަސް, Republic Day) with a public holiday across the islands.\n\n"
    "Visiting a local island today? Government offices are closed and some shops and cafés keep holiday "
    "hours, so check with your host before you plan the day.\n\n"
    "Warm wishes to everyone across the 26 atolls. 🇲🇻"
)


def add_post(apps, schema_editor):
    Island = apps.get_model("directory", "Island")
    SocialPost = apps.get_model("social", "SocialPost")
    if not Island.objects.exists() or SocialPost.objects.filter(title=TITLE).exists():
        return  # empty database (tests, new installs) or already added
    when = dt.datetime(2026, 11, 11, 18, 0, tzinfo=zoneinfo.ZoneInfo("Indian/Maldives"))
    SocialPost.objects.create(
        title=TITLE, pillar="culture", template="word", format="portrait", post_type="feed", status="ready",
        platforms="instagram,facebook", publish_at=when,
        eyebrow="11 November · Jumhooree Dhuvas", headline="Republic Day", accent_word="",
        attribution="ޖުމްހޫރީ ދުވަސް",
        body="58 years ago today, on 11 November 1968, the Maldives became a republic.",
        caption=CAPTION, link="Link in bio",
        hashtags="#IslandStay #Maldives #LocalIslands #RepublicDay #JumhooreeDhuvas #MaldivesCulture #Dhivehi",
    )


class Migration(migrations.Migration):
    dependencies = [("social", "0006_layout"), ("directory", "0029_home_banner")]
    operations = [migrations.RunPython(add_post, migrations.RunPython.noop)]
