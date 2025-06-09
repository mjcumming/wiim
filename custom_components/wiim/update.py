from __future__ import annotations

"""Firmware update entity for WiiM devices.

LinkPlay exposes only an *availability flag* (VersionUpdate/NewVer) – there is no
public API to download or stage firmware.  On devices that already downloaded
a new release, issuing a normal `reboot` starts the update process.  Therefore
`async_install()` simply reboots the speaker when the user presses *Install*.
"""

import logging
from typing import Any

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    FIRMWARE_KEY,
    LATEST_VERSION_KEY,
    UPDATE_AVAILABLE_KEY,
)
from .data import Speaker, get_speaker_from_config_entry
from .entity import WiimEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the firmware UpdateEntity from config entry."""
    speaker = get_speaker_from_config_entry(hass, config_entry)
    async_add_entities([WiiMFirmwareUpdateEntity(speaker)])


class WiiMFirmwareUpdateEntity(WiimEntity, UpdateEntity):
    """Represents a firmware update offered by the speaker."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = UpdateEntityFeature.INSTALL

    def __init__(self, speaker: Speaker) -> None:
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_fw_update"
        self._attr_name = "Firmware Update"

    # ------------- UpdateEntity required properties -------------

    @property
    def installed_version(self) -> str | None:  # type: ignore[override]
        info: dict[str, Any] = self.speaker.coordinator.data.get("device_info", {})
        return info.get(FIRMWARE_KEY)

    @property
    def latest_version(self) -> str | None:  # type: ignore[override]
        info: dict[str, Any] = self.speaker.coordinator.data.get("device_info", {})
        return info.get(LATEST_VERSION_KEY)

    @property
    def available(self) -> bool:  # type: ignore[override]
        info: dict[str, Any] = self.speaker.coordinator.data.get("device_info", {})
        return bool(info.get(UPDATE_AVAILABLE_KEY))

    # ------------- Optional actions -------------

    async def async_install(self, version: str | None, backup: bool, **kwargs) -> None:  # type: ignore[override]
        """Attempt to start firmware installation by rebooting the device."""
        _LOGGER.info("User requested firmware install on %s (version=%s)", self.speaker.name, version)

        try:
            await self.speaker.coordinator.client.reboot()
            _LOGGER.info("Reboot command sent to %s – speaker will install firmware if staged.", self.speaker.name)
        except Exception as err:  # pragma: no cover – network errors
            _LOGGER.error("Failed to trigger firmware install on %s: %s", self.speaker.name, err)
            raise
