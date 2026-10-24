from django.core.management.base import BaseCommand, CommandError

from opposable_thumbs import clean_cache

from ...conf import get_config


class Command(BaseCommand):
    help = (
        "Delete cached files older than cache_max_age from the cache folders "
        "in OPPOSABLE_THUMBS, then the oldest files in any folder bigger than "
        "cache_max_size. Run it on a schedule to stop the caches growing."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--all", action="store_true", help="Delete every cached file."
        )
        parser.add_argument(
            "--max-size",
            help="The size to keep each folder under, e.g. 5GB, instead of "
            "cache_max_size.",
        )

    def handle(self, *args, **options):
        try:
            deleted = clean_cache(
                get_config(), all=options["all"], max_size=options["max_size"]
            )
        except ValueError as e:
            raise CommandError(e) from e
        self.stdout.write(f"Deleted {deleted} cached file(s)")
