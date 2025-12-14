"""Support to interface with WiiM players - platform entity actions.

This module provides entity service descriptions for WiiM-specific services.
Services are registered via EntityServiceDescription pattern in media_player.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import voluptuous as vol
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.typing import VolDictType, VolSchemaType

# Service names
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
SCHEMA_SET_SLEEP_TIMER: Final[VolDictType] = {
    vol.Required(ATTR_SLEEP_TIME): vol.All(vol.Coerce(int), vol.Range(min=0, max=7200))
}

SCHEMA_UPDATE_ALARM: Final[VolDictType] = {
    vol.Required(ATTR_ALARM_ID): vol.All(vol.Coerce(int), vol.Range(min=0, max=2)),
    vol.Optional(ATTR_TIME): cv.string,
    vol.Optional(ATTR_TRIGGER): cv.string,
    vol.Optional(ATTR_OPERATION): cv.string,
}

SCHEMA_SCAN_BLUETOOTH: Final[VolDictType] = {
    vol.Optional(ATTR_DURATION, default=5): vol.All(vol.Coerce(int), vol.Range(min=3, max=10))
}

SCHEMA_SET_CHANNEL_BALANCE: Final[VolDictType] = {
    vol.Required(ATTR_BALANCE): vol.All(vol.Coerce(float), vol.Range(min=-1.0, max=1.0))
}


@dataclass(frozen=True)
class EntityServiceDescription:
    """Describe an entity service for WiiM platform."""

    name: str
    method_name: str
    schema: VolDictType | VolSchemaType | None = None
    supports_response: SupportsResponse = SupportsResponse.NONE

    def async_register(self, platform: entity_platform.EntityPlatform) -> None:
        """Register the service with the platform."""
        platform.async_register_entity_service(
            self.name,
            self.schema,
            self.method_name,
            supports_response=self.supports_response,
        )


# All WiiM platform entity services
MEDIA_PLAYER_ENTITY_SERVICES: Final = (
    # Sleep timer services
    EntityServiceDescription(
        SERVICE_SET_SLEEP_TIMER,
        "set_sleep_timer",
        SCHEMA_SET_SLEEP_TIMER,
    ),
    EntityServiceDescription(
        SERVICE_CLEAR_SLEEP_TIMER,
        "clear_sleep_timer",
    ),
    # Alarm services
    EntityServiceDescription(
        SERVICE_UPDATE_ALARM,
        "set_alarm",
        SCHEMA_UPDATE_ALARM,
    ),
    # Device management services
    EntityServiceDescription(
        SERVICE_REBOOT_DEVICE,
        "async_reboot_device",
    ),
    EntityServiceDescription(
        SERVICE_SYNC_TIME,
        "async_sync_time",
    ),
    EntityServiceDescription(
        SERVICE_SCAN_BLUETOOTH,
        "async_scan_bluetooth",
        SCHEMA_SCAN_BLUETOOTH,
    ),
    EntityServiceDescription(
        SERVICE_SET_CHANNEL_BALANCE,
        "async_set_channel_balance",
        SCHEMA_SET_CHANNEL_BALANCE,
    ),
)


def register_media_player_services(platform: entity_platform.EntityPlatform | None = None) -> None:
    """Register media_player entity services using the new EntityServiceDescription pattern.

    This should be called from media_player.async_setup_entry() after entities are added.

    Args:
        platform: The entity platform. If None, will try to get current platform.
    """
    if platform is None:
        platform = entity_platform.async_get_current_platform()
    for service in MEDIA_PLAYER_ENTITY_SERVICES:
        service.async_register(platform)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Legacy function for backward compatibility.

    Services are now registered via register_media_player_services() in media_player.py.
    This function is kept for API compatibility but does nothing.
    """
    # Services are registered via EntityServiceDescription pattern in media_player.py
    pass
