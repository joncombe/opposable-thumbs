from django.http import HttpResponse
from django.urls import reverse
from django.views.decorators.http import require_safe

from opposable_thumbs import handle_request, thumbnail_query

from .conf import get_config


@require_safe
def thumbnail(request):
    result = handle_request(
        get_config(),
        request.META.get("QUERY_STRING", ""),
        if_none_match=request.headers.get("If-None-Match"),
    )
    response = HttpResponse(result.body, status=result.status)
    for name, value in result.headers.items():
        response[name] = value
    if "Content-Type" not in result.headers:
        # a 304 has none, and Django would otherwise add text/html
        del response["Content-Type"]
    return response


def thumbnail_url(file=None, *, url=None, operations=(), format=None, quality=None):
    """The URL of a thumbnail, signed, for use in views and templates.

    Takes the same arguments as make_thumbnail(), e.g.
    thumbnail_url("media/a.jpg", operations=[("fit", 300, 300)]).
    """
    query = thumbnail_query(
        get_config(),
        file=file,
        url=url,
        operations=operations,
        format=format,
        quality=quality,
    )
    return f"{reverse('opposable_thumbs:thumbnail')}?{query}"
