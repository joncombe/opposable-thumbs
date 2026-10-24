# Using with Django

```
pip install opposable-thumbs[django]
```

In `settings.py`, add the app and its settings. `OPPOSABLE_THUMBS` takes any
of the [`Config` settings](configuration.md):

```python
INSTALLED_APPS = [
    # ...
    "opposable_thumbs.django",
]

OPPOSABLE_THUMBS = {
    "roots": {"media": MEDIA_ROOT},
    "output_cache_dir": BASE_DIR / "cache" / "thumbnails",
}
```

In `urls.py`, choose where thumbnails are served from:

```python
urlpatterns = [
    # ...
    path("thumb/", include("opposable_thumbs.django.urls")),
]
```

Then use thumbnails in templates. The operations are written as in the `p`
[query parameter](operations.md#query-parameters): each is a name and its
arguments, separated by commas, and they are separated by `|`. This one
resizes and crops to 300 × 300, then sharpens:

```html
{% load opposable_thumbs %}
<img src="{% thumbnail_url "media/photo.jpg" "fit,300,300|unsharp" format="webp" %}">
```

or in Python, with the same arguments as
[`make_thumbnail()`](python.md#make_thumbnail):

```python
from opposable_thumbs.django.views import thumbnail_url

src = thumbnail_url("media/photo.jpg", operations=[("fit", 300, 300), "unsharp"])
```

## Settings

- URLs are [signed](configuration.md#signed-urls) with a key made from your
  `SECRET_KEY`, so there is nothing to set up. Changing `SECRET_KEY` changes
  every thumbnail URL. To use your own key, set `"secret_key"` in
  `OPPOSABLE_THUMBS`.
- An invalid setting raises `ImproperlyConfigured`.

## The view

The view serves `GET` and `HEAD` requests. It answers a matching
`If-None-Match` header with `304 Not Modified`, and errors with their status
code and messages as plain text. See [Errors](python.md#errors).

## Cleaning the caches

To remove expired cache files, and the oldest if a cache folder is bigger
than `"cache_max_size"`, run this on a schedule, e.g. daily from cron:

```
python manage.py clean_opposable_cache
```

`--max-size 5GB` sets the size instead of the setting, and `--all` empties
the caches.

See [Caching](caching.md).
