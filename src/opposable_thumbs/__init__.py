"""Thumbnails and image manipulation, from Python or from URL query strings."""

from importlib.metadata import version

from .cache import clean_cache
from .config import Config
from .errors import ConfigError, ThumbnailError
from .query import thumbnail_query
from .result import Result, Thumbnail
from .thumbnail import handle_request, make_thumbnail, save_thumbnail

__version__ = version("opposable-thumbs")

__all__ = [
    "Config",
    "ConfigError",
    "Result",
    "Thumbnail",
    "ThumbnailError",
    "clean_cache",
    "handle_request",
    "make_thumbnail",
    "save_thumbnail",
    "thumbnail_query",
]
