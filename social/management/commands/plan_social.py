from django.core.management.base import BaseCommand

from social.planner import generate_plan


class Command(BaseCommand):
    help = "Draft a social media plan (6 posts a week) from the islands, hosts and activities in the directory."

    def add_arguments(self, parser):
        parser.add_argument("--weeks", type=int, default=4)

    def handle(self, *args, weeks, **opts):
        posts = generate_plan(weeks=weeks)
        self.stdout.write(self.style.SUCCESS(f"Drafted {len(posts)} posts."))
