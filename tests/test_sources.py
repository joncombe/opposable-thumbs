import os

import pytest
import requests

from opposable_thumbs import Config, handle_request
from opposable_thumbs.sources import is_allowed_url, root_file_path

from helpers import FakeResponse, png_bytes

ALLOWED_URLS = [
    "https://example.com",
    "https://*.example.org",
    "https://cdn.example.net/images/",
    "http://plain.example.com:8080/",
]


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/a.jpg",
        "https://example.com",
        "https://img.example.org/a.jpg",
        "https://a.b.example.org/a.jpg",
        "https://cdn.example.net/images/a.jpg",
        "https://cdn.example.net/images/sub/a.jpg",
        "http://plain.example.com:8080/a.jpg",
    ],
)
def test_allowed_url(url):
    assert is_allowed_url(url, ALLOWED_URLS)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/a.jpg",  # scheme
        "https://example.com:8443/a.jpg",  # port
        "https://example.org/a.jpg",  # *.example.org doesn't match itself
        "https://evil.com/a.jpg",
        "https://example.com.evil.com/a.jpg",
        "https://example.com@evil.com/a.jpg",  # credentials
        "https://user:pass@example.com/a.jpg",
        "https://cdn.example.net/images-private/a.jpg",  # path prefix
        "https://cdn.example.net/a.jpg",
        "https://cdn.example.net/images/../secret.jpg",  # ..
        "https://cdn.example.net/images/%2e%2e/secret.jpg",
        "ftp://example.com/a.jpg",
        "file:///etc/passwd",
        "https://example.com:bad/a.jpg",
        "not a url",
    ],
)
def test_disallowed_url(url):
    assert not is_allowed_url(url, ALLOWED_URLS)


def test_no_allowed_urls_allows_nothing():
    assert not is_allowed_url("https://example.com/a.jpg", [])


@pytest.fixture
def media(tmp_path):
    folder = tmp_path / "media"
    (folder / "sub").mkdir(parents=True)
    return folder


@pytest.mark.parametrize("file", ["media/sub/a.jpg", "media/sub/../sub/a.jpg"])
def test_root_file_path(media, file):
    expected = os.path.realpath(media / "sub" / "a.jpg")
    assert root_file_path(file, {"media": str(media)}) == expected


@pytest.mark.parametrize(
    "file",
    [
        "media/../outside.jpg",
        "media/sub/../../outside.jpg",
        "media//etc/passwd",
        "media/",
        "media",
        "other/a.jpg",
        "/etc/passwd",
        "",
        "media/a\0.jpg",
    ],
)
def test_disallowed_root_file_path(media, file):
    assert root_file_path(file, {"media": str(media)}) is None


def test_symlink_out_of_root(media, tmp_path):
    (tmp_path / "secret.jpg").write_bytes(b"")
    (media / "link.jpg").symlink_to(tmp_path / "secret.jpg")
    assert root_file_path("media/link.jpg", {"media": str(media)}) is None


def test_no_roots_allows_nothing():
    assert root_file_path("media/a.jpg", {}) is None


def test_disallowed_sources_are_403(images):
    result = handle_request(
        Config(signed_urls=False, roots={"images": images}), "file=/etc/hosts"
    )
    assert (result.status, result.errors) == (403, ("Disallowed image file path",))

    result = handle_request(Config(signed_urls=False), "url=https://evil.com/a.png")
    assert (result.status, result.errors) == (403, ("Disallowed image url",))


@pytest.mark.parametrize("query", ["p=blur", "file=/a.jpg&url=https://example.com/"])
def test_one_source_is_needed(config, query):
    result = handle_request(config, query)
    assert (result.status, result.errors) == (400, ("Give one of file or url",))


@pytest.mark.parametrize("name", ["missing.png", "not-an-image.png"])
def test_unopenable_file_is_404(thumb, name):
    result = thumb(name)
    assert (result.status, result.errors) == (404, ("Failed to open image",))


def test_format_not_in_allowed_formats_is_404(images, thumb):
    config = Config(
        signed_urls=False, roots={"images": images}, allowed_formats=["JPEG"]
    )
    assert thumb("rgb.png", config=config).status == 404
    assert thumb("rgb.jpg", config=config).status == 200


def test_too_many_pixels(images, thumb):
    config = Config(signed_urls=False, roots={"images": images}, max_source_pixels=100)
    result = thumb("rgb.png", config=config)
    assert result.errors == ("Source image larger than 100 pixels",)


# urls (requests.get is replaced by the fake_fetch fixture)

URL_CONFIG = Config(signed_urls=False, allowed_urls=["https://example.com/"])
URL_QUERY = "url=https://example.com/a.png"


def test_fetch(fake_fetch):
    fake_fetch.response = FakeResponse(png_bytes())
    result = handle_request(URL_CONFIG, URL_QUERY)
    assert result.status == 200

    url, kwargs = fake_fetch.calls[0]
    assert url == "https://example.com/a.png"
    assert kwargs["allow_redirects"] is False
    assert kwargs["timeout"] == URL_CONFIG.fetch_timeout


@pytest.mark.parametrize(
    "response, status, error",
    [
        (FakeResponse(status_code=404), 502, "Unexpected response status 404"),
        (FakeResponse(status_code=302), 502, "Unexpected response status 302"),
        (
            FakeResponse(headers={"Content-Length": "999"}),
            400,
            "Source image larger than 100 bytes",
        ),
        (FakeResponse(b"x" * 101), 400, "Source image larger than 100 bytes"),
    ],
)
def test_fetch_response_errors(fake_fetch, response, status, error):
    fake_fetch.response = response
    config = Config(
        signed_urls=False, allowed_urls=["https://example.com/"], max_download_bytes=100
    )
    result = handle_request(config, URL_QUERY)
    assert (result.status, result.errors) == (status, (error,))


@pytest.mark.parametrize(
    "error, status, message",
    [
        (requests.ConnectTimeout(), 504, "Timed out after 10s fetching source image"),
        (requests.ConnectionError(), 502, "Failed to fetch source image"),
    ],
)
def test_fetch_exceptions(fake_fetch, error, status, message):
    fake_fetch.error = error
    result = handle_request(URL_CONFIG, URL_QUERY)
    assert (result.status, result.errors) == (status, (message,))


def test_fetched_non_image_is_404(fake_fetch):
    fake_fetch.response = FakeResponse(b"<html>")
    assert handle_request(URL_CONFIG, URL_QUERY).status == 404


def test_malformed_content_length_is_ignored(fake_fetch):
    fake_fetch.response = FakeResponse(png_bytes(), headers={"Content-Length": "x"})
    assert handle_request(URL_CONFIG, URL_QUERY).status == 200
