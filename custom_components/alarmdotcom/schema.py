"""Use the schema library shipped by the running Home Assistant release."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import probatio as vol
else:
    try:
        import probatio as vol
    except ImportError:
        # Home Assistant before 2026.10 ships Voluptuous instead.
        import voluptuous as vol

__all__ = ["vol"]
