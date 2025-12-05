"""Base entity class for WiiM integration - minimal HA glue only."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WiiMCoordinator


class WiimEntity(CoordinatorEntity):
    """Base class for all WiiM entities - minimal glue to coordinator."""

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize with coordinator and config entry."""
        super().__init__(coordinator)
        self._config_entry = config_entry

    @property
    def player(self):
        """Access pywiim Player directly."""
        return self.coordinator.player

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info from player."""
        player = self.coordinator.player
        uuid = self._config_entry.unique_id or player.host

        # Get MAC address from device_info if available
        mac_address = None
        if player.device_info and hasattr(player.device_info, "mac"):
            mac_address = player.device_info.mac

        # Get pywiim library version
        try:
            import pywiim

            pywiim_version = f"pywiim {getattr(pywiim, '__version__', 'unknown')}"
        except (ImportError, AttributeError):
            pywiim_version = "pywiim unknown"

        # Build connections set with MAC address if available
        connections: set[tuple[str, str]] = set()
        if mac_address:
            from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

            connections.add((CONNECTION_NETWORK_MAC, mac_address))

        return DeviceInfo(
            identifiers={(DOMAIN, uuid)},
            manufacturer="WiiM",
            name=player.name or self._config_entry.title or "WiiM Speaker",
            model=player.model or "WiiM Speaker",
            hw_version=player.firmware,  # Device firmware (LinkPlay)
            sw_version=pywiim_version,  # Integration library version
            serial_number=player.host,  # IP address as serial number
            connections=connections if connections else None,  # MAC address as connection
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success
