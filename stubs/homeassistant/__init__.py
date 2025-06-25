"""Minimal stub package for Home Assistant to satisfy mypy during strict checks.
Only contains the bare names referenced by the WiiM custom component.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from enum import Enum
from types import ModuleType
from typing import Any, Generic, Optional, TypeVar


# ---------------------------------------------------------------------------
# Core – HomeAssistant object placeholder
# ---------------------------------------------------------------------------
class HomeAssistant:  # noqa: D101 – stub
    pass


core = ModuleType("homeassistant.core")
core.HomeAssistant = HomeAssistant  # type: ignore[attr-defined]
sys.modules["homeassistant.core"] = core


# ---------------------------------------------------------------------------
# config_entries – ConfigEntry placeholder
# ---------------------------------------------------------------------------
class ConfigEntry:  # noqa: D101 – stub
    entry_id: str | None = None
    unique_id: str | None = None
    title: str = "WiiM Speaker"
    data: dict[str, Any] = {}
    options: dict[str, Any] = {}


config_entries = ModuleType("homeassistant.config_entries")
config_entries.ConfigEntry = ConfigEntry  # type: ignore[attr-defined]
sys.modules["homeassistant.config_entries"] = config_entries

# ---------------------------------------------------------------------------
# helpers.update_coordinator – coordinator base + UpdateFailed
# ---------------------------------------------------------------------------
T = TypeVar("T")


class DataUpdateCoordinator(Generic[T]):  # noqa: D101 – stub
    def __init__(self, hass: HomeAssistant, logger: Any, name: str, update_interval: Any): ...


class UpdateFailed(Exception):  # noqa: D101 – stub
    pass


helpers_mod = ModuleType("homeassistant.helpers")
helpers_update_coord = ModuleType("homeassistant.helpers.update_coordinator")
helpers_update_coord.DataUpdateCoordinator = DataUpdateCoordinator  # type: ignore[attr-defined]
helpers_update_coord.UpdateFailed = UpdateFailed  # type: ignore[attr-defined]


# CoordinatorEntity base
class Entity:  # noqa: D101 – stub
    pass


# Define CoordinatorEntity now that Entity exists
class CoordinatorEntity(Entity): ...


helpers_update_coord.CoordinatorEntity = CoordinatorEntity  # type: ignore[attr-defined]

helpers_mod.update_coordinator = helpers_update_coord  # type: ignore[attr-defined]
sys.modules["homeassistant.helpers"] = helpers_mod
sys.modules["homeassistant.helpers.update_coordinator"] = helpers_update_coord


# ---------------------------------------------------------------------------
# helpers.entity – base Entity + EntityCategory enum placeholder
# ---------------------------------------------------------------------------
class EntityCategory:  # noqa: D101 – stub
    DIAGNOSTIC = "diagnostic"
    CONFIG = "config"


helpers_entity_mod = ModuleType("homeassistant.helpers.entity")
helpers_entity_mod.Entity = Entity  # type: ignore[attr-defined]
helpers_entity_mod.EntityCategory = EntityCategory  # type: ignore[attr-defined]
sys.modules["homeassistant.helpers.entity"] = helpers_entity_mod

# ---------------------------------------------------------------------------
# Component base entity classes (sensor, switch, media_player, etc.)
# ---------------------------------------------------------------------------
components_mod = ModuleType("homeassistant.components")
sys.modules["homeassistant.components"] = components_mod

# Explicit component entity stubs so mypy treats them as concrete classes


class SensorEntity(Entity): ...


class SwitchEntity(Entity): ...


class MediaPlayerEntity(Entity): ...


class LightEntity(Entity): ...


class ButtonEntity(Entity): ...


class BinarySensorEntity(Entity): ...


class NumberEntity(Entity): ...


class UpdateEntity(Entity): ...


_component_mapping = {
    "sensor": SensorEntity,
    "switch": SwitchEntity,
    "media_player": MediaPlayerEntity,
    "light": LightEntity,
    "button": ButtonEntity,
    "binary_sensor": BinarySensorEntity,
    "number": NumberEntity,
    "update": UpdateEntity,
}

for mod_name, cls in _component_mapping.items():
    mod = ModuleType(f"homeassistant.components.{mod_name}")
    setattr(mod, cls.__name__, cls)
    sys.modules[f"homeassistant.components.{mod_name}"] = mod

# Special: media_player.MediaPlayerState enum stub
media_player_mod = sys.modules["homeassistant.components.media_player"]


class MediaPlayerState:  # noqa: D101 – stub
    PLAYING = "playing"
    PAUSED = "paused"
    IDLE = "idle"


media_player_mod.MediaPlayerState = MediaPlayerState

# ---------------------------------------------------------------------------
# homeassistant.const – common constants
# ---------------------------------------------------------------------------
const_mod = ModuleType("homeassistant.const")
const_mod.CONF_HOST = "host"
const_mod.EntityCategory = EntityCategory


# ---------------------------------------------------------------------------
# homeassistant.const.Platform – core supported platforms (subset)
# ---------------------------------------------------------------------------
class Platform(str, Enum):  # noqa: D101 – stub
    SENSOR = "sensor"
    SWITCH = "switch"
    MEDIA_PLAYER = "media_player"
    LIGHT = "light"
    BUTTON = "button"
    BINARY_SENSOR = "binary_sensor"
    NUMBER = "number"
    UPDATE = "update"


const_mod.Platform = Platform

sys.modules["homeassistant.const"] = const_mod

# ---------------------------------------------------------------------------
# CoordinatorEntity + UpdateEntity stubs
# ---------------------------------------------------------------------------

update_mod = ModuleType("homeassistant.components.update")
update_mod.UpdateEntity = type("UpdateEntity", (Entity,), {})
sys.modules["homeassistant.components.update"] = update_mod

# ---------------------------------------------------------------------------
# homeassistant.exceptions – exception stubs
# ---------------------------------------------------------------------------


class HomeAssistantError(Exception):
    """Base class for Home Assistant exceptions (stub)."""


class ConfigEntryNotReady(HomeAssistantError):
    """Raised when a config entry isn't ready (stub)."""


