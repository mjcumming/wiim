"""WiiM API modular façade.

This lightweight wrapper keeps public import path (`custom_components.wiim.api.WiiMClient`) stable while we
incrementally carve out functionality into smaller `api_*` modules.  It composes the
(new) mixin classes with the original, feature-complete legacy client (now located
in `api_base.py`) so nothing breaks during the transition.
"""

from __future__ import annotations

from .api_base import (
    WiiMClient as _LegacyClient,
)
from .api_base import (
    WiiMConnectionError,
    WiiMError,
    WiiMInvalidDataError,
    WiiMRequestError,
    WiiMResponseError,
    WiiMTimeoutError,
)

# Order is important: mixins first, legacy client last so their `__init__` is called
# exactly once via Python's MRO.
from .api_device import DeviceAPI
from .api_diag import DiagnosticsAPI
from .api_eq import EQAPI
from .api_group import GroupAPI
from .api_playback import PlaybackAPI
from .api_preset import PresetAPI


class WiiMClient(
    DeviceAPI,
    PlaybackAPI,
    GroupAPI,
    EQAPI,
    PresetAPI,
    DiagnosticsAPI,
    _LegacyClient,
):
    """Aggregated WiiM HTTP API client – modular in the future, legacy compatible today."""

    # No additional code – all behaviour lives in the mixins or the legacy client.
    pass


# after class definition, export exceptions for `from .api import` compatibility
__all__ = [
    "WiiMClient",
    "WiiMError",
    "WiiMRequestError",
    "WiiMResponseError",
    "WiiMTimeoutError",
    "WiiMConnectionError",
    "WiiMInvalidDataError",
]
