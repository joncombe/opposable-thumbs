import pytest
import requests
from PIL import Image

from opposable_thumbs import Config, handle_request

from helpers import FakeResponse


@pytest.fixture
def images(tmp_path):
    """A folder of small test images, allowed as a file source."""
    folder = tmp_path / "images"
    folder.mkdir()

    # 40 x 30, left half red, right half white
    rgb = Image.new("RGB", (40, 30), "white")
    rgb.paste((255, 0, 0), (0, 0, 20, 30))
    rgb.save(folder / "rgb.png")
    rgb.save(folder / "rgb.jpg")

    Image.new("RGBA", (40, 30), (255, 0, 0, 128)).save(folder / "rgba.png")
    Image.new("LA", (40, 30)).save(folder / "la.png")
    Image.new("I;16", (40, 30), 32768).save(folder / "grey16.png")
    Image.new("CMYK", (40, 30)).save(folder / "cmyk.jpg")
    palette = Image.new("P", (40, 30))
    palette.info["transparency"] = 0
    palette.save(folder / "palette.gif")
    Image.new("1", (40, 30)).save(folder / "bilevel.bmp")
    Image.new("RGB", (40, 30)).save(folder / "photo.tif")

    # an MPO, as phones save: a JPEG with a second image
    red, blue = Image.new("RGB", (40, 30), "red"), Image.new("RGB", (40, 30), "blue")
    red.save(folder / "phone.jpg", "MPO", save_all=True, append_images=[blue])

    # stored 40 x 20, left half red, with an EXIF tag saying to rotate it 90
    # degrees clockwise: upright it is 20 x 40 with red at the top
    sideways = Image.new("RGB", (40, 20), "white")
    sideways.paste((255, 0, 0), (0, 0, 20, 20))
    exif = Image.Exif()
    exif[0x0112] = 6
    sideways.save(folder / "sideways.jpg", exif=exif.tobytes())

    (folder / "not-an-image.png").write_bytes(b"hello")
    return folder


@pytest.fixture
def config(images):
    return Config(roots={"images": images}, signed_urls=False)


@pytest.fixture
def thumb(images, config):
    """handle_request() for a file in `images`, e.g. thumb("rgb.png", "p=blur")."""

    def thumb(name, query="", config=config, **kwargs):
        full_query = f"file=images/{name}" + (f"&{query}" if query else "")
        return handle_request(config, full_query, **kwargs)

    return thumb


@pytest.fixture
def fake_fetch(monkeypatch):
    """Replace requests.get. Set .response or .error, read .calls."""

    class Fetch:
        def __init__(self):
            self.response = FakeResponse()
            self.error = None
            self.calls = []

        def get(self, url, **kwargs):
            self.calls.append((url, kwargs))
            if self.error:
                raise self.error
            return self.response

    fetch = Fetch()
    monkeypatch.setattr(requests, "get", fetch.get)
    return fetch
