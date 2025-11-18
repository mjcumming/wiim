"""Support to interface with WiiM players - sleep timer and alarm services."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

SERVICE_SET_SLEEP_TIMER = "set_sleep_timer"
SERVICE_CLEAR_SLEEP_TIMER = "clear_sleep_timer"
SERVICE_UPDATE_ALARM = "update_alarm"

ATTR_SLEEP_TIME = "sleep_time"
ATTR_ALARM_ID = "alarm_id"
ATTR_TIME = "time"
ATTR_TRIGGER = "trigger"
ATTR_OPERATION = "operation"


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register WiiM services."""

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
