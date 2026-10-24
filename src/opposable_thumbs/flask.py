"""Flask integration: pip install opposable-thumbs[flask].

    from opposable_thumbs.flask import init_app

    app.config["OPPOSABLE_THUMBS"] = {"roots": {"media": "/srv/media"}}
    init_app(app)

See the README for the details.
"""

import hashlib
import hmac

try:
    import click
    from flask import Response, current_app, request, url_for
except ImportError as e:
    raise ImportError(
        "opposable_thumbs.flask needs Flask: pip install opposable-thumbs[flask]"
    ) from e

from opposable_thumbs import Config, clean_cache, handle_request, thumbnail_query

EXTENSION = "opposable_thumbs"


def init_app(app, url="/thumb", config=None):
    """Serve thumbnails at `url`, and add thumbnail_url() to templates.

    The Config is `config` if given, otherwise made from
    app.config["OPPOSABLE_THUMBS"], a dict of Config settings. Unless that
    sets secret_key, URLs are signed with a key made from app.secret_key (not
    app.secret_key itself).
    """
    if config is None:
        options = dict(app.config.get("OPPOSABLE_THUMBS", {}))
        if "secret_key" not in options and app.secret_key:
            secret = app.secret_key
            if isinstance(secret, str):
                secret = secret.encode("utf-8")
            options["secret_key"] = hmac.new(
                secret, b"opposable_thumbs.signing", hashlib.sha256
            ).hexdigest()
        config = Config(**options)

    app.extensions[EXTENSION] = config
    app.add_url_rule(url, endpoint=EXTENSION, view_func=_thumbnail)
    app.add_template_global(thumbnail_url)

    @app.cli.command("clean-thumbnail-cache")
    @click.option("--all", "all_", is_flag=True, help="Delete every cached file.")
    @click.option(
        "--max-size",
        help="The size to keep each folder under, e.g. 5GB, instead of cache_max_size.",
    )
    def clean_thumbnail_cache(all_, max_size):
        """Delete expired files from the thumbnail cache folders, then the
        oldest files in any folder bigger than cache_max_size."""
        try:
            deleted = clean_cache(config, all=all_, max_size=max_size)
        except ValueError as e:
            raise click.BadParameter(str(e), param_hint="--max-size") from e
        click.echo(f"Deleted {deleted} cached file(s)")


def _thumbnail():
    result = handle_request(
        current_app.extensions[EXTENSION],
        request.query_string.decode("utf-8", errors="replace"),
        if_none_match=request.headers.get("If-None-Match"),
    )
    response = Response(result.body, status=result.status, headers=result.headers)
    if "Content-Type" not in result.headers:
        # a 304 has none, and Flask would otherwise add text/html
        del response.headers["Content-Type"]
    return response


def thumbnail_url(file=None, *, url=None, operations=(), format=None, quality=None):
    """The URL of a thumbnail, signed, for use in views and templates.

    Takes the same arguments as make_thumbnail(), e.g. in a template
    {{ thumbnail_url("media/a.jpg", operations="fit,300,300|grayscale") }}.
    """
    query = thumbnail_query(
        current_app.extensions[EXTENSION],
        file=file,
        url=url,
        operations=operations,
        format=format,
        quality=quality,
    )
    return f"{url_for(EXTENSION)}?{query}"
