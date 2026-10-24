# Changelog

All notable changes to this project are listed here. It follows
[semantic versioning](https://semver.org): while the version is 0.x, a minor
release may change the API.

## 0.1.0

The first release.

- Make thumbnails from Python with `make_thumbnail()` and `save_thumbnail()`,
  or serve them from any web app with `handle_request()`, which turns a query
  string into an HTTP response.
- Build thumbnail URLs with `thumbnail_query()`. URLs are signed with
  `secret_key` by default, so nobody else can make new ones.
- Django and Flask integrations, installed with `opposable-thumbs[django]` or
  `opposable-thumbs[flask]`: a view or route, a `thumbnail_url` template tag
  or global, settings, and a command to clean the caches.
- 29 operations, including `fit`, `pad`, `cropratio`, `rotate`, `circle`,
  `rounded`, `unsharp` and colour adjustments.
- Sources are files in named folders (`roots`) or allowed URLs, in allowed
  formats only, with limits on download size, image size and work per
  request.
- Optional caches for downloaded sources and finished thumbnails, and an
  `opposable-thumbs clean-cache` command to remove expired files and keep
  each cache under a maximum size.
- `ETag`, `Cache-Control` and `304 Not Modified` responses for browsers and
  CDNs.
- JPEGs are decoded at a reduced size when the operations allow it, for
  faster thumbnails that use less memory.
- EXIF orientation is applied, so phone photos come out upright.
