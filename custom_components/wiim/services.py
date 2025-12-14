"""Support to interface with WiiM players - platform entity actions.

This module provides action schemas for WiiM-specific services.
The actual service registration happens in the platform setup (media_player.py).
"""

from __future__ import annotations

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

# Action names
SERVICE_SET_SLEEP_TIMER = "set_sleep_timer"
SERVICE_CLEAR_SLEEP_TIMER = "clear_sleep_timer"
SERVICE_UPDATE_ALARM = "update_alarm"
SERVICE_REBOOT_DEVICE = "reboot_device"
SERVICE_SYNC_TIME = "sync_time"
SERVICE_SCAN_BLUETOOTH = "scan_bluetooth"
SERVICE_SET_CHANNEL_BALANCE = "set_channel_balance"

# Attribute names
ATTR_SLEEP_TIME = "sleep_time"
ATTR_ALARM_ID = "alarm_id"
ATTR_TIME = "time"
ATTR_TRIGGER = "trigger"
ATTR_OPERATION = "operation"
ATTR_DURATION = "duration"
ATTR_BALANCE = "balance"

# Service schemas
SCHEMA_SET_SLEEP_TIMER = {vol.Required(ATTR_SLEEP_TIME): vol.All(vol.Coerce(int), vol.Range(min=0, max=7200))}

SCHEMA_UPDATE_ALARM = {
    vol.Required(ATTR_ALARM_ID): vol.All(vol.Coerce(int), vol.Range(min=0, max=2)),
    vol.Optional(ATTR_TIME): cv.string,
    vol.Optional(ATTR_TRIGGER): cv.string,
    vol.Optional(ATTR_OPERATION): cv.string,
}

SCHEMA_SCAN_BLUETOOTH = {vol.Optional(ATTR_DURATION, default=5): vol.All(vol.Coerce(int), vol.Range(min=3, max=10))}

SCHEMA_SET_CHANNEL_BALANCE = {vol.Required(ATTR_BALANCE): vol.All(vol.Coerce(float), vol.Range(min=-1.0, max=1.0))}


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register WiiM platform entity actions.

    Note: Service registration is temporarily disabled while we migrate
    to the new Home Assistant service API.
    
    Services are still available via the entity methods directly.
    This function exists for API compatibility but does not register services.
    """
    # TODO: Migrate to new HA service registration API
    # Services are still available via the entity methods directly
    pass
