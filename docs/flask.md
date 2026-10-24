# Using with Flask

```
pip install opposable-thumbs[flask]
```

Set `OPPOSABLE_THUMBS` to any of the [`Config` settings](configuration.md),
then call `init_app()`:

```python
from opposable_thumbs.flask import init_app

app.config["OPPOSABLE_THUMBS"] = {
    "roots": {"media": "/srv/media"},
    "output_cache_dir": "/srv/cache/thumbnails",
}
init_app(app)  # serves thumbnails at /thumb
```

Then use thumbnails in templates. The operations can be written as in the
`p` [query parameter](operations.md#query-parameters): each is a name and its
arguments, separated by commas, and they are separated by `|`. This one
resizes and crops to 300 × 300, then sharpens:

```html
<img src="{{ thumbnail_url('media/photo.jpg', operations='fit,300,300|unsharp', format='webp') }}">
```

or in Python, during a request, with the same arguments as
[`make_thumbnail()`](python.md#make_thumbnail):

```python
from opposable_thumbs.flask import thumbnail_url

src = thumbnail_url("media/photo.jpg", operations=[("fit", 300, 300), "unsharp"])
```

## Settings

- URLs are [signed](configuration.md#signed-urls) with a key made from
  `app.secret_key`, which must be set. To use your own key, set
  `"secret_key"` in `OPPOSABLE_THUMBS`.
- `init_app()` reads `OPPOSABLE_THUMBS` when it is called, so set it first.
- `init_app(app, url="/images/thumb")` serves thumbnails somewhere else.
- `init_app(app, config=Config(...))` uses a `Config` you made, instead of
  `OPPOSABLE_THUMBS`.

## The route

The route answers a matching `If-None-Match` header with `304 Not Modified`,
and errors with their status code and messages as plain text. See
[Errors](python.md#errors).

## Cleaning the caches

To remove expired cache files, and the oldest if a cache folder is bigger
than `"cache_max_size"`, run this on a schedule, e.g. daily from cron:

```
flask clean-thumbnail-cache
```

`--max-size 5GB` sets the size instead of the setting, and `--all` empties
the caches.

See [Caching](caching.md).
