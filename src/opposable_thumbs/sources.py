import os
from fnmatch import fnmatchcase
from urllib.parse import unquote, urlsplit

import requests


class SourceError(Exception):
    """The source image couldn't be fetched."""

    def __init__(self, message, status):
        super().__init__(message)
        self.status = status


def root_file_path(file, roots):
    # the real path of file= ("<root name>/<path inside the root>") if it is
    # inside that root's folder, otherwise None. both sides are resolved with
    # realpath, so ".." and symlinks can't escape the folder
    name, _, relative = file.partition("/")
    if name not in roots or not relative or os.path.isabs(relative):
        return None

    try:
        root = os.path.realpath(roots[name])
        path = os.path.realpath(os.path.join(root, relative))
        if path != root and os.path.commonpath([root, path]) == root:
            return path
    except ValueError:
        # e.g. a null byte in the path, or a different drive on Windows
        pass

    return None


def is_allowed_url(url, allowed_urls):
    # compare the parsed url against each allowed_urls entry: scheme, hostname
    # (glob, e.g. *.example.com), port and path prefix must all match. no
    # allowed_urls means nothing is allowed
    try:
        u = urlsplit(url)
        port = u.port
    except ValueError:
        return False

    # reject credentials (https://allowed.com@evil.com) and ".." segments
    if (
        u.scheme not in ("http", "https")
        or not u.hostname
        or u.username is not None
        or u.password is not None
        or ".." in unquote(u.path).split("/")
    ):
        return False

    path = u.path or "/"
    for source in allowed_urls:
        s = urlsplit(source)
        if (
            u.scheme == s.scheme
            and fnmatchcase(u.hostname, s.hostname or "")
            and port == s.port
            and path.startswith(s.path or "/")
        ):
            return True

    return False


def fetch(url, config, out):
    # download the url into `out`, a binary file. redirects are not followed:
    # an allowed source could otherwise redirect to a disallowed one. the body
    # is streamed to `out`, so it is never all in memory, and an oversized
    # response is abandoned at max_download_bytes. fetch_timeout applies to
    # connecting and to each wait for data, not to the whole download
    max_bytes = config.max_download_bytes
    too_large = f"Source image larger than {max_bytes} bytes (max_download_bytes)"

    try:
        with requests.get(
            url, allow_redirects=False, stream=True, timeout=config.fetch_timeout
        ) as r:
            if r.status_code != 200:
                raise SourceError(f"Unexpected response status {r.status_code}", 502)

            # a malformed Content-Length is ignored: the download below is
            # limited either way
            try:
                declared = int(r.headers.get("Content-Length") or 0)
            except ValueError:
                declared = 0
            if declared > max_bytes:
                raise SourceError(too_large, 400)

            size = 0
            for chunk in r.iter_content(chunk_size=64 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise SourceError(too_large, 400)
                out.write(chunk)
    except requests.Timeout as e:
        raise SourceError(
            f"Timed out after {config.fetch_timeout}s fetching source image "
            "(fetch_timeout)",
            504,
        ) from e
    except requests.RequestException as e:
        # includes a timeout while reading the body, which requests reports as
        # a ConnectionError
        raise SourceError("Failed to fetch source image", 502) from e
