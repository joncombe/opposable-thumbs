# Using with another web framework

There are integrations for [Django](django.md) and [Flask](flask.md). For
anything else, route a URL, e.g. `/thumb`, to a function that:

1. passes the request's query string (and its `If-None-Match` header, if
   any) to [`handle_request()`](python.md#handle_request), and
2. sends back the result's `status`, `headers` and `body`.

Your pages then use URLs made by
[`thumbnail_query()`](#building-thumbnail-urls), which are
[signed](configuration.md#signed-urls) so nobody can make up their own.
That's all. In a plain WSGI app:

```python
from opposable_thumbs import Config, handle_request

config = Config(
    roots={"media": "/srv/media"},
    secret_key=SECRET_KEY,  # a long random string, kept private
    output_cache_dir="/srv/cache",
)


def app(environ, start_response):
    result = handle_request(
        config,
        environ.get("QUERY_STRING", ""),
        if_none_match=environ.get("HTTP_IF_NONE_MATCH"),
    )
    start_response(result.status_line, list(result.headers.items()))
    return [result.body]
```

Every framework gives you the query string and headers, and a way to return
a status, headers and body, so the same few lines work anywhere. If your
framework has already parsed the query string, you can pass a dict of its
parameters instead.

- `handle_request()` never raises for a bad request: it returns a `Result`
  with an error status and the error messages as the body. See
  [Errors](python.md#errors).
- A `304 Not Modified` result has no `Content-Type`. Make sure your framework
  doesn't add one.
- Make one `Config` when your app starts and reuse it. It can't be changed
  after it is made, so it is safe to share between threads.

## Building thumbnail URLs

[`thumbnail_query()`](python.md#thumbnail_query) takes the same arguments as
`make_thumbnail()` and returns the query string that asks for that
thumbnail, signed and with every value encoded as needed. Call it with the
same `Config` as `handle_request()` when you render a page:

```python
from opposable_thumbs import thumbnail_query

src = "/thumb?" + thumbnail_query(
    config,
    file="media/photo.jpg",
    operations=[("cropratio", 1), ("resize", 300, 300)],
    format="webp",
)
# /thumb?file=media/photo.jpg&p=cropratio,1%7Cresize,300,300&format=webp&s=...
```

A thumbnail made with `make_thumbnail()` and the same one asked for in a
query string are identical, and share an entry in the output cache.

## Writing an integration

If you'd like to package one for others, see
[Adding a framework integration](../DEVELOP.md#adding-a-framework-integration).
