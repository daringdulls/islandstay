"""Fill the arrival-planner fields of existing routes from their schedule text, where they're still empty."""
from django.db import migrations


def fill(apps, schema_editor):
    from directory.route_timing import infer

    Route = apps.get_model("directory", "TransportRoute")
    for r in Route.objects.all():
        days, last, evening = infer(r.schedule)
        changed = []
        if days and not r.days:
            r.days = days; changed.append("days")
        if last and not r.last_departure:
            r.last_departure = last; changed.append("last_departure")
        if evening and not r.evening:
            r.evening = evening; changed.append("evening")
        if changed:
            r.save(update_fields=changed)


class Migration(migrations.Migration):
    dependencies = [("directory", "0032_arrival_planning_island_fit")]
    operations = [migrations.RunPython(fill, migrations.RunPython.noop)]
