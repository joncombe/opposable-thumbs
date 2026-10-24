from django import template

from ..views import thumbnail_url as _thumbnail_url

register = template.Library()


@register.simple_tag
def thumbnail_url(file=None, p="", *, url=None, format=None, quality=None):
    """The signed URL of a thumbnail, e.g.

    {% thumbnail_url "media/a.jpg" "fit,300,300|grayscale" format="webp" %}

    The operations are written as in the p= query parameter.
    """
    return _thumbnail_url(file, url=url, operations=p, format=format, quality=quality)
