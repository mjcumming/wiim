"""Minimal speaker wrapper - just holds coordinator reference.

All device logic is in pywiim. Entities read directly from coordinator.data.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.device_registry import DeviceInfo as HADeviceInfo

from .const import DOMAIN
from .models import DeviceInfo

if TYPE_CHECKING:
    from .coordinator import WiiMCoordinator

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "Speaker",
    "get_speaker_from_config_entry",
    "find_speaker_by_uuid",
    "find_speaker_by_ip",
    "get_all_speakers",
]


class Speaker:
    """Minimal speaker wrapper - pywiim handles everything."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: WiiMCoordinator,
        config_entry: ConfigEntry,
    ):
        """Initialize speaker."""
        self.hass = hass
        self.coordinator = coordinator
        self.config_entry = config_entry
        self._uuid: str = self.config_entry.unique_id or self.coordinator.player.host
        self.device_info: HADeviceInfo | None = None

    async def async_setup(self, entry: ConfigEntry) -> None:
        """Complete async setup."""
        await self._register_ha_device(entry)

    @property
    def uuid(self) -> str:
        """Return unique identifier."""
        return self._uuid

    @property
    def name(self) -> str:
        """Return device name from Player."""
        if self.coordinator.data:
            player = self.coordinator.data.get("player")
            if player and player.device_info and player.device_info.name:
                return player.device_info.name
        return self.config_entry.title or "WiiM Speaker"

    @property
    def model(self) -> str:
        """Return device model from Player."""
        if self.coordinator.data:
            player = self.coordinator.data.get("player")
            if player and player.device_info and player.device_info.model:
                return player.device_info.model
        return "WiiM Speaker"

    @property
    def firmware(self) -> str | None:
        """Return firmware version from Player."""
        if self.coordinator.data:
            player = self.coordinator.data.get("player")
            if player and player.device_info and player.device_info.firmware:
                return player.device_info.firmware
        return None

    @property
    def ip_address(self) -> str:
        """Return IP address."""
        return self.coordinator.player.host

    @property
    def mac_address(self) -> str | None:
        """Return MAC address from device model."""
        device_model = self.device_model
        if device_model and device_model.mac:
            return device_model.mac
        return None

    @property
    def role(self) -> str | None:
        """Return role reported by pywiim Player."""
        player = getattr(self.coordinator, "player", None)
        if player:
            return player.role
        return None

    @property
    def available(self) -> bool:
        """Return if speaker is available."""
        return self.coordinator.last_update_success

    @property
    def device_model(self) -> DeviceInfo | None:
        """Return device model from Player."""
        if self.coordinator and self.coordinator.data:
            player = self.coordinator.data.get("player")
            if player and player.device_info:
                return player.device_info
        return None

    @property
    def input_list(self) -> list[str] | None:
        """Return input list from Player."""
        if self.coordinator and self.coordinator.data:
            player = self.coordinator.data.get("player")
            if player and player.device_info and player.device_info.input_list:
                return player.device_info.input_list
        return None

    def async_write_entity_states(self) -> None:
        """Notify entities of state changes - handled by CoordinatorEntity."""
        pass

    async def _register_ha_device(self, entry: ConfigEntry) -> None:
        """Register device in HA registry.

        Device Info display:
        - Hardware: Device firmware version (e.g., "Linkplay 4.8.731953")
        - Software: PyWiiM library version (e.g., "pywiim 2.0.17")
        - Serial Number: Device IP address
        - Connections: Device MAC address
        """
        dev_reg = dr.async_get(self.hass)
        identifiers = {(DOMAIN, self.uuid)}

        # Get pywiim library version
        try:
            import pywiim

            pywiim_version = f"pywiim {getattr(pywiim, '__version__', 'unknown')}"
        except (ImportError, AttributeError):
            pywiim_version = "pywiim unknown"

        # Build connections set with MAC address if available
        connections: set[tuple[str, str]] = set()
        if self.mac_address:
            connections.add((CONNECTION_NETWORK_MAC, self.mac_address))

        dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers=identifiers,
            manufacturer="WiiM",
            name=self.name,
            model=self.model,
            hw_version=self.firmware,  # Device firmware (LinkPlay)
            sw_version=pywiim_version,  # Integration library version
            serial_number=self.ip_address,  # IP address as serial number
            connections=connections if connections else None,  # MAC address as connection
        )

        self.device_info = HADeviceInfo(
            identifiers=identifiers,
            manufacturer="WiiM",
            name=self.name,
            model=self.model,
            hw_version=self.firmware,  # Device firmware (LinkPlay)
            sw_version=pywiim_version,  # Integration library version
            serial_number=self.ip_address,  # IP address as serial number
            connections=connections if connections else None,  # MAC address as connection
        )


# ===== HELPER FUNCTIONS =====


def get_speaker_from_config_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> Speaker:
    """Get speaker from config entry."""
    try:
        return cast("Speaker", hass.data[DOMAIN][config_entry.entry_id]["speaker"])
    except KeyError as err:
        _LOGGER.error("Speaker not found for config entry %s: %s", config_entry.entry_id, err)
        raise RuntimeError(f"Speaker not found for {config_entry.entry_id}") from err


def find_speaker_by_uuid(hass: HomeAssistant, uuid: str) -> Speaker | None:
    """Find speaker by UUID."""
    if not uuid:
        return None
    entry = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, uuid)
    if entry and entry.entry_id in hass.data.get(DOMAIN, {}):
        return get_speaker_from_config_entry(hass, entry)
    return None


def find_speaker_by_ip(hass: HomeAssistant, ip: str) -> Speaker | None:
    """Find speaker by IP address."""
    if not ip:
        return None
    from homeassistant.const import CONF_HOST

    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get(CONF_HOST) == ip and entry.entry_id in hass.data.get(DOMAIN, {}):
            return get_speaker_from_config_entry(hass, entry)
    return None


def get_all_speakers(hass: HomeAssistant) -> list[Speaker]:
    """Get all registered speakers."""
    speakers = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id in hass.data.get(DOMAIN, {}):
            speakers.append(get_speaker_from_config_entry(hass, entry))
    return speakers
