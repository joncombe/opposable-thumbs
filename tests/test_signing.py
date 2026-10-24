"""Signed URLs: thumbnail_query() signs, handle_request() checks."""

from urllib.parse import parse_qsl, urlencode

import pytest

from opposable_thumbs import (
    Config,
    ConfigError,
    handle_request,
    make_thumbnail,
    thumbnail_query,
)

from helpers import FakeResponse, png_bytes

SECRET = "a-long-random-secret-for-the-tests"
ARGUMENTS = {"file": "images/rgb.png", "operations": [("fit", 20, 20)]}


@pytest.fixture
def signed(images):
    return Config(roots={"images": images}, secret_key=SECRET)


def with_params(query, **changes):
    params = dict(parse_qsl(query))
    params.update(changes)
    return urlencode(params)


def test_signed_url(signed):
    query = thumbnail_query(signed, **ARGUMENTS)
    assert "&s=" in query
    assert handle_request(signed, query).status == 200


@pytest.mark.parametrize(
    "change",
    [
        {"p": "fit,21,21"},
        {"file": "images/rgba.png"},
        {"format": "png"},
        {"quality": "50"},
        {"s": "x" * 22},
        {"s": ""},
        {"s": "ünïcode"},
    ],
)
def test_changed_url_is_refused(signed, change):
    query = with_params(thumbnail_query(signed, **ARGUMENTS), **change)
    result = handle_request(signed, query)
    assert (result.status, result.errors) == (403, ("Missing or invalid signature",))


def test_unsigned_url_is_refused(signed):
    result = handle_request(signed, "file=images/rgb.png&p=fit,20,20")
    assert (result.status, result.errors) == (403, ("Missing or invalid signature",))


def test_signature_is_checked_before_anything_else(signed):
    # a made-up URL learns nothing about what else is wrong with it
    result = handle_request(signed, "file=/etc/hosts&p=nope&format=foo")
    assert result.errors == ("Missing or invalid signature",)


def test_another_secret_is_refused(images, signed):
    other = Config(roots={"images": images}, secret_key="another-secret")
    query = thumbnail_query(other, **ARGUMENTS)
    assert handle_request(signed, query).status == 403


def test_order_encoding_and_other_parameters_dont_matter(signed):
    params = dict(parse_qsl(thumbnail_query(signed, **ARGUMENTS)))
    reordered = urlencode(dict(reversed(params.items())) | {"utm_source": "x"})
    assert handle_request(signed, reordered).status == 200
    assert handle_request(signed, params).status == 200


def test_bytes_secret(images):
    config = Config(roots={"images": images}, secret_key=SECRET.encode())
    query = thumbnail_query(config, **ARGUMENTS)
    assert handle_request(config, query).status == 200


def test_signed_url_source(fake_fetch):
    fake_fetch.response = FakeResponse(png_bytes())
    config = Config(allowed_urls=["https://example.com/"], secret_key=SECRET)
    query = thumbnail_query(config, url="https://example.com/a.png?v=1&x=2")
    assert handle_request(config, query).status == 200


# signing is on by default


def test_signing_needs_a_secret_key(images):
    config = Config(roots={"images": images})
    with pytest.raises(ConfigError, match="secret_key"):
        handle_request(config, "file=images/rgb.png")
    with pytest.raises(ConfigError, match="secret_key"):
        thumbnail_query(config, **ARGUMENTS)


def test_make_thumbnail_doesnt_need_a_secret_key(images):
    assert make_thumbnail(Config(roots={"images": images}), **ARGUMENTS).data


def test_signing_can_be_turned_off(images):
    config = Config(roots={"images": images}, signed_urls=False)
    query = thumbnail_query(config, **ARGUMENTS)
    assert "s=" not in query
    assert handle_request(config, query).status == 200
    assert handle_request(config, query + "&s=anything").status == 200


@pytest.mark.parametrize("secret", ["", b"", 123])
def test_invalid_secret_key(secret):
    with pytest.raises(ConfigError, match="secret_key"):
        Config(secret_key=secret)


def test_secret_key_isnt_in_repr():
    assert SECRET not in repr(Config(secret_key=SECRET))
