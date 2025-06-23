"""Device registry stub."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


def async_get(hass):  # noqa: D401
    return DeviceRegistry()


@dataclass
class DeviceEntry:
    id: str
    identifiers: set[Any]
    name: str | None = None


@dataclass
class DeviceInfo:
    identifiers: set[Any]
    manufacturer: str | None = None
    model: str | None = None
    name: str | None = None
    sw_version: str | None = None


class DeviceRegistry:
    def async_get_or_create(self, **kwargs):  # noqa: D401
        return DeviceEntry(id="stub", identifiers=set())
