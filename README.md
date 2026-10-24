# opposable-thumbs

Make thumbnails and simple image edits from Python, or serve them from your
web app with URLs like
`/thumb?file=media/photo.jpg&p=fit,300,300&format=webp`.

It is designed to plug into a project you already have: install it, add a
few lines, and your app serves its own thumbnails, with no separate image
server, reverse proxy or other infrastructure to run. Sources must be allowed
explicitly, URLs are signed, and every request is limited in size and work,
so it is safe to expose to the public.

It isn't trying to compete with dedicated image servers such as
[Thumbor](https://github.com/thumbor/thumbor) or
[imgproxy](https://github.com/imgproxy/imgproxy). They are faster and do
more, e.g. face-aware cropping, cloud storage and animated images. If you
serve a lot of images, or speed matters most, use one of those instead.

Requires Python 3.11+. Uses [Pillow](https://python-pillow.org) for images
and [requests](https://requests.readthedocs.io) to fetch remote ones.

## Install

```
pip install opposable-thumbs
```

For the Django or Flask integration, install `opposable-thumbs[django]` or
`opposable-thumbs[flask]` instead, which also requires the framework.

## Quick start

### Django

```python
# settings.py
INSTALLED_APPS = [..., "opposable_thumbs.django"]
OPPOSABLE_THUMBS = {"roots": {"media": MEDIA_ROOT}}

# urls.py
urlpatterns = [..., path("thumb/", include("opposable_thumbs.django.urls"))]
```

```html
{% load opposable_thumbs %}
<img src="{% thumbnail_url "media/photo.jpg" "fit,300,300|unsharp" format="webp" %}">
```

More in [Using with Django](https://github.com/joncombe/opposable-thumbs/blob/main/docs/django.md).

### Flask

```python
from opposable_thumbs.flask import init_app

app.config["OPPOSABLE_THUMBS"] = {"roots": {"media": "/srv/media"}}
init_app(app)
```

```html
<img src="{{ thumbnail_url('media/photo.jpg', operations='fit,300,300|unsharp') }}">
```

More in [Using with Flask](https://github.com/joncombe/opposable-thumbs/blob/main/docs/flask.md).

### Python

```python
from opposable_thumbs import Config, make_thumbnail

config = Config(roots={"media": "/srv/media"})
thumbnail = make_thumbnail(
    config, file="media/photo.jpg", operations="fit,300,300", format="webp"
)
thumbnail.data  # the image, as bytes
```

More in [The Python API](https://github.com/joncombe/opposable-thumbs/blob/main/docs/python.md),
and for other web frameworks, see
[Using with another web framework](https://github.com/joncombe/opposable-thumbs/blob/main/docs/other-frameworks.md).

## Features

- 29 operations, including `fit`, `pad`, `cropratio`, `rotate`, `circle`,
  `rounded`, `unsharp` and colour adjustments, with JPEG, PNG, WebP, GIF,
  BMP and TIFF output.
- Signed URLs, so nobody can make up their own.
- Sources from named folders or allowed URLs only, with limits on download
  size, image size and work per request.
- Optional caches for downloaded sources and finished thumbnails, plus
  `ETag`, `Cache-Control` and `304 Not Modified` for browsers and CDNs.
- Faster, lower-memory decoding of large JPEGs, and EXIF orientation applied
  so phone photos come out upright.

## Documentation

- [Using with Django](https://github.com/joncombe/opposable-thumbs/blob/main/docs/django.md)
- [Using with Flask](https://github.com/joncombe/opposable-thumbs/blob/main/docs/flask.md)
- [Using with another web framework](https://github.com/joncombe/opposable-thumbs/blob/main/docs/other-frameworks.md)
- [The Python API](https://github.com/joncombe/opposable-thumbs/blob/main/docs/python.md):
  functions, results and errors
- [Operations and output](https://github.com/joncombe/opposable-thumbs/blob/main/docs/operations.md):
  every operation, query parameters, output formats, speed
- [Configuration](https://github.com/joncombe/opposable-thumbs/blob/main/docs/configuration.md):
  settings, allowed sources, signed URLs, limits
- [Caching](https://github.com/joncombe/opposable-thumbs/blob/main/docs/caching.md):
  the caches, cleaning them, and browser and CDN caching

The repository also has a playground for trying every operation in a
browser, and a guide to working on the project: see
[DEVELOP.md](https://github.com/joncombe/opposable-thumbs/blob/main/DEVELOP.md).

## Licence

BSD 3-Clause. See
[LICENCE](https://github.com/joncombe/opposable-thumbs/blob/main/LICENCE).