exceptions_mod = ModuleType("homeassistant.exceptions")
exceptions_mod.HomeAssistantError = HomeAssistantError  # type: ignore[attr-defined]
exceptions_mod.ConfigEntryNotReady = ConfigEntryNotReady  # type: ignore[attr-defined]

sys.modules["homeassistant.exceptions"] = exceptions_mod

# ---------------------------------------------------------------------------
# helpers.aiohttp_client – return dummy aiohttp session
# ---------------------------------------------------------------------------

helpers_aiohttp_client_mod = ModuleType("homeassistant.helpers.aiohttp_client")


async def async_get_clientsession(hass: HomeAssistant):  # noqa: D101 – stub
    class DummyClientSession:  # minimal dummy aiohttp client session
        async def close(self):
            return None

    return DummyClientSession()


helpers_aiohttp_client_mod.async_get_clientsession = async_get_clientsession  # type: ignore[attr-defined]

helpers_mod.aiohttp_client = helpers_aiohttp_client_mod  # type: ignore[attr-defined]
sys.modules["homeassistant.helpers.aiohttp_client"] = helpers_aiohttp_client_mod

# Add `callback` decorator used by HA for synchronous callbacks


def callback(func):  # noqa: D401, D103 – simple pass-through decorator
    return func


core.callback = callback

# ---------------------------------------------------------------------------
# homeassistant.data_entry_flow – FlowResult type alias
# ---------------------------------------------------------------------------

data_entry_flow_mod = ModuleType("homeassistant.data_entry_flow")


class FlowResult(dict):  # noqa: D101 – stub acts like dict
    pass


data_entry_flow_mod.FlowResult = FlowResult  # type: ignore[attr-defined]
sys.modules["homeassistant.data_entry_flow"] = data_entry_flow_mod
