class ConfigError(ValueError):
    """A Config setting is invalid."""


class ThumbnailError(Exception):
    """save_thumbnail() couldn't make the thumbnail.

    `errors` lists every problem found, and `status` is the HTTP status code
    make_thumbnail() would have returned for them.
    """

    def __init__(self, errors, status):
        super().__init__("\n".join(errors))
        self.errors = tuple(errors)
        self.status = status
