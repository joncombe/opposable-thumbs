"""Django integration: pip install opposable-thumbs[django].

Add "opposable_thumbs.django" to INSTALLED_APPS, set OPPOSABLE_THUMBS in your
settings and include "opposable_thumbs.django.urls" in your URLconf. See the
README for the details.
"""

try:
    import django  # noqa: F401
except ImportError as e:
    raise ImportError(
        "opposable_thumbs.django needs Django: pip install opposable-thumbs[django]"
    ) from e
