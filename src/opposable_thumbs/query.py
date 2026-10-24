"""The query string format: parsed by handle_request(), built by
thumbnail_query().

e.g. file=media/a.jpg&p=cropratio,1|resize,300,300&format=webp&s=<signature>
"""

import base64
import hashlib
import hmac
import json
import os
from collections.abc import Mapping
from urllib.parse import parse_qsl, urlencode

from .errors import ConfigError

# between operations in p=, and between an operation's name and arguments
OPERATION_SEPARATOR = "|"
ARGUMENT_SEPARATOR = ","

# the query parameter holding the signature
SIGNATURE = "s"


def split_operations(p):
    # the operations in a p= string, e.g. "fit,300,300|grayscale"
    return (
        [op.split(ARGUMENT_SEPARATOR) for op in p.split(OPERATION_SEPARATOR)]
        if p
        else []
    )


def normalise_operations(operations):
    # operations as lists of strings, from Python values: a list of names on
    # their own or sequences of a name and its arguments, e.g.
    # ["blur", ("resize", 300, 300)], or a string as in p=, e.g.
    # "blur|resize,300,300". the operations convert the arguments back
    if isinstance(operations, str):
        return split_operations(operations)
    return [
        [op] if isinstance(op, str) else [str(part) for part in op] or [""]
        for op in operations
    ]


def parse_query(query):
    """The arguments a query string (or a mapping of its parameters) asks for."""
    if isinstance(query, Mapping):
        params = {str(k): str(v) for k, v in query.items()}
    else:
        # parse_qsl splits on & and = before decoding each value, so an
        # encoded & or = inside a value (e.g. a url with its own query string)
        # is kept. if a key repeats, the last value wins
        params = dict(parse_qsl(str(query).lstrip("?"), keep_blank_values=True))

    return {
        "file": params.get("file"),
        "url": params.get("url"),
        "operations": split_operations(params.get("p")),
        "format": params.get("format"),
        "quality": params.get("quality"),
        "signature": params.get(SIGNATURE),
    }


def signing_key(config):
    # the key to sign and check URLs with, or None if they aren't signed
    if not config.signed_urls:
        return None
    if not config.secret_key:
        raise ConfigError(
            "Signed URLs need a secret_key in the Config, or set signed_urls=False"
        )
    key = config.secret_key
    return key.encode("utf-8") if isinstance(key, str) else key


def sign(key, parsed):
    # the signature for what parse_query() returned. the parsed values are
    # signed, not the query string, so parameter order, encoding and other
    # parameters don't change it
    values = [parsed[name] for name in ("file", "url", "operations", "format")]
    values.append(parsed["quality"])
    message = json.dumps(values).encode("utf-8")
    digest = hmac.new(key, message, hashlib.sha256).digest()
    # 128 bits is plenty, and keeps URLs short
    return base64.urlsafe_b64encode(digest[:16]).rstrip(b"=").decode("ascii")


def is_signed(key, parsed):
    # compared as bytes, as compare_digest refuses non-ASCII strings
    expected = sign(key, parsed).encode("ascii")
    given = (parsed["signature"] or "").encode("utf-8")
    return hmac.compare_digest(expected, given)


def thumbnail_query(
    config, *, file=None, url=None, operations=(), format=None, quality=None
):
    """The query string that asks handle_request() for this thumbnail.

    Takes the same arguments as make_thumbnail(), e.g.

        thumbnail_query(config, file="media/a.jpg", operations=[("fit", 300, 300)])

    and returns e.g. "file=media/a.jpg&p=fit,300,300&s=<signature>", with
    every value encoded as needed. It is signed with config.secret_key unless
    config.signed_urls is False. Nothing else is checked against the Config
    here; that happens when the query is handled.
    """
    params = {}
    if file is not None:
        params["file"] = os.fspath(file)
    if url is not None:
        params["url"] = url

    ops = normalise_operations(operations)
    for part in (part for op in ops for part in op):
        if OPERATION_SEPARATOR in part or ARGUMENT_SEPARATOR in part:
            raise ValueError(
                f"Operation names and arguments can't contain "
                f'"{OPERATION_SEPARATOR}" or "{ARGUMENT_SEPARATOR}": {part!r}'
            )
    if ops:
        params["p"] = OPERATION_SEPARATOR.join(
            ARGUMENT_SEPARATOR.join(op) for op in ops
        )

    if format is not None:
        params["format"] = str(format)
    if quality is not None:
        params["quality"] = str(quality)

    # signed as handle_request() will parse it, so the two always agree
    key = signing_key(config)
    if key is not None:
        params[SIGNATURE] = sign(key, parse_query(params))

    # / , and : are left as they are, so the result stays readable
    return urlencode(params, safe="/,:")
