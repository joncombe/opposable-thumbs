# The Python API

Everything is imported from `opposable_thumbs`. Each function takes a
[`Config`](configuration.md) first.

## make_thumbnail()

```python
from opposable_thumbs import Config, make_thumbnail

config = Config(roots={"media": "/srv/media"})

thumbnail = make_thumbnail(
    config,
    file="media/photo.jpg",
    operations=[("cropratio", 1), ("resize", 300, 300)],
    format="webp",
)
thumbnail.data  # the image, as bytes
thumbnail.content_type  # "image/webp"
```

It takes:

| Argument | |
|---|---|
| `file` | A source image on disk: the name of one of the [`roots`](configuration.md#folders), then the path inside that folder, e.g. `"media/photos/a.jpg"`. |
| `url` | A source image to download. It must match [`allowed_urls`](configuration.md#urls). |
| `operations` | The [operations](operations.md) to run: each a name on its own, or a tuple of a name and its arguments, e.g. `["grayscale", ("resize", 300, 300)]`. Or a string, written as in the `p` [query parameter](operations.md#query-parameters), e.g. `"grayscale\|resize,300,300"`. |
| `format` | The [output format](operations.md#output-format), e.g. `"webp"`. |
| `quality` | JPEG and WebP compression, from `1` (smallest file) to `100` (best image). Pillow's default is `75`. Other formats ignore it. |

Give one of `file` or `url`. It returns a [`Thumbnail`](#thumbnail), and
raises [`ThumbnailError`](#errors) if the thumbnail can't be made. It uses
the [output cache](caching.md), if there is one.

## save_thumbnail()

```python
from opposable_thumbs import save_thumbnail

save_thumbnail(
    config, "/tmp/grey.jpg", file="media/photo.jpg", operations=["grayscale"]
)
```

Makes a thumbnail as `make_thumbnail()` does, with the same arguments after
the path, and saves it to the path. The format is `format` if given,
otherwise the format of the path's extension (e.g. `.webp`), otherwise the
same format as `make_thumbnail()`. Raises [`ThumbnailError`](#errors) if the
thumbnail can't be made.

## image_size()

```python
from opposable_thumbs import image_size

width, height = image_size(config, url="https://media.example.com/photo.jpg")
```

The source image's size, after its EXIF orientation is applied (unless
`apply_exif_orientation` is off), so it matches the image the operations
see. Useful for a crop editor that shows a small thumbnail but saves `crop`
boxes in the source's pixels. Give one of `file` or `url`. Only the header is
read, but a `url` is downloaded in full, to the [input cache](caching.md) if
there is one, so a thumbnail made from it next doesn't download it again.
Raises [`ThumbnailError`](#errors) if the image can't be read.

## handle_request()

```python
result = handle_request(config, query_string, if_none_match=None)
```

Answers a web request for a thumbnail with a [`Result`](#result), an HTTP
response ready to send. `query_string` is the request's query string (see
[Query parameters](operations.md#query-parameters)), or a dict of its
parameters. `if_none_match` is the request's `If-None-Match` header, if any:
when it matches, the result is `304 Not Modified` with no body.

It never raises for a bad request: it returns an error result instead. It
does raise `ConfigError` if URLs are [signed](configuration.md#signed-urls)
but there is no `secret_key`. See
[Using with another web framework](other-frameworks.md).

## thumbnail_query()

```python
query = thumbnail_query(config, file="media/photo.jpg", operations="fit,300,300")
# "file=media/photo.jpg&p=fit,300,300&s=..."
```

Takes the same arguments as `make_thumbnail()` and returns the query string
that asks `handle_request()` for that thumbnail, with every value encoded as
needed. It is [signed](configuration.md#signed-urls) with
`config.secret_key`, unless `config.signed_urls` is `False`. Raises
`ValueError` for an operation name or argument containing `,` or `|`, which
can't be written in a query string. See
[Building thumbnail URLs](other-frameworks.md#building-thumbnail-urls).

## clean_cache()

```python
deleted = clean_cache(config)  # or with all=True, or max_size="5GB"
```

Deletes expired files from the cache folders, or all of them with
`all=True`. Then, while a folder is bigger than `max_size` (by default the
`cache_max_size` setting), deletes its oldest files. Returns how many it
deleted. See [Cleaning the caches](caching.md#cleaning-the-caches).

## Thumbnail

What `make_thumbnail()` returns.

| Attribute | |
|---|---|
| `data` | The image, as bytes. |
| `format` | Its Pillow format name, e.g. `"JPEG"`. |
| `content_type` | Its MIME type, e.g. `"image/jpeg"`. |

## Result

What `handle_request()` returns.

| Attribute | |
|---|---|
| `status` | The HTTP status code, e.g. `200`. |
| `status_line` | The status code and reason, e.g. `"200 OK"`, as WSGI wants it. |
| `headers` | A dict of HTTP headers. Every result has `X-Content-Type-Options: nosniff`, so browsers trust its `Content-Type`. A `304` has no `Content-Type`. |
| `body` | The image, the error messages as plain text, or nothing for a `304`. |
| `content_type` | The `Content-Type` header, if any. |
| `errors` | The error messages, if the status is an error. |

## Errors

Every problem found is reported, not just the first. `make_thumbnail()`,
`save_thumbnail()` and `image_size()` raise `ThumbnailError`, with the messages in `.errors`
and an HTTP status in `.status`. `handle_request()` returns a `Result` with
that status and the messages as plain text, one per line; they are also in
`result.errors`. The status is that of the first error:

| Status | When |
|---|---|
| `400` | No source, or both `file` and `url`; invalid operations or arguments, an unsupported `format` or `quality`, or a request over a [limit](configuration.md#limits). |
| `403` | The URL's [signature](configuration.md#signed-urls) is missing or wrong, or the `file` or `url` isn't allowed by `roots` or `allowed_urls`. |
| `404` | The source image can't be opened: it doesn't exist, isn't an image, is damaged (e.g. truncated), or its format isn't in [`allowed_formats`](configuration.md#allowed-formats). |
| `502` | Downloading the `url` failed, or it didn't return a `200` response. |
| `504` | Downloading the `url` timed out. |

Error results have `Cache-Control: no-store`, so a temporary problem isn't
cached.

A `Config` with an invalid setting raises `ConfigError` when it is made.
