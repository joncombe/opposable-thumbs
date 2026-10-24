"""The playground isn't part of the package, but it shouldn't break."""

import importlib.util
import threading
import urllib.error
import urllib.request
from io import BytesIO
from pathlib import Path
from wsgiref.simple_server import WSGIRequestHandler, make_server

import pytest
from PIL import Image

PLAYGROUND = Path(__file__).resolve().parent.parent / "playground"

# the playground is in the repo but not in the sdist
pytestmark = pytest.mark.skipif(
    not PLAYGROUND.exists(), reason="the playground isn't here"
)


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def server():
    spec = importlib.util.spec_from_file_location("serve", PLAYGROUND / "serve.py")
    serve = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(serve)

    httpd = make_server("127.0.0.1", 0, serve.app, handler_class=QuietHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    httpd.server_close()


def test_page(server):
    with urllib.request.urlopen(server) as response:
        page = response.read().decode()
    assert '"playground/beach.jpg"' in page


def test_source(server):
    with urllib.request.urlopen(f"{server}/source") as response:
        assert response.headers["Content-Type"] == "image/jpeg"
        assert response.read() == (PLAYGROUND / "beach.jpg").read_bytes()


def test_thumbnail(server):
    query = "file=playground/beach.jpg&p=resizemax,100,100&format=png"
    with urllib.request.urlopen(f"{server}/thumb?{query}") as response:
        assert response.headers["Content-Type"] == "image/png"
        assert Image.open(BytesIO(response.read())).size == (100, 60)


def test_error(server):
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(f"{server}/thumb?file=/etc/hosts")
    with e.value as response:
        assert response.code == 403
        assert response.read() == b"Disallowed image file path"
