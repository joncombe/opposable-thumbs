import pytest

from opposable_thumbs import Config


def test_image_result(thumb):
    result = thumb("rgb.png")
    assert result.status_line == "200 OK"
    assert result.errors == ()
    assert result.headers == {
        "ETag": result.headers["ETag"],
        "Cache-Control": "max-age=86400",
        "Content-Type": "image/png",
        "Content-Length": str(len(result.body)),
        "X-Content-Type-Options": "nosniff",
    }


def test_etag_is_a_hash_of_the_image(thumb):
    first, again = thumb("rgb.png"), thumb("rgb.png")
    other = thumb("rgb.png", "p=invert")
    assert first.headers["ETag"] == again.headers["ETag"]
    assert first.headers["ETag"] != other.headers["ETag"]


def test_etag_is_the_same_from_the_output_cache(thumb, images, tmp_path):
    config = Config(
        signed_urls=False, roots={"images": images}, output_cache_dir=tmp_path
    )
    miss, hit = thumb("rgb.png", config=config), thumb("rgb.png", config=config)
    assert miss.headers["ETag"] == hit.headers["ETag"]


@pytest.mark.parametrize(
    "if_none_match",
    ["{etag}", "W/{etag}", '"other", {etag}', "*"],
)
def test_not_modified(thumb, if_none_match):
    etag = thumb("rgb.png").headers["ETag"]
    result = thumb("rgb.png", if_none_match=if_none_match.format(etag=etag))
    assert result.status_line == "304 Not Modified"
    assert result.body == b""
    assert result.headers == {"ETag": etag, "Cache-Control": "max-age=86400"}


@pytest.mark.parametrize("if_none_match", ['"other"', "", None])
def test_modified(thumb, if_none_match):
    assert thumb("rgb.png", if_none_match=if_none_match).status == 200


def test_errors_are_never_304(thumb):
    assert thumb("rgb.png", "p=nope", if_none_match="*").status == 400


@pytest.mark.parametrize(
    "cache_control, expected",
    [("public, max-age=31536000", "public, max-age=31536000"), (None, None)],
)
def test_cache_control_setting(images, thumb, cache_control, expected):
    config = Config(
        signed_urls=False, roots={"images": images}, cache_control=cache_control
    )
    assert thumb("rgb.png", config=config).headers.get("Cache-Control") == expected
