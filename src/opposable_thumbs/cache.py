import hashlib
import os
import re
import time
import uuid
from contextlib import contextmanager

# only files named like cache entries are deleted, in case a cache folder
# shares a directory with other files: "<md5>", or "<md5>.<uuid>.tmp" left by
# an interrupted write
CACHE_FILENAME = re.compile(r"^[0-9a-f]{32}(\.[0-9a-f]{32}\.tmp)?$")


def cache_key(*parts):
    # a file name for whatever identifies a cache entry
    key = repr(parts).encode("utf-8")
    return hashlib.md5(key, usedforsecurity=False).hexdigest()


def is_fresh(path, max_age):
    # cached files older than max_age seconds are treated as missing, so they
    # are replaced. a max_age of None keeps them forever
    try:
        age = time.time() - os.path.getmtime(path)
    except OSError:
        return False

    return max_age is None or age < max_age


def write_cache_file(path, data):
    with cache_writer(path) as f:
        f.write(data)


@contextmanager
def cache_writer(path):
    # a file to write a cache entry to. it is a temp file renamed into place
    # when the block ends, so a concurrent request never reads a partly
    # written file, and is deleted instead if the block raises. the folder is
    # created if missing
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = f"{path}.{uuid.uuid4().hex}.tmp"
    try:
        with open(temp_path, "xb") as f:
            yield f
        os.replace(temp_path, path)
    except BaseException:
        try:
            os.remove(temp_path)
        except OSError:
            pass
        raise


# multipliers for the units a size can be given in, e.g. "5GB"
SIZE_UNITS = {
    "": 1,
    "b": 1,
    "k": 1000,
    "kb": 1000,
    "m": 1000**2,
    "mb": 1000**2,
    "g": 1000**3,
    "gb": 1000**3,
    "t": 1000**4,
    "tb": 1000**4,
}


def parse_size(size):
    """A size in bytes, from a number or a string like "500MB" or "5GB"
    (in powers of 1000). None stays None. Raises ValueError if it isn't one.
    """
    if size is None:
        return None
    if isinstance(size, int | float) and not isinstance(size, bool):
        value = size
    else:
        match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]*)\s*", str(size))
        if not match or match.group(2).lower() not in SIZE_UNITS:
            raise ValueError(f"Invalid size: {size!r}, e.g. use 500MB or 5GB")
        value = float(match.group(1)) * SIZE_UNITS[match.group(2).lower()]
    if value < 0:
        raise ValueError(f"Invalid size: {size!r}, it can't be negative")
    return int(value)


def clean_cache(config, all=False, max_size=None):
    """Delete files from both cache folders, and return how many.

    Expired files are deleted, or every file with all=True. Then, while a
    cache folder is bigger than max_size bytes (by default
    config.cache_max_size), its oldest files are deleted. max_size can be a
    number of bytes or a string like "5GB". Run it on a schedule, as files
    that are never requested again otherwise stay on disk.
    """
    max_size = config.cache_max_size if max_size is None else parse_size(max_size)
    return sum(
        _clean_folder(folder, config.cache_max_age, all, max_size)
        for folder in (config.input_cache_dir, config.output_cache_dir)
        if folder and os.path.isdir(folder)
    )


def _clean_folder(folder, max_age, all, max_size):
    now = time.time()
    deleted = 0
    kept = []
    for entry in os.scandir(folder):
        if not entry.is_file(follow_symlinks=False):
            continue
        if not CACHE_FILENAME.match(entry.name):
            continue
        try:
            stat = entry.stat()
        except FileNotFoundError:
            continue

        if all or (max_age is not None and now - stat.st_mtime >= max_age):
            deleted += _remove(entry.path)
        else:
            kept.append((stat.st_mtime, stat.st_size, entry.name, entry.path))

    if max_size is not None:
        total = sum(size for _, size, _, _ in kept)
        # oldest first. files still being written (.tmp) count towards the
        # size, but are left alone
        for _, size, name, path in sorted(kept):
            if total <= max_size:
                break
            if name.endswith(".tmp"):
                continue
            if _remove(path):
                deleted += 1
                total -= size

    return deleted


def _remove(path):
    # 1 if the file was deleted, 0 if it was already gone (e.g. deleted by
    # another process)
    try:
        os.remove(path)
        return 1
    except FileNotFoundError:
        return 0
