"""A playground for trying opposable-thumbs in a browser.

Run `uv run playground/serve.py` (or `python playground/serve.py` with the
package installed) and open http://127.0.0.1:8000. Give a port number as an
argument to use another port.

It uses wsgiref from the standard library, which handles one request at a
time. It is for trying the package out, not an example of how to deploy it.
"""

import sys
from pathlib import Path
from wsgiref.simple_server import make_server

from opposable_thumbs import Config, handle_request

HERE = Path(__file__).resolve().parent
# the page asks for file=playground/beach.jpg. it builds thumbnail URLs in the
# browser as you click, and a browser can't sign them (any secret in it could
# be read), so signing is off. a real site signs its URLs with
# thumbnail_query() when it renders its pages, and leaves signing on
CONFIG = Config(roots={"playground": HERE}, signed_urls=False)
SOURCE = HERE / "beach.jpg"


def app(environ, start_response):
    path = environ.get("PATH_INFO", "/")

    if path == "/":
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [(HERE / "index.html").read_bytes()]

    if path == "/source":
        # the original image, to compare with the thumbnails
        start_response("200 OK", [("Content-Type", "image/jpeg")])
        return [SOURCE.read_bytes()]

    if path == "/thumb":
        # this is all it takes to serve thumbnails from a web app
        result = handle_request(
            CONFIG,
            environ.get("QUERY_STRING", ""),
            if_none_match=environ.get("HTTP_IF_NONE_MATCH"),
        )
        start_response(result.status_line, list(result.headers.items()))
        return [result.body]

    start_response("404 Not Found", [("Content-Type", "text/plain")])
    return [b"Not found"]


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    with make_server("127.0.0.1", port, app) as server:
        print(f"Playground at http://127.0.0.1:{port} (Ctrl+C to stop)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
