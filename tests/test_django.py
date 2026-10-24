"""The Django integration, through Django's test client."""

from html import unescape
from io import BytesIO, StringIO
from pathlib import Path

import pytest

django = pytest.importorskip("django")

from django.conf import settings  # noqa: E402

if not settings.configured:
    settings.configure(
        SECRET_KEY="django-test-secret",
        ALLOWED_HOSTS=["testserver"],
        INSTALLED_APPS=["opposable_thumbs.django"],
        # this module is the URLconf: see urlpatterns below
        ROOT_URLCONF=__name__,
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "APP_DIRS": True,
            }
        ],
    )
    django.setup()

from django.core.exceptions import ImproperlyConfigured  # noqa: E402
from django.core.management import CommandError, call_command  # noqa: E402
from django.template import Context, Template  # noqa: E402
from django.test import Client, override_settings  # noqa: E402
from django.urls import include, path  # noqa: E402
from PIL import Image  # noqa: E402

from opposable_thumbs import thumbnail_query  # noqa: E402
from opposable_thumbs.django.conf import get_config  # noqa: E402
from opposable_thumbs.django.views import thumbnail_url  # noqa: E402

urlpatterns = [path("thumb/", include("opposable_thumbs.django.urls"))]


@pytest.fixture
def media(images):
    with override_settings(OPPOSABLE_THUMBS={"roots": {"images": str(images)}}):
        yield images


@pytest.fixture
def client():
    return Client()


def render(source, **context):
    return Template("{% load opposable_thumbs %}" + source).render(Context(context))


def test_template_tag(media, client):
    html = render('{% thumbnail_url "images/rgb.png" "fit,20,20" format="webp" %}')
    # escaped for HTML, as it should be in a src attribute
    assert html.startswith("/thumb/?file=images/rgb.png&amp;p=fit,20,20&amp;format")
    url = unescape(html)
    assert "&s=" in url

    response = client.get(url)
    assert response.status_code == 200
    assert response["Content-Type"] == "image/webp"
    assert Image.open(BytesIO(response.content)).size == (20, 20)


def test_thumbnail_url(media, client):
    url = thumbnail_url("images/rgb.png", operations=[("fit", 20, 20)])
    assert client.get(url).status_code == 200


def test_not_modified(media, client):
    url = thumbnail_url("images/rgb.png")
    etag = client.get(url)["ETag"]
    response = client.get(url, headers={"If-None-Match": etag})
    assert response.status_code == 304
    assert response.content == b""
    assert "Content-Type" not in response


def test_errors(media, client):
    response = client.get("/thumb/?file=images/rgb.png")
    assert response.status_code == 403
    assert response.content == b"Missing or invalid signature"
    assert response["Content-Type"] == "text/plain; charset=utf-8"


def test_only_get_and_head(media, client):
    assert client.post(thumbnail_url("images/rgb.png")).status_code == 405
    assert client.head(thumbnail_url("images/rgb.png")).status_code == 200


def test_secret_key_comes_from_django_secret_key(media):
    secret_key = get_config().secret_key
    assert secret_key and secret_key != settings.SECRET_KEY
    with override_settings(SECRET_KEY="another-secret"):
        assert get_config().secret_key != secret_key


def test_secret_key_setting(images, client):
    options = {"roots": {"images": str(images)}, "secret_key": "my-own-secret"}
    with override_settings(OPPOSABLE_THUMBS=options):
        assert get_config().secret_key == "my-own-secret"
        query = thumbnail_query(get_config(), file="images/rgb.png")
        assert client.get(f"/thumb/?{query}").status_code == 200


def test_invalid_settings():
    with override_settings(OPPOSABLE_THUMBS={"no_such_setting": 1}):
        with pytest.raises(ImproperlyConfigured, match="OPPOSABLE_THUMBS"):
            get_config()
    with override_settings(OPPOSABLE_THUMBS={"allowed_formats": ["NOPE"]}):
        with pytest.raises(ImproperlyConfigured, match="NOPE"):
            get_config()


def test_clean_cache_command(images, tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / ("a" * 32)).write_bytes(b"")
    options = {"roots": {"images": str(images)}, "output_cache_dir": str(cache)}
    with override_settings(OPPOSABLE_THUMBS=options):
        output = StringIO()
        call_command("clean_opposable_cache", "--all", stdout=output)
    assert list(Path(cache).iterdir()) == []
    assert output.getvalue() == "Deleted 1 cached file(s)\n"


def test_clean_cache_command_max_size(images, tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / ("a" * 32)).write_bytes(b"x" * 100)
    options = {
        "roots": {"images": str(images)},
        "output_cache_dir": str(cache),
        "cache_max_size": "1KB",
    }
    with override_settings(OPPOSABLE_THUMBS=options):
        # within the setting's limit, so nothing goes
        call_command("clean_opposable_cache", stdout=StringIO())
        assert len(list(cache.iterdir())) == 1
        call_command("clean_opposable_cache", "--max-size", "50", stdout=StringIO())
        assert list(cache.iterdir()) == []
        with pytest.raises(CommandError, match="Invalid size"):
            call_command("clean_opposable_cache", "--max-size", "lots")
