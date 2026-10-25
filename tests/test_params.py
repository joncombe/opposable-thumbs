import pytest

from opposable_thumbs import (
    Config,
    ConfigError,
    ThumbnailError,
    handle_request,
    save_thumbnail,
)

from helpers import open_result


def test_query_as_mapping(images, config):
    query = {"file": "images/rgb.png", "p": "resize,10,10"}
    assert open_result(handle_request(config, query)).size == (10, 10)


def test_query_with_leading_question_mark(images, config):
    result = handle_request(config, "?file=images/rgb.png")
    assert result.status == 200


def test_last_repeated_parameter_wins(thumb):
    assert open_result(thumb("rgb.png", "p=resize,5,5&p=resize,8,8")).size == (8, 8)


def test_empty_p_means_no_operations(thumb):
    assert open_result(thumb("rgb.png", "p=")).size == (40, 30)


@pytest.mark.parametrize(
    "query, error",
    [
        ("p=resise,10,10", 'Unknown operation "resise"'),
        ("p=blur|", 'Unknown operation ""'),
        (
            "format=foo",
            "Unsupported format, use one of: JPEG, PNG, GIF, WEBP, BMP, TIFF",
        ),
        ("quality=0", "Invalid quality, use 1 to 100"),
        ("quality=101", "Invalid quality, use 1 to 100"),
        ("quality=5.5", "Invalid quality, use 1 to 100"),
        ("quality=", "Invalid quality, use 1 to 100"),
        ("quality=²", "Invalid quality, use 1 to 100"),
        ("p=" + "|".join(["blur"] * 11), "More than 10 operations (max_operations)"),
    ],
)
def test_invalid_parameters(thumb, query, error):
    result = thumb("rgb.png", query)
    assert (result.status, result.errors) == (400, (error,))


def test_every_parameter_error_is_reported(config):
    result = handle_request(config, "url=https://evil.com/a&p=nope&format=foo")
    # the status is the first error's
    assert result.status == 403
    assert result.errors == (
        "Disallowed image url",
        'Unknown operation "nope"',
        "Unsupported format, use one of: JPEG, PNG, GIF, WEBP, BMP, TIFF",
    )
    assert result.body.decode() == "\n".join(result.errors)


def test_error_result(thumb):
    result = thumb("rgb.png", "p=nope")
    assert result.status_line == "400 Bad Request"
    assert result.headers == {
        "Content-Type": "text/plain; charset=utf-8",
        "Content-Length": str(len(result.body)),
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    }


def test_save_thumbnail_raises(images, config, tmp_path):
    with pytest.raises(ThumbnailError) as e:
        save_thumbnail(
            config, tmp_path / "x.png", file="images/rgb.png", operations=["nope"]
        )
    assert e.value.errors == ('Unknown operation "nope"',)
    assert e.value.status == 400
    assert str(e.value) == 'Unknown operation "nope"'


# Config


def test_config_defaults_allow_nothing(images):
    result = handle_request(Config(signed_urls=False), "file=images/rgb.png")
    assert result.status == 403


def test_config_accepts_paths_and_lists(images):
    config = Config(
        signed_urls=False, roots={"images": images}, allowed_formats=["png", "jpeg"]
    )
    assert config.roots == {"images": str(images)}
    assert config.allowed_formats == ("PNG", "JPEG")


def test_config_rejects_unknown_format():
    with pytest.raises(ConfigError, match="Unknown allowed_formats: NOPE"):
        Config(signed_urls=False, allowed_formats=["JPEG", "nope"])


@pytest.mark.parametrize("name", ["allowed_urls", "allowed_formats"])
def test_config_rejects_single_string(name):
    with pytest.raises(ConfigError, match=f"{name} must be a list"):
        Config(signed_urls=False, **{name: "JPEG"})


@pytest.mark.parametrize("roots", [["/srv/media"], {"": "/srv"}, {"a/b": "/srv"}])
def test_config_rejects_invalid_roots(roots):
    with pytest.raises(ConfigError, match="roots"):
        Config(signed_urls=False, roots=roots)


def test_config_is_immutable():
    config = Config(signed_urls=False, roots={"media": "/srv/media"})
    with pytest.raises(AttributeError):
        config.max_operations = 1
    with pytest.raises(TypeError):
        config.roots["other"] = "/srv/other"
