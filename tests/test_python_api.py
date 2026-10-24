"""make_thumbnail(), and thumbnail_query() building queries for handle_request()."""

import os
import subprocess
import sys
from io import BytesIO
from urllib.parse import parse_qs

import pytest
from PIL import Image

from opposable_thumbs import (
    Config,
    Thumbnail,
    ThumbnailError,
    handle_request,
    make_thumbnail,
    thumbnail_query,
)

from helpers import FakeResponse, png_bytes


def size_of(thumbnail):
    return Image.open(BytesIO(thumbnail.data)).size


def test_make_thumbnail(images, config):
    thumbnail = make_thumbnail(
        config,
        file="images/rgb.png",
        operations=["grayscale", ("resize", 20, 10)],
        format="webp",
        quality=80,
    )
    assert isinstance(thumbnail, Thumbnail)
    assert thumbnail.format == "WEBP"
    assert thumbnail.content_type == "image/webp"
    assert size_of(thumbnail) == (20, 10)


def test_make_thumbnail_keeps_source_format(images, config):
    assert make_thumbnail(config, file="images/rgb.jpg").format == "JPEG"


@pytest.mark.parametrize(
    "operation", [("resizepc", 0.5, 0.5), ("resizepc", "0.5", "0.5")]
)
def test_arguments_can_be_numbers_or_strings(images, config, operation):
    thumbnail = make_thumbnail(config, file="images/rgb.png", operations=[operation])
    assert size_of(thumbnail) == (20, 15)


def test_make_thumbnail_from_url(fake_fetch):
    fake_fetch.response = FakeResponse(png_bytes())
    config = Config(signed_urls=False, allowed_urls=["https://example.com/"])
    thumbnail = make_thumbnail(config, url="https://example.com/a.png")
    assert thumbnail.format == "PNG"


FORMAT_ERROR = "Unsupported format, use one of: JPEG, PNG, GIF, WEBP, BMP, TIFF"
QUALITY_ERROR = "Invalid quality, use 1 to 100"


@pytest.mark.parametrize(
    "kwargs, errors, status",
    [
        ({"operations": ["nope"]}, ('Unknown operation "nope"',), 400),
        ({"operations": [("resize", "x", 1)]}, ("Invalid resize arguments",), 400),
        ({"operations": [()]}, ('Unknown operation ""',), 400),
        ({"format": "nope"}, (FORMAT_ERROR,), 400),
        ({"format": 5}, (FORMAT_ERROR,), 400),
        ({"quality": 0}, (QUALITY_ERROR,), 400),
        ({"quality": 50.5}, (QUALITY_ERROR,), 400),
        ({"quality": True}, (QUALITY_ERROR,), 400),
        (
            {"operations": ["nope"], "format": "nope"},
            ('Unknown operation "nope"', FORMAT_ERROR),
            400,
        ),
    ],
)
def test_make_thumbnail_errors(images, config, kwargs, errors, status):
    with pytest.raises(ThumbnailError) as e:
        make_thumbnail(config, file="images/rgb.png", **kwargs)
    assert (e.value.errors, e.value.status) == (errors, status)


@pytest.mark.parametrize(
    "kwargs, error, status",
    [
        ({}, "Give one of file or url", 400),
        ({"file": "/etc/hosts"}, "Disallowed image file path", 403),
        ({"url": "https://evil.com/a.png"}, "Disallowed image url", 403),
    ],
)
def test_make_thumbnail_source_errors(config, kwargs, error, status):
    with pytest.raises(ThumbnailError) as e:
        make_thumbnail(config, **kwargs)
    assert (e.value.errors, e.value.status) == ((error,), status)


def test_both_sources_is_an_error(images, config):
    with pytest.raises(ThumbnailError, match="Give one of file or url"):
        make_thumbnail(config, file="images/rgb.png", url="https://example.com/")


def test_quality_as_a_numeric_string(images, config):
    assert make_thumbnail(config, file="images/rgb.png", quality="80").data


# thumbnail_query

UNSIGNED = Config(signed_urls=False)


def test_thumbnail_query():
    query = thumbnail_query(
        UNSIGNED,
        file="media/a.jpg",
        operations=[("cropratio", 1), ("resize", 300, 300), "grayscale"],
        format="webp",
        quality=80,
    )
    assert query == (
        "file=media/a.jpg&p=cropratio,1%7Cresize,300,300%7Cgrayscale"
        "&format=webp&quality=80"
    )


def test_thumbnail_query_encodes_values():
    query = thumbnail_query(UNSIGNED, url="https://example.com/a.jpg?v=1&w=2 x")
    assert parse_qs(query) == {"url": ["https://example.com/a.jpg?v=1&w=2 x"]}


def test_thumbnail_query_leaves_out_what_isnt_given():
    assert thumbnail_query(UNSIGNED, file="media/a.jpg") == "file=media/a.jpg"


@pytest.mark.parametrize("operation", [("resize", "1,2", 3), "blur|invert"])
def test_thumbnail_query_rejects_separators(operation):
    with pytest.raises(ValueError, match="can't contain"):
        thumbnail_query(UNSIGNED, file="media/a.jpg", operations=[operation])


# the Python arguments and the query string mean the same thing

ARGUMENTS = {
    "operations": [("cropratio", 1.5), ("resize", 30, 20), "invert"],
    "format": "jpeg",
    "quality": 60,
}


def test_query_and_python_arguments_make_the_same_image(images, config):
    file = "images/rgb.png"
    thumbnail = make_thumbnail(config, file=file, **ARGUMENTS)
    result = handle_request(config, thumbnail_query(config, file=file, **ARGUMENTS))
    assert result.body == thumbnail.data
    assert result.content_type == thumbnail.content_type


def test_query_and_python_arguments_share_a_cache_entry(images, tmp_path):
    config = Config(
        signed_urls=False, roots={"images": images}, output_cache_dir=tmp_path / "out"
    )
    file = "images/rgb.png"
    make_thumbnail(config, file=file, **ARGUMENTS)
    handle_request(config, thumbnail_query(config, file=file, **ARGUMENTS))
    assert len(os.listdir(tmp_path / "out")) == 1


def test_operations_as_a_string(images, config):
    thumbnail = make_thumbnail(
        config, file="images/rgb.png", operations="grayscale|resize,20,10"
    )
    assert size_of(thumbnail) == (20, 10)
    assert thumbnail_query(UNSIGNED, file="a/b.jpg", operations="blur|fit,1,1") == (
        "file=a/b.jpg&p=blur%7Cfit,1,1"
    )


# the core is framework-free


def run_python(code):
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)


def test_core_imports_no_framework():
    result = run_python(
        "import sys, opposable_thumbs\n"
        "print(sorted({'django', 'flask'} & sys.modules.keys()))"
    )
    assert result.stdout.strip() == "[]", result.stderr


@pytest.mark.parametrize("framework", ["django", "flask"])
def test_integration_without_its_framework(framework):
    # None in sys.modules makes importing it fail, as if it weren't installed
    result = run_python(
        f"import sys; sys.modules[{framework!r}] = None\n"
        f"import opposable_thumbs.{framework}"
    )
    assert f"pip install opposable-thumbs[{framework}]" in result.stderr
