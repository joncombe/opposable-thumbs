from dataclasses import dataclass, field
from http import HTTPStatus

from .imaging import OUTPUT_FORMATS


@dataclass(frozen=True)
class Thumbnail:
    """What make_thumbnail() returns: the image, and the format it is in."""

    data: bytes
    # a Pillow format name, e.g. "JPEG"
    format: str

    @property
    def content_type(self):
        # e.g. "image/jpeg"
        return OUTPUT_FORMATS[self.format]


@dataclass(frozen=True)
class Result:
    """What handle_request() returns: an HTTP response, ready to send.

    `status` is 200 with the image as `body`, 304 with an empty body when the
    caller's copy is current, or an error status with the error messages as
    plain text. `headers` always includes Content-Type, except on a 304.
    """

    status: int
    headers: dict[str, str]
    body: bytes
    # the error messages, when status is an error
    errors: tuple[str, ...] = field(default=())

    @property
    def status_line(self):
        # e.g. "200 OK", as WSGI's start_response wants it
        return f"{self.status} {HTTPStatus(self.status).phrase}"

    @property
    def content_type(self):
        return self.headers.get("Content-Type")
