# Caching

## The caches

There are two optional caches, each turned on by setting its folder in the
[`Config`](configuration.md). Folders are created when first needed.

- `input_cache_dir` keeps the original images downloaded from `url` sources,
  so different thumbnails of the same image only download it once.
- `output_cache_dir` keeps finished thumbnails, so a repeated request skips
  downloading and processing. The cache key is the source, operations,
  `format` and `quality` (and `apply_exif_orientation`), so other query
  parameters don't create extra entries. `make_thumbnail()` and
  `handle_request()` share it.

Use folders that are only used for these caches. Each file is written under
a temporary name and then renamed, so a request never reads a partly
written file. If a cache file can't be written (e.g. the disk is full), the
thumbnail is still returned and a warning is logged to the
`opposable_thumbs` logger.

## When sources change

When a `file` source changes, its thumbnails are made again on the next
request: the file's modification time and size are part of the cache key.

A `url` source isn't checked for changes: once downloaded, the cached copy
and its thumbnails are used until they expire, even if the image online
changes. When you replace an image at the same address, change its `url`,
e.g. add a version: `https://cdn.example.com/photo.jpg?v=2`. The whole
`url` is part of the cache key, so it is downloaded again. Most servers
ignore a query string they don't use, but check that yours does.

## Cleaning the caches

Cached files older than `cache_max_age` seconds are replaced the next time
they are requested. Expired files that are never requested again, and the
thumbnails of files that have since changed, stay on disk. To remove them,
run this on a schedule, e.g. daily from cron:

```
opposable-thumbs clean-cache --input-cache-dir /srv/cache/in --output-cache-dir /srv/cache/out
```

It deletes expired files. Then, if `cache_max_size` is set, it deletes the
oldest files in any cache folder that is still bigger than that, until it
isn't. Each folder is kept under the size separately. Files being written at
that moment are left alone.

- `--max-age SECONDS` sets the age (default one week).
- `--max-size SIZE` sets the size, e.g. `5GB` (default no limit).
- `--all` empties the caches.

Only files whose names look like cache entries are deleted. "Oldest" means
first written, not least used, so a popular thumbnail may be deleted and then
made again on its next request. From Python, call
[`clean_cache(config)`](python.md#clean_cache), optionally with `all=True` or
`max_size="5GB"`. The [Django](django.md#cleaning-the-caches) and
[Flask](flask.md#cleaning-the-caches) integrations have their own commands,
which use your settings.

The caches are only cleaned by these commands, never while serving
thumbnails, so requests don't slow down to check the folders. A full disk
doesn't break anything: the thumbnail is still returned and a warning is
logged.

## Browser and CDN caching

This applies to [`handle_request()`](python.md#handle_request) and the
framework integrations. Images are sent with the `cache_control` setting as
their `Cache-Control` header, by default `max-age=86400` (one day).

Images also have an `ETag`, a hash of the image. When a request's
`If-None-Match` header matches it, the result is `304 Not Modified` with no
body, so a browser or CDN revalidating its copy doesn't download it again.
The thumbnail is still made, or read from the output cache, to check this,
so it saves bandwidth, not processing.
