"""WiiM API modular façade.

This lightweight wrapper keeps public import path (`custom_components.wiim.api.WiiMClient`) stable while we
incrementally carve out functionality into smaller `api_*` modules.  It composes the
(new) mixin classes with the original, feature-complete legacy client (now located
in `api_base.py`) so nothing breaks during the transition.
"""

from __future__ import annotations

from .api_audio_settings import AudioSettingsAPI
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

# Unofficial API mixins (reverse-engineered endpoints)
from .api_bluetooth import BluetoothAPI

# Order is important: mixins first, legacy client last so their `__init__` is called
# exactly once via Python's MRO.
# Phase-1 refactor: core mixins extracted.
# mixins included - official and unofficial endpoints
from .api_device import DeviceAPI
from .api_diag import DiagnosticsAPI
from .api_eq import EQAPI
from .api_group import GroupAPI
from .api_lms import LMSAPI
from .api_misc import MiscAPI
from .api_playback import PlaybackAPI
from .api_preset import PresetAPI

# Placeholder imports for future mixins (not yet implemented).
# from .api_group import GroupAPI        # noqa: ERA001
# from .api_eq import EQAPI             # noqa: ERA001
# from .api_preset import PresetAPI     # noqa: ERA001
# from .api_diag import DiagnosticsAPI   # noqa: ERA001


class WiiMClient(
    BluetoothAPI,
    AudioSettingsAPI,
    LMSAPI,
    MiscAPI,
    DeviceAPI,
    PlaybackAPI,
    EQAPI,
    GroupAPI,
    PresetAPI,
    DiagnosticsAPI,
    _LegacyClient,
):
    """Aggregated WiiM HTTP API client – modular with official and unofficial endpoints.

    This client includes both official WiiM HTTP API endpoints and unofficial
    reverse-engineered endpoints. The unofficial endpoints may not be available
    on all firmware versions or device models.

    Unofficial API modules:
    - BluetoothAPI: Device discovery and scanning
    - AudioSettingsAPI: SPDIF settings, channel balance
    - LMSAPI: Squeezelite/Lyrion Music Server integration
    - MiscAPI: Button controls, alternative LED methods
    """

    # No additional code – all behaviour lives in the mixins or the legacy client.


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
