import argparse

from .cache import clean_cache
from .config import Config
from .errors import ConfigError


def main(argv=None):
    parser = argparse.ArgumentParser(prog="opposable-thumbs")
    commands = parser.add_subparsers(dest="command", required=True)

    clean = commands.add_parser(
        "clean-cache",
        help="delete expired files from the cache folders",
        description=(
            "Delete cached files older than --max-age seconds, then the oldest "
            "files in any folder bigger than --max-size. Run it on a schedule "
            "to stop the caches growing."
        ),
    )
    clean.add_argument("--input-cache-dir", help="the input_cache_dir folder")
    clean.add_argument("--output-cache-dir", help="the output_cache_dir folder")
    clean.add_argument(
        "--max-age",
        type=float,
        default=Config.cache_max_age,
        help="the cache_max_age setting, in seconds (default: %(default)s)",
    )
    clean.add_argument(
        "--max-size",
        help="the cache_max_size setting: the size to keep each folder under, "
        "e.g. 5GB (default: no limit)",
    )
    clean.add_argument("--all", action="store_true", help="delete every cached file")

    args = parser.parse_args(argv)
    if not args.input_cache_dir and not args.output_cache_dir:
        parser.error("give --input-cache-dir, --output-cache-dir or both")

    try:
        config = Config(
            input_cache_dir=args.input_cache_dir,
            output_cache_dir=args.output_cache_dir,
            cache_max_age=args.max_age,
            cache_max_size=args.max_size,
        )
    except ConfigError as e:
        parser.error(str(e))
    deleted = clean_cache(config, all=args.all)
    print(f"Deleted {deleted} cached file(s)")
