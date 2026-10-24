import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

from PIL import Image

from .cache import parse_size
from .errors import ConfigError

StrPath = str | os.PathLike


@dataclass(frozen=True)
class Config:
    """Settings for making thumbnails. Every setting has a safe default.

    Nothing can be opened until `roots` or `allowed_urls` lists a source, and
    URLs are signed, so serving them needs a `secret_key`.
    """

    # sources. file= is "<root name>/<path inside that root's folder>", e.g.
    # roots={"media": "/srv/media"} and file=media/photos/a.jpg. a url is only
    # fetched if it matches allowed_urls
    roots: Mapping[str, StrPath] = field(default_factory=dict)
    allowed_urls: Sequence[str] = ()

    # thumbnail_query() signs URLs with secret_key, and handle_request()
    # rejects any that aren't signed with it, so nobody can make up new ones.
    # without signed_urls, any URL is accepted. not shown in repr(), so it
    # doesn't end up in logs
    secret_key: str | bytes | None = field(default=None, repr=False)
    signed_urls: bool = True
    # source images in any other format are rejected, to limit the Pillow
    # parsers that untrusted input can reach
    allowed_formats: Sequence[str] = ("JPEG", "PNG", "GIF", "WEBP", "BMP", "TIFF")

    # caches, each turned on by setting its folder
    input_cache_dir: StrPath | None = None
    output_cache_dir: StrPath | None = None
    # seconds before a cached file is replaced. None keeps them forever
    cache_max_age: float | None = 7 * 24 * 60 * 60
    # the size clean_cache() keeps each cache folder under, in bytes or as a
    # string like "5GB". None has no limit
    cache_max_size: int | str | None = None

    # sent with every image. None sends no Cache-Control header
    cache_control: str | None = "max-age=86400"
    # rotate images upright using their EXIF orientation, as browsers do
    apply_exif_orientation: bool = True

    # limits on a single request
    max_download_bytes: int = 20 * 1024 * 1024
    fetch_timeout: float = 10
    max_source_pixels: int = 50_000_000
    max_output_size: int = 4000
    max_operations: int = 10
    max_blur_radius: int = 100

    def __post_init__(self):
        # store lists as tuples and paths as strings, so a Config can't change
        # after it is made and can be shared between threads
        set_ = object.__setattr__
        set_(self, "roots", self._roots(self.roots))
        set_(self, "allowed_urls", self._tuple("allowed_urls", self.allowed_urls))
        if self.secret_key is not None and (
            not isinstance(self.secret_key, str | bytes) or not self.secret_key
        ):
            raise ConfigError("secret_key must be a non-empty string")
        set_(self, "allowed_formats", self._formats(self.allowed_formats))
        try:
            set_(self, "cache_max_size", parse_size(self.cache_max_size))
        except ValueError as e:
            raise ConfigError(f"cache_max_size: {e}") from e
        for name in ("input_cache_dir", "output_cache_dir"):
            value = getattr(self, name)
            set_(self, name, os.fspath(value) if value else None)

    @staticmethod
    def _roots(roots):
        if not isinstance(roots, Mapping):
            raise ConfigError("roots must map names to folders")
        for name in roots:
            # the name is the first part of file=, up to the first /
            if not isinstance(name, str) or not name or "/" in name:
                raise ConfigError(f"Invalid roots name: {name!r}")
        return MappingProxyType({n: os.fspath(f) for n, f in roots.items()})

    @staticmethod
    def _tuple(name, value):
        # a single string would otherwise become a tuple of its characters
        if isinstance(value, str | bytes | os.PathLike):
            raise ConfigError(f"{name} must be a list, not a single value")
        return tuple(value)

    @classmethod
    def _formats(cls, formats):
        # an unknown name would make Image.open raise, so fail here instead
        formats = tuple(f.upper() for f in cls._tuple("allowed_formats", formats))
        Image.init()
        unknown = [f for f in formats if f not in Image.OPEN]
        if unknown:
            raise ConfigError(f"Unknown allowed_formats: {', '.join(unknown)}")
        return formats
