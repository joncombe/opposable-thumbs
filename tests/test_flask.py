"""The Flask integration, through Flask's test client."""

from html import unescape
from io import BytesIO

import pytest

flask = pytest.importorskip("flask")

from flask import Flask, render_template_string  # noqa: E402
from PIL import Image  # noqa: E402

from opposable_thumbs import Config, ConfigError  # noqa: E402
from opposable_thumbs.flask import init_app, thumbnail_url  # noqa: E402


@pytest.fixture
def app(images):
    app = Flask(__name__)
    app.secret_key = "flask-test-secret"
    app.config["OPPOSABLE_THUMBS"] = {"roots": {"images": str(images)}}
    init_app(app)
    return app


def test_template_global(app):
    with app.test_request_context():
        html = render_template_string(
            '{{ thumbnail_url("images/rgb.png", operations="fit,20,20", '
            'format="webp") }}'
        )
    url = unescape(html)
    assert url.startswith("/thumb?file=images/rgb.png&p=fit,20,20&format=webp&s=")

    response = app.test_client().get(url)
    assert response.status_code == 200
    assert response.content_type == "image/webp"
    assert Image.open(BytesIO(response.data)).size == (20, 20)


def test_thumbnail_url(app):
    with app.test_request_context():
        url = thumbnail_url("images/rgb.png", operations=[("fit", 20, 20)])
    assert app.test_client().get(url).status_code == 200


def test_not_modified(app):
    with app.test_request_context():
        url = thumbnail_url("images/rgb.png")
    client = app.test_client()
    etag = client.get(url).headers["ETag"]
    response = client.get(url, headers={"If-None-Match": etag})
    assert response.status_code == 304
    assert response.data == b""
    assert "Content-Type" not in response.headers


def test_errors(app):
    response = app.test_client().get("/thumb?file=images/rgb.png")
    assert response.status_code == 403
    assert response.data == b"Missing or invalid signature"
    assert response.headers["Content-Type"] == "text/plain; charset=utf-8"


def test_secret_key_comes_from_app_secret_key(app):
    secret_key = app.extensions["opposable_thumbs"].secret_key
    assert secret_key and secret_key != app.secret_key


def test_without_a_secret_key(images):
    app = Flask(__name__)
    app.config["OPPOSABLE_THUMBS"] = {"roots": {"images": str(images)}}
    init_app(app)
    with app.test_request_context(), pytest.raises(ConfigError, match="secret_key"):
        thumbnail_url("images/rgb.png")


def test_url_and_config(images):
    app = Flask(__name__)
    config = Config(roots={"media": str(images)}, secret_key="my-own-secret")
    init_app(app, url="/images/thumb", config=config)
    with app.test_request_context():
        url = thumbnail_url("media/rgb.png")
    assert url.startswith("/images/thumb?")
    assert app.test_client().get(url).status_code == 200


def test_clean_cache_command(images, tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / ("a" * 32)).write_bytes(b"")
    app = Flask(__name__)
    app.secret_key = "flask-test-secret"
    app.config["OPPOSABLE_THUMBS"] = {"output_cache_dir": str(cache)}
    init_app(app)
    result = app.test_cli_runner().invoke(args=["clean-thumbnail-cache", "--all"])
    assert result.output == "Deleted 1 cached file(s)\n"
    assert list(cache.iterdir()) == []


def test_clean_cache_command_max_size(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / ("a" * 32)).write_bytes(b"x" * 100)
    app = Flask(__name__)
    app.secret_key = "flask-test-secret"
    app.config["OPPOSABLE_THUMBS"] = {"output_cache_dir": str(cache)}
    init_app(app)
    runner = app.test_cli_runner()

    result = runner.invoke(args=["clean-thumbnail-cache", "--max-size", "lots"])
    assert result.exit_code == 2
    assert "Invalid size" in result.output

    result = runner.invoke(args=["clean-thumbnail-cache", "--max-size", "50"])
    assert result.output == "Deleted 1 cached file(s)\n"
