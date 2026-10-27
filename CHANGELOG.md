# Changelog

All notable changes to this project are listed here. It follows
[semantic versioning](https://semver.org): while the version is 0.x, a minor
release may change the API.

## 0.3.0

- `image_size()` returns a source image's size, after its EXIF orientation,
  reading only its header. A `url` source goes to the input cache, so a
  thumbnail made from it next doesn't download it again.

## 0.2.0

- `crop` and `cropratio` are no longer limited by `max_output_size`, as a crop
  can't make an image larger. A crop of a large source works, e.g. before a
  resize. `max_output_size` now only applies to `fit`, `pad`, `resize`,
  `resizemax`, `resizemin`, `resizepc` and `rotate`.
- The part of a `crop` box outside the image is ignored, rather than filled
  in, and a box entirely outside the image is an error ("Crop box outside the
  image").
- JPEGs are decoded at a reduced size when the operations include a `crop`
  followed by a resize, with the crop box scaled to match. This was turned off
  by any crop before.
- Downloaded `url` sources are written straight to the input cache, or to a
  temporary file if there isn't one, instead of being held in memory.
- Error messages for limits name the setting, e.g. "Output larger than 4000px
  (max_output_size)".

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
