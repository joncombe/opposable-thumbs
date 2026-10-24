from functools import cache

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.signals import setting_changed
from django.dispatch import receiver
from django.utils.crypto import salted_hmac

from opposable_thumbs import Config, ConfigError


@cache
def get_config():
    """The Config from settings.OPPOSABLE_THUMBS, a dict of Config settings.

    Unless it sets secret_key, URLs are signed with a key made from
    settings.SECRET_KEY (not SECRET_KEY itself), so they need no setting.
    """
    options = dict(getattr(settings, "OPPOSABLE_THUMBS", {}))
    options.setdefault(
        "secret_key",
        salted_hmac("opposable_thumbs", "signing", algorithm="sha256").hexdigest(),
    )
    try:
        return Config(**options)
    except (TypeError, ConfigError) as e:
        raise ImproperlyConfigured(f"OPPOSABLE_THUMBS: {e}") from e


@receiver(setting_changed)
def _settings_changed(setting, **kwargs):
    # e.g. override_settings in tests
    if setting in ("OPPOSABLE_THUMBS", "SECRET_KEY"):
        get_config.cache_clear()
