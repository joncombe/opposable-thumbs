import hashlib
import logging
import math
import os
import tempfile
from contextlib import ExitStack
from io import BytesIO

from PIL import Image

from .cache import cache_key, cache_writer, is_fresh, write_cache_file
from .errors import ThumbnailError
from .imaging import (
    FORMAT_ALIASES,
    OUTPUT_FORMATS,
    QUALITY_FORMATS,
    apply_exif_orientation,
    format_for_path,
    normalise_mode,
    output_format_for,
    prepare_for_format,
)
from .operations import (
    CROP_OPERATIONS,
    OPERATIONS,
    OperationError,
    reduction_limit,
    scale_crop,
)
from .query import is_signed, normalise_operations, parse_query, signing_key
from .result import Result, Thumbnail
from .sources import SourceError, fetch, is_allowed_url, root_file_path

logger = logging.getLogger("opposable_thumbs")

# a downloaded source larger than this is kept in a temporary file rather
# than in memory, when there is no input cache to download it to
SPOOL_MAX_SIZE = 5 * 1024 * 1024


def make_thumbnail(
    config, *, file=None, url=None, operations=(), format=None, quality=None
):
    """Make a thumbnail and return it as a Thumbnail.

    Give one of `file` (a root name from config.roots and a path inside it,
    e.g. "media/photos/a.jpg") or `url` (one that matches
    config.allowed_urls). `operations` is a list of operations, each a name
    on its own or a tuple of a name and its arguments, e.g.
    ["grayscale", ("resize", 300, 300)], or a string as in p=, e.g.
    "grayscale|resize,300,300". `format` is the output format (e.g.
    "webp") and `quality` the JPEG or WebP quality, 1 to 100.

    Raises ThumbnailError if the thumbnail can't be made.
    """
    job = _Job(config, file, url, normalise_operations(operations), format, quality)
    made = job.check() and job.make()
    if not made:
        raise job.error()
    return Thumbnail(*made)


def save_thumbnail(
    config, path, *, file=None, url=None, operations=(), format=None, quality=None
):
    """Make a thumbnail, as make_thumbnail() does, and save it to `path`.

    The format is `format` if given, otherwise the one the file extension
    stands for, otherwise the one make_thumbnail() would use. Raises
    ThumbnailError if the thumbnail can't be made.
    """
    job = _Job(config, file, url, normalise_operations(operations), format, quality)
    if not job.check() or not job.render():
        raise job.error()
    job.format = (
        job.requested_format
        or format_for_path(path)
        or output_format_for(job.source_format)
    )
    job.encode(path)


def handle_request(config, query, if_none_match=None):
    """Answer a web request for a thumbnail with a Result: an HTTP response.

    `query` is the request's query string (e.g.
    "file=/images/a.jpg&p=resize,100,100") or a mapping of its parameters.
    `if_none_match` is the request's If-None-Match header, if any: when it
    matches, the Result is a 304 with no body. Problems with the request are
    returned as an error Result, never raised.

    Unless config.signed_urls is False, the query must have been made by
    thumbnail_query() with the same config.secret_key, or it is refused.
    Raises ConfigError if URLs are signed but there is no secret_key.
    """
    parsed = parse_query(query)
    key = signing_key(config)
    if key is not None and not is_signed(key, parsed):
        # checked first, so a made-up URL gets no further
        job = _Job(config, None, None, [], None, None)
        job.add_error("Missing or invalid signature", 403)
        return job.error_result()

    del parsed["signature"]
    job = _Job(config, **parsed)
    made = job.check() and job.make()
    if not made:
        return job.error_result()
    data, format = made
    return job.image_result(data, OUTPUT_FORMATS[format], if_none_match)


def _write_cache(path, data):
    # a cache that can't be written to (e.g. a full disk) only makes things
    # slower, so it is logged rather than failing the request
    try:
        write_cache_file(path, data)
    except OSError as e:
        logger.warning("Can't write cache file %s: %s", path, e)


def _turns_sideways(image):
    # whether the EXIF orientation rotates the image by 90 degrees
    try:
        return image.getexif().get(0x0112) in (5, 6, 7, 8)
    except Exception:
        return False


def _etag_matches(if_none_match, etag):
    # If-None-Match is "*" or a comma separated list of (maybe weak) ETags
    if not if_none_match:
        return False
    tags = [t.strip() for t in if_none_match.split(",")]
    return any(t == "*" or t.removeprefix("W/") == etag for t in tags)


