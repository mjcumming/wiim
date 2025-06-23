"""Stub for homeassistant.config_entries used in unit tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ConfigFlow:  # minimal for import
    def __init_subclass__(cls, **kwargs):  # noqa: D401
        # Ignore custom kwargs like 'domain' used by HA
        return


@dataclass
class ConfigEntry:
    entry_id: str
    data: dict[str, Any]
    title: str = "Stub Entry"

    async def async_setup(self, hass):  # noqa: D401
        return True

    async def async_unload(self, hass):  # noqa: D401
        return True


class OptionsFlow:
    def __init__(self, config_entry):
        self.config_entry = config_entry
