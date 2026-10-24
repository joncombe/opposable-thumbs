# Developing opposable-thumbs

How to work on this project. For how to use the package, see
[README.md](README.md) and [docs/](docs/).

## Setup

The project uses [uv](https://docs.astral.sh/uv/). Install it, then from the
repository folder:

```
uv sync
```

This creates `.venv` with the package (editable) and the development tools,
including Django and Flask for testing the integrations.
Prefix commands with `uv run` to use it, or activate `.venv` yourself.

## Tests

```
uv run pytest
```

The tests never use the network: downloads go through a fake
`requests.get` (the `fake_fetch` fixture in `tests/conftest.py`). Test images
are generated in a temporary folder for each test (the `images` fixture).

GitHub Actions runs the tests on every supported Python version, plus once
with the oldest versions of Pillow and requests that `pyproject.toml` allows.
To run those yourself:

```
uv run --python 3.11 pytest
uv run --isolated --resolution lowest-direct --python 3.11 pytest
```

The oldest-versions run is worth doing after any change to how Pillow is
used: older versions behave differently in places (e.g. `posterize`).

## Linting and formatting

```
uv run ruff check .
uv run ruff format .
```

GitHub Actions fails if either would change anything.

## Documentation

The README is the front page, on GitHub and PyPI: what the package is, quick
starts, and links to the rest. Everything else is in `docs/`, one page per
topic.

- PyPI shows only the README, where relative links don't work, so its links
  to other files are full GitHub URLs. Links between pages in `docs/` are
  relative.
- `tests/test_docs.py` checks that every link, including `#section` anchors,
  goes somewhere that exists, and that the README has no relative links.
  Renaming a heading breaks links to it, and the tests say which.
- It also checks the docs against the code: the settings table and its
  defaults, the operations table (and the playground's list), the output
  formats, the Python API's arguments and attributes, the error statuses,
  and the cleanup commands' options. Change one without the other and a
  test says what's out of date.

## The playground

`playground/` is a page for trying every operation in a browser:

```
uv run playground/serve.py
```

Then open http://127.0.0.1:8000. Give a port number as an argument to use
another port.

- `serve.py` is a small WSGI app on the standard library's `wsgiref` server.
  Its `/thumb` route is the whole integration, so it doubles as the example of
  serving thumbnails from a web app. `/source` serves the original image, so
  the page can show its real file size. `wsgiref` handles one request at a
  time, so it isn't a deployment example.
- The playground sets `signed_urls=False`, because the page builds thumbnail
  URLs in the browser as you click, and a browser can't keep a secret. A real
  site leaves signing on.
- `index.html` is deliberately plain: a table of operations, the format and
  quality options, the resulting URL, and the result and source images, each
  with its size, type and file size. It shows error messages as text.
- When you add an operation, add it to the `OPERATIONS` list in `index.html`.
- `tests/test_playground.py` starts the server and requests a page and a
  thumbnail, so the playground can't silently break.

The playground isn't in the package or the sdist.

The sample image is
[a photo](https://unsplash.com/photos/person-standing-inside-the-brown-boat-parked-on-the-seashore-fzEOvcazEtI)
by [Frankie Spontelli](https://unsplash.com/@fr33water) on Unsplash, at
1920 × 1152.

## Code layout

Everything is in `src/opposable_thumbs/`:

| Module | |
|---|---|
| `__init__.py` | The public API. Anything not exported here is internal. |
| `thumbnail.py` | `make_thumbnail()`, `save_thumbnail()` and `handle_request()`, and the `_Job` class that makes one thumbnail. |
| `query.py` | The query string format: parsing it for `handle_request()`, building it in `thumbnail_query()`, and signing and checking it. |
| `config.py` | `Config`, a frozen dataclass of every setting. |
| `result.py` | `Thumbnail`, what `make_thumbnail()` returns, and `Result`, what `handle_request()` returns. |
| `errors.py` | `ConfigError` and `ThumbnailError`. |
| `operations.py` | Every operation, registered by name with `@operation`. |
| `imaging.py` | Output formats and image modes: what format to save in, converting modes so every operation works, EXIF orientation, flattening transparency for JPEG. |
| `sources.py` | Checking `file` against `roots` and `url` against `allowed_urls`, and downloading. |
| `cache.py` | Reading and writing the cache folders, and `clean_cache()`. |
| `cli.py` | The `opposable-thumbs` command. |
| `django/` | The Django integration: an app with a view, `urls.py`, a template tag and a management command. `conf.py` builds the `Config` from settings. |
| `flask.py` | The Flask integration: `init_app()`, which adds a route, a template global and a CLI command. |

There are two ways in, and they meet in `_Job`. `make_thumbnail()` and
`save_thumbnail()` take Python arguments; `handle_request()` turns a query
string into the same arguments with `parse_query()`. Operations are kept as
lists of strings either way (`normalise_operations()` converts Python
values), so both give the same image and share output cache entries.

A thumbnail is made in this order (see `_Job.check` and `_Job.make`):

1. Check every argument. All the checks run, so every problem is reported,
   not just the first.
2. Return the thumbnail from the output cache, if it has a fresh copy. This
   comes after the checks, so a source that is no longer allowed isn't served
   from the cache.
3. Open the source, checking its format and pixel count before it is decoded.
4. Decode it, at a reduced size if it is a JPEG and the operations allow it
   (see `reduction_limit()`), then apply the EXIF orientation and convert it
   to RGB, RGBA or L.
5. Run the operations, crops first.
6. Save in the output format, write it to the output cache, and return it.

`handle_request()` then turns the image or the errors into a `Result`, with
the ETag, `Cache-Control` and any 304.

A few rules the code follows:

- **The core imports no web framework.** It must stay usable from any Python
  code. Each integration imports only its own framework, and only when it is
  imported itself. A test checks that `import opposable_thumbs` loads neither
  Django nor Flask.
- **Integrations stay thin.** They turn the framework's request into a call
  to `handle_request()`, its `Result` into the framework's response, and the
  framework's settings into a `Config`. Anything more belongs in the core, so
  every framework gets it.
- **Nothing is allowed by default.** Sources must be listed explicitly, URLs
  must be signed unless `signed_urls=False` is set, and every setting that
  limits work has a default.
- **Python callers get exceptions, web requests get responses.**
  `make_thumbnail()` and `save_thumbnail()` raise `ThumbnailError` for bad
  arguments. `handle_request()` never raises for a bad request: it returns an
  error `Result`. Only a bug raises: a cache that can't be written to is
  logged as a warning, as it only makes things slower.
- **Close what you open.** Pillow keeps some image files open until they are
  closed, so `_Job.open_source` closes the source once it has a copy. The
  tests fail on any warning, including a file left open.
- **The query string format lives here, not in framework packages.** They
  pass the query string to `handle_request()` untouched, so a URL behaves the
  same in every framework.
- **`Config` can't change after it is made**, so one instance can be shared by
  every request and thread.

## Adding a framework integration

Look at `flask.py`, the simpler of the two. An integration:

1. Imports its framework in a `try`, raising an `ImportError` that says which
   extra to install, e.g. `pip install opposable-thumbs[flask]`.
2. Builds a `Config` from the framework's settings, using a key made from
   the framework's own secret (if it has one) as the default `secret_key`.
3. Serves thumbnails with `handle_request()`, passing the raw query string
   and the `If-None-Match` header, and copying the `Result`'s status, headers
   and body to the response. A 304 has no Content-Type, so make sure the
   framework doesn't add one.
4. Offers a `thumbnail_url()` for templates and code, using
   `thumbnail_query()`.
5. Wraps `clean_cache()` in the framework's command line, if it has one.

Then add the framework to `[project.optional-dependencies]` and the `dev`
group in `pyproject.toml`, add tests that go through the framework's test
client (see `tests/test_flask.py`), add it to the framework import test in
`tests/test_python_api.py`, and add a page to `docs/` and a quick start to
the README.

## Adding an operation

1. Write a function in `operations.py` and register it:

   ```python
   @operation("sepia")
   def sepia(image, args, config):
       ...
       return new_image
   ```

   It gets the image (always RGB, RGBA or L), the arguments from `p` as a
   list of strings, and the `Config`. It returns the new image.

   - Raise `ValueError`, `IndexError` or `ArithmeticError` for invalid
     arguments; they are reported as "Invalid sepia arguments". Converting
     with `int()` and `float()` and indexing `args` does this for you.
   - Raise `OperationError("...")` for a more specific message, e.g. a limit.
   - If it changes the size, call `check_output_size()` first.
   - If it uses a Pillow function that refuses or mishandles an alpha channel,
     wrap it in `apply_without_alpha()`.
   - Use `@operation("name", crop=True)` only for crops, which run first.
   - If it gives the same result on a smaller image (e.g. a colour change),
     add it to `SCALE_FREE_OPERATIONS`, so JPEGs can still be decoded at a
     reduced size when it comes before a resize. If it sets the output size,
     add it to `reduction_limit()`. Otherwise do nothing: unknown operations
     turn reduced decoding off, which is always safe.

2. Add it to `VALID` in `tests/test_operations.py`, with example arguments
   and the size it should produce. A test fails until every operation is
   listed there, and the operation is then tested on every image mode and with
   transparency. Add bad arguments to `test_invalid_arguments`.
3. Add it to the operations table in `docs/operations.md`.
4. Add it to the `OPERATIONS` list in `playground/index.html`.

## Releasing

Releases are published to PyPI by GitHub Actions when a tag like `v0.2.0` is
pushed. `.github/workflows/release.yml` runs the tests, checks the tag
matches the version in `pyproject.toml`, builds, and publishes.

### How publishing is set up

PyPI trusts this repository's `release.yml` workflow, running in the GitHub
`pypi` environment, to publish `opposable-thumbs`
([trusted publishing](https://docs.pypi.org/trusted-publishers/)), so no API
token is stored anywhere. If you rename the repository, the workflow file or
the environment, update the publisher in the project's settings on PyPI to
match, or releases will fail.

### Each release

1. Set the new version, following [semantic versioning](https://semver.org):

   ```
   uv version --bump patch    # or minor, or major, or e.g. uv version 0.2.0
   ```

   While the version is `0.x`, a minor release may change the API.
2. Add the version and its changes to the top of `CHANGELOG.md`.
3. Commit, then tag and push:

   ```
   git tag v0.2.0
   git push origin main v0.2.0
   ```

4. Watch the Release workflow in GitHub Actions. If a step fails, nothing is
   published: fix it, delete the tag (`git tag -d v0.2.0` and
   `git push origin :v0.2.0`), and tag again.

## Security notes

Two limits are knowingly out of scope, because both need a hostile host
listed in `allowed_urls`, and those hosts are trusted:

- **DNS can point an allowed hostname at an internal address.** Nothing stops
  an allowed domain resolving to e.g. `127.0.0.1`. Only list domains you
  control.
- **There is no limit on the total download time.** `fetch_timeout` applies to
  each wait for data, so a host that sends a byte every few seconds can hold a
  worker much longer.

Keeping animation (every frame of a GIF or WebP) is also out of scope: it
multiplies the work by the frame count and isn't needed for thumbnails.
