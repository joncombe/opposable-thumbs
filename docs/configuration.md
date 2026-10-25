# Configuration

Everything is set on `Config`, and every setting has a default. Two are
needed in practice: nothing can be opened until `roots` or `allowed_urls`
lists a source, and serving URLs needs a `secret_key`. The
[Django](django.md) and [Flask](flask.md) integrations take the same
settings, and make the `secret_key` for you.

```python
from opposable_thumbs import Config

config = Config(
    roots={"media": "/srv/media"},
    secret_key=SECRET_KEY,
    output_cache_dir="/srv/cache/thumbnails",
)
```

| Setting | Default | |
|---|---|---|
| `roots` | `{}` | Named folders that `file` sources come from. See [Folders](#folders). |
| `allowed_urls` | `()` | Where `url` sources may come from. See [URLs](#urls). |
| `secret_key` | `None` | The secret that URLs are signed with. See [Signed URLs](#signed-urls). It isn't shown when the `Config` is printed. |
| `signed_urls` | `True` | `False` accepts URLs without a signature. |
| `allowed_formats` | `("JPEG", "PNG", "GIF", "WEBP", "BMP", "TIFF")` | Source image formats that may be opened. See [Allowed formats](#allowed-formats). |
| `input_cache_dir` | `None` | A folder to keep downloaded `url` sources in. See [Caching](caching.md). |
| `output_cache_dir` | `None` | A folder to keep finished thumbnails in. |
| `cache_max_age` | `604800` (one week) | Seconds before a cached file is replaced. `None` keeps them forever. |
| `cache_max_size` | `None` | The size the cleanup commands keep each cache folder under, in bytes or as a string like `"5GB"`. `None` has no limit. See [Cleaning the caches](caching.md#cleaning-the-caches). |
| `cache_control` | `"max-age=86400"` | The `Cache-Control` header sent with images. `None` sends none. See [Browser and CDN caching](caching.md#browser-and-cdn-caching). |
| `apply_exif_orientation` | `True` | Rotate images upright using their EXIF orientation. See [EXIF orientation](operations.md#exif-orientation). |
| `max_download_bytes` | `20971520` (20 MB) | See [Limits](#limits). |
| `fetch_timeout` | `10` | |
| `max_source_pixels` | `50000000` | |
| `max_output_size` | `4000` | |
| `max_operations` | `10` | |
| `max_blur_radius` | `100` | |

Lists can be given as any sequence, `roots` as any mapping, and folders as
strings or `pathlib.Path`. An invalid setting raises `ConfigError` when the
`Config` is made. A `Config` can't be changed after it is made, so one can be
shared by every request and thread.

## Folders

`file` sources come from named folders, the `roots`:

```python
Config(roots={"media": "/srv/media", "uploads": "/srv/uploads"})
```

`file` is a root name, then the path inside that folder, e.g.
`media/photos/a.jpg` opens `/srv/media/photos/a.jpg`. Your server's folder
paths never appear in URLs, and moving a folder only means changing its
root.

- A `file` whose root isn't listed is rejected.
- The path is fully resolved (`..` and symlinks) and must still be inside the
  root's folder, including any subfolder. A symlink inside the folder that
  points outside it is rejected.
- Root names can't be empty or contain `/`.

**Anyone who can reach your thumbnail URL can read any image under the
`roots`.** Only list folders whose images are safe to make public.

## URLs

A `url` is only fetched if it matches an entry in `allowed_urls`, e.g.

```python
Config(
    allowed_urls=[
        "https://example.com",
        "https://*.example.com",
        "https://cdn.example.net/images/",
    ]
)
```

Each entry is a URL, and a `url` matches it when all of these match:

- **Scheme**: `http` and `https` are different sources.
- **Hostname**: `*` is a wildcard, e.g. `*.example.com` matches
  `my.example.com` and `a.b.example.com`. It does **not** match
  `example.com` itself; add that as a separate entry.
- **Port**: if the entry has no port, the `url` must not have one either, so
  `https://example.com:8443/` needs its own entry.
- **Path**: if the entry has a path, the `url` path must start with it. End
  it with a `/`, otherwise `/images` also matches `/images-private/`.

A `url` containing a username or password, or `..` path segments, is always
rejected. Redirects are not followed: the source must return the image
directly with a `200` response.

Only list domains you control. A hostname is trusted wherever its DNS
points, including internal addresses.

## Allowed formats

Source images are only opened if their format is in `allowed_formats`.
Other formats are rejected, which limits the Pillow image parsers that
untrusted input can reach.

- Names are Pillow format names and are not case sensitive. An empty list
  rejects every image.
- `JPEG` also allows MPO images, the JPEG variant many phones save.
- TIFF is the most complex of the defaults and has the longest history of
  parser vulnerabilities. Remove it if you don't need it, especially if you
  load images from URLs you don't control.

## Signed URLs

Without signing, anyone could make up thumbnail URLs: every size of every
image, with every operation. Each one costs your server processing time,
and with `output_cache_dir` set, each fills more disk. So URLs are signed:
[`thumbnail_query()`](python.md#thumbnail_query) adds a signature (`s=`)
made with your `secret_key`, and
[`handle_request()`](python.md#handle_request) refuses any URL whose
signature doesn't match, with a `403`. Your own pages work as normal, but
nobody else can make new URLs.

- Set `secret_key` to a long random string, kept private like a password,
  e.g. from `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
  Use the same one on every server.
- Changing it makes every existing thumbnail URL invalid, including those in
  pages and caches elsewhere.
- What is signed is the source, operations, `format` and `quality`, so a URL
  still works if its parameters are reordered or others are added, but not
  if any of those change.
- Without a `secret_key`, `thumbnail_query()` and `handle_request()` raise
  `ConfigError`. `make_thumbnail()` and `save_thumbnail()` don't use URLs,
  so they never need one.
- To accept any URL instead, set `signed_urls=False`. Only do this if you
  trust everyone who can reach the URL, or need to build URLs where a secret
  can't be kept, such as in a browser.

## Limits

These stop a single request from using excessive memory, CPU, bandwidth or
disk.

| Setting | Limits |
|---|---|
| `max_download_bytes` | Size of an image downloaded from a `url`: bandwidth, and disk in the input cache. A larger declared `Content-Length` is rejected before downloading, and the download stops as soon as it passes the limit. Downloads go to the input cache, or to a temporary file, so a large one isn't held in memory. |
| `fetch_timeout` | Seconds to wait when downloading from a `url`: for the connection, and for each piece of data after that. It is not a limit on the whole download, so a host that keeps sending data slowly can take longer. |
| `max_source_pixels` | Width × height of the source image, checked before it is decoded. This is the limit on memory: a decoded image needs up to 4 bytes per pixel, e.g. 200 MB for 50 million pixels, though a JPEG is often decoded at a reduced size (see [Speed](operations.md#speed)). |
| `max_output_size` | Width and height (in pixels) of the image produced by an operation that can make it larger: `fit`, `pad`, `resize`, `resizemax`, `resizemin`, `resizepc` and `rotate`. A crop can't, so `crop` and `cropratio` aren't limited by it, even when the source is larger. |
| `max_operations` | Number of operations. |
| `max_blur_radius` | Radius for `gblur` and `unsharp`. |

A request over a limit is an [error](python.md#errors). Its message names the
setting, e.g. `Output larger than 4000px (max_output_size)`.