class _Job:
    # one thumbnail: the arguments it was asked for, checked against the
    # Config, then made

    def __init__(self, config, file, url, operations, format, quality):
        self.config = config
        self.file = file
        self.url = url
        self.operations = operations
        self.format_value = format
        self.quality_value = quality

        self.errors = []
        self.error_status = 400

        # set by check()
        self.source_type = None
        self.source = None
        self.source_version = None
        self.requested_format = None
        self.quality = None

        # set while making it
        self.image = None
        self.source_format = None
        self.format = None
        # how many times smaller than the source the image was decoded, across
        # and down, see reduce_decoding() and open_source_from()
        self.scale = (1, 1)

    def add_error(self, error, status=400):
        # keep every error, so a request with several problems reports them
        # all. the status is the first error's, which is usually the cause
        if not self.errors:
            self.error_status = status
        if error not in self.errors:
            self.errors.append(error)

    def error(self):
        return ThumbnailError(self.errors, self.error_status)

    # checking the arguments

    def check(self):
        # everything that can be checked before the source is opened. each
        # check runs, so all of their errors are reported
        results = [
            self.check_source(),
            self.check_operations(),
            self.check_format(),
            self.check_quality(),
        ]
        return all(results)

    def check_source(self):
        if (self.file is None) == (self.url is None):
            self.add_error("Give one of file or url")
            return False

        if self.file is not None:
            path = root_file_path(os.fspath(self.file), self.config.roots)
            if path is None:
                self.add_error("Disallowed image file path", 403)
                return False

            self.source_type, self.source = "file", path
            # part of the output cache key, so a changed file gets a new
            # thumbnail. a missing file is reported when it is opened
            try:
                stat = os.stat(path)
                self.source_version = (stat.st_mtime_ns, stat.st_size)
            except OSError:
                pass
            return True

        if not is_allowed_url(self.url, self.config.allowed_urls):
            self.add_error("Disallowed image url", 403)
            return False

        self.source_type, self.source = "url", self.url
        return True

    def check_operations(self):
        if len(self.operations) > self.config.max_operations:
            self.add_error(
                f"More than {self.config.max_operations} operations (max_operations)"
            )
            return False

        unknown = [op[0] for op in self.operations if op[0] not in OPERATIONS]
        for name in unknown:
            self.add_error(f'Unknown operation "{name}"')

        return not unknown

    def check_format(self):
        value = self.format_value
        if value is None:
            return True

        name = value.upper() if isinstance(value, str) else None
        name = FORMAT_ALIASES.get(name, name)
        if name not in OUTPUT_FORMATS:
            self.add_error(
                f"Unsupported format, use one of: {', '.join(OUTPUT_FORMATS)}"
            )
            return False

        self.requested_format = name
        return True

    def check_quality(self):
        # 1 (smallest file) to 100 (best image), for JPEG and WebP output.
        # other formats ignore it. without it, Pillow's default (75) is used
        value = self.quality_value
        if value is None:
            return True

        if isinstance(value, str) and value.isdecimal():
            value = int(value)
        if isinstance(value, bool) or not isinstance(value, int):
            value = None
        if value is None or not 1 <= value <= 100:
            self.add_error("Invalid quality, use 1 to 100")
            return False

        self.quality = value
        return True

    # making the image

    def download(self, files):
        # the url's image, as a path or an open file. it is downloaded to the
        # input cache when there is one (or read from it, if it has a fresh
        # copy), otherwise to a temporary file closed by `files`, an
        # ExitStack. either way it is never held in memory all at once
        if self.config.input_cache_dir:
            path = os.path.join(self.config.input_cache_dir, cache_key(self.source))
            if is_fresh(path, self.config.cache_max_age):
                return path
            try:
                with cache_writer(path) as f:
                    fetch(self.source, self.config, f)
                return path
            except OSError as e:
                # a cache that can't be written to only makes things slower
                logger.warning("Can't write cache file %s: %s", path, e)

        f = files.enter_context(tempfile.SpooledTemporaryFile(SPOOL_MAX_SIZE))
        fetch(self.source, self.config, f)
        f.seek(0)
        return f

    def open_source(self):
        # the source is closed when this returns
        with ExitStack() as files:
            return self.open_source_from(files)

    def open_source_from(self, files):
        # a file is opened by path, or a download from a file, so only its
        # header is read until the size has been checked
        formats = list(self.config.allowed_formats)
        try:
            if self.source_type == "file":
                source = Image.open(self.source, formats=formats)
            else:
                source = Image.open(self.download(files), formats=formats)
        except SourceError as e:
            self.add_error(str(e), e.status)
            return False
        except Exception:
            self.add_error("Failed to open image", 404)
            return False

        # the source is closed at the end of this block, as Pillow keeps a
        # file with several frames (GIF, TIFF, MPO) open until it is closed
        with source:
            # Image.open only reads the header, so this runs before decoding
            width, height = source.size
            if width * height > self.config.max_source_pixels:
                self.add_error(
                    f"Source image larger than {self.config.max_source_pixels} "
                    "pixels (max_source_pixels)"
                )
                return False

            # decode now, so a broken image (e.g. a truncated file) is an
            # error here rather than an exception in an operation
            try:
                self.reduce_decoding(source)
                source.load()
            except Exception:
                self.add_error("Failed to open image", 404)
                return False

            # how many times smaller it was decoded, if it was, across and
            # down the image the operations see
            x_scale, y_scale = width / source.width, height / source.height
            if self.config.apply_exif_orientation and _turns_sideways(source):
                x_scale, y_scale = y_scale, x_scale
            self.scale = (x_scale, y_scale)

            # keep the format: a converted image doesn't have one
            self.source_format = source.format
            image = source
            if self.config.apply_exif_orientation:
                image = apply_exif_orientation(source)
            if image is source:
                # a copy, as the source can't be used once it is closed
                image = source.copy()
            self.image = normalise_mode(image)

        return True

    def reduce_decoding(self, source):
        # a JPEG can be decoded at 1/2, 1/4 or 1/8 of its size, which is much
        # faster and needs much less memory. done when the operations would
        # shrink it that much anyway, keeping twice the pixels the resize
        # needs, so it stays as smooth as resizing the full image
        if source.format not in ("JPEG", "MPO"):
            return

        # the operations see the image after the EXIF orientation is applied
        width, height = source.size
        if self.config.apply_exif_orientation and _turns_sideways(source):
            width, height = height, width

        limit = reduction_limit(self.operations, width, height) / 2
        if limit >= 2:
            size = (math.ceil(source.width / limit), math.ceil(source.height / limit))
            source.draft(source.mode, size)

    def run_operations(self):
        # crops run first, whatever order they are given in
        ordered = sorted(self.operations, key=lambda op: op[0] not in CROP_OPERATIONS)
        for name, *args in ordered:
            try:
                if name == "crop" and self.scale != (1, 1):
                    args = scale_crop(args, *self.scale)
                self.image = OPERATIONS[name](self.image, args, self.config)
            except OperationError as e:
                self.add_error(str(e))
            except (ValueError, IndexError, ArithmeticError):
                self.add_error(f"Invalid {name} arguments")

    def render(self):
        # open the source and run the operations on it
        if not self.open_source():
            return False

        self.run_operations()
        return not self.errors

    def encode(self, target):
        # save to a path or file object in self.format
        options = {}
        if self.quality and self.format in QUALITY_FORMATS:
            options["quality"] = self.quality
        prepare_for_format(self.image, self.format).save(target, self.format, **options)

    def make(self):
        # (data, format) of the thumbnail, from the output cache if it has a
        # fresh copy, or None if it can't be made. call after check(), so a
        # source no longer allowed isn't served from the cache
        if self.config.output_cache_dir:
            cached = self.read_output_cache()
            if cached:
                return cached

        if not self.render():
            return None

        # save via a buffer: some writers (e.g. TIFF) need to seek
        self.format = self.requested_format or output_format_for(self.source_format)
        buffer = BytesIO()
        self.encode(buffer)
        data = buffer.getvalue()

        if self.config.output_cache_dir:
            _write_cache(self.output_cache_path(), data)

        return data, self.format

    # the output cache

    def output_cache_path(self):
        # only what changes the output is part of the key, so a query string
        # and the same Python arguments share an entry, and unknown query
        # parameters can't create extra ones. no extension: without a format
        # the output format isn't known until the source is opened, so on a
        # hit it is read from the file instead
        key = cache_key(
            self.source_type,
            self.source,
            self.source_version,
            [tuple(op) for op in self.operations],
            self.requested_format or "",
            self.quality,
            self.config.apply_exif_orientation,
        )
        return os.path.join(self.config.output_cache_dir, key)

    def read_output_cache(self):
        # (data, format) of a fresh cached thumbnail, or None. an unreadable
        # file, or one in a format that can't be returned, is treated as
        # missing, so it is replaced
        path = self.output_cache_path()
        if not is_fresh(path, self.config.cache_max_age):
            return None

        try:
            with open(path, "rb") as f:
                data = f.read()
            with Image.open(BytesIO(data)) as cached:
                format = cached.format
        except Exception:
            return None

        return (data, format) if format in OUTPUT_FORMATS else None

    # web responses

    def image_result(self, data, content_type, if_none_match):
        # the ETag is a hash of the image, so it is the same whether or not
        # the image came from the output cache
        etag = f'"{hashlib.md5(data, usedforsecurity=False).hexdigest()}"'
        headers = {"ETag": etag}
        if self.config.cache_control:
            headers["Cache-Control"] = self.config.cache_control

        if _etag_matches(if_none_match, etag):
            return Result(304, headers, b"")

        headers["Content-Type"] = content_type
        headers["Content-Length"] = str(len(data))
        headers["X-Content-Type-Options"] = "nosniff"
        return Result(200, headers, data)

    def error_result(self):
        # plain text, and nosniff so a browser never treats it as HTML (the
        # messages repeat parts of the request). never cached, as the problem
        # may be temporary (e.g. a failed fetch)
        body = "\n".join(self.errors).encode("utf-8")
        headers = {
            "Content-Type": "text/plain; charset=utf-8",
            "Content-Length": str(len(body)),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        }
        return Result(self.error_status, headers, body, tuple(self.errors))
