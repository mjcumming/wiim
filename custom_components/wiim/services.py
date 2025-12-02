"""Support to interface with WiiM players - platform entity actions.

This module registers WiiM-specific actions using the recommended
service.async_register_platform_entity_service() pattern, which provides
proper target entity selection in the Home Assistant UI.
"""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import service

from .const import DOMAIN

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


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register WiiM platform entity actions.

    Uses service.async_register_platform_entity_service() for proper
    Home Assistant UI integration with target entity selection.
    """

    # Sleep Timer
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_SLEEP_TIMER,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={vol.Required(ATTR_SLEEP_TIME): vol.All(vol.Coerce(int), vol.Range(min=0, max=7200))},
        func="set_sleep_timer",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CLEAR_SLEEP_TIMER,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="clear_sleep_timer",
    )

    # Alarms
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_UPDATE_ALARM,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            vol.Required(ATTR_ALARM_ID): vol.All(vol.Coerce(int), vol.Range(min=0, max=2)),
            vol.Optional(ATTR_TIME): cv.string,
            vol.Optional(ATTR_TRIGGER): cv.string,
            vol.Optional(ATTR_OPERATION): cv.string,
        },
        func="set_alarm",
    )

    # Device Management - now as proper entity actions
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_REBOOT_DEVICE,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="async_reboot_device",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SYNC_TIME,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="async_sync_time",
    )

    # Unofficial API actions (may not work on all firmware versions)
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SCAN_BLUETOOTH,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            vol.Optional(ATTR_DURATION, default=5): vol.All(vol.Coerce(int), vol.Range(min=3, max=10)),
        },
        func="async_scan_bluetooth",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_CHANNEL_BALANCE,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            vol.Required(ATTR_BALANCE): vol.All(vol.Coerce(float), vol.Range(min=-1.0, max=1.0)),
        },
        func="async_set_channel_balance",
    )
