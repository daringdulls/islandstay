"""Three seasonal Stories for December 2026 (Stories don't change the grid). Runs once."""
import datetime as dt
import zoneinfo

from django.db import migrations

MV = zoneinfo.ZoneInfo("Indian/Maldives")
STORIES = [
    (dt.datetime(2026, 12, 1, 12, 0, tzinfo=MV), "High season: book transfers early",
     "December is high season", "season",
     "Speedboats fill up, so book with your host\nAsk about the last boat after your flight\nGuest houses on popular islands sell out first",
     "December is high season on the local islands. Book your guest house and your transfer together, and tell your host when your flight lands."),
    (dt.datetime(2026, 12, 23, 12, 0, tzinfo=MV), "Christmas on a local island",
     "Christmas on a local island", "local",
     "It's a normal working week on the islands\nNo alcohol, but plenty of fresh juice and seafood\nMany guest houses lay on a special dinner\nResort day trips run if you want a party",
     "Christmas isn't a holiday on local islands, but many guest houses lay on a special dinner for their guests. Ask your host what's planned."),
    (dt.datetime(2026, 12, 31, 20, 0, tzinfo=MV), "New Year's Eve on the islands",
     "Happy New Year from the islands", "islands",
     "Bonfires and music on many local islands\nFireworks from nearby resorts across the lagoon\nThank you for following Island Stay",
     "Happy New Year from all of us at Island Stay. See you on the islands in 2027."),
]


def add(apps, schema_editor):
    Island = apps.get_model("directory", "Island")
    SocialPost = apps.get_model("social", "SocialPost")
    if not Island.objects.exists():
        return
    for when, title, headline, accent, body, caption in STORIES:
        if SocialPost.objects.filter(title=title).exists():
            continue
        SocialPost.objects.create(
            title=title, pillar="practical", template="tip", format="story", post_type="story", status="draft",
            platforms="instagram,facebook", publish_at=when, eyebrow="December on the islands", headline=headline,
            accent_word=accent, body=body, attribution="islandstaymv.com", caption=caption, link="Link in bio",
            hashtags="#IslandStay #Maldives #LocalIslands #MaldivesTravel",
            script="Add a link sticker to islandstaymv.com. Save it to the 'Tips' highlight.")


class Migration(migrations.Migration):
    dependencies = [("social", "0012_know_before_you_go_dec2026")]
    operations = [migrations.RunPython(add, migrations.RunPython.noop)]
