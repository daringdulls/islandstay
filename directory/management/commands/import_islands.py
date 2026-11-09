from django.core.management.base import BaseCommand

from directory.island_import import import_islands
from directory.models import Atoll, Island


class Command(BaseCommand):
    help = "Add every inhabited island of the Maldives from directory/data/inhabited_islands.json."

    def handle(self, *args, **options):
        import_islands(Island, Atoll, log=self.stdout.write)
