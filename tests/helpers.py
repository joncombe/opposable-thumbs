from io import BytesIO

from PIL import Image


def open_result(result):
    """The Result's body as a Pillow image."""
    assert result.status == 200, result.body
    return Image.open(BytesIO(result.body))


class FakeResponse:
    """Stands in for the response of requests.get()."""

    def __init__(self, body=b"", status_code=200, headers=None):
        self.body = body
        self.status_code = status_code
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def iter_content(self, chunk_size):
        for i in range(0, len(self.body), chunk_size):
            yield self.body[i : i + chunk_size]


def png_bytes(size=(40, 30), color="green"):
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, "PNG")
    return buffer.getvalue()
