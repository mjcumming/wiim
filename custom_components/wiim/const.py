"""Constants for the WiiM integration - minimal HA-specific constants only.

All API endpoints and device communication are handled by pywiim.
This file only contains Home Assistant integration constants.
"""

from __future__ import annotations

from homeassistant.const import CONF_HOST  # noqa: F401

DOMAIN = "wiim"

# HA-specific config option keys (not from pywiim)
CONF_VOLUME_STEP = "volume_step"
CONF_VOLUME_STEP_PERCENT = "volume_step_percent"
CONF_ENABLE_MAINTENANCE_BUTTONS = "enable_maintenance_buttons"
CONF_ENABLE_NETWORK_MONITORING = "enable_network_monitoring"

# HA-specific defaults (not from pywiim)
DEFAULT_VOLUME_STEP = 0.05
DEFAULT_DEVICE_NAME = "WiiM Speaker"
