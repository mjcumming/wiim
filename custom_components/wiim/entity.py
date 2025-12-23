"""Base entity class for WiiM integration - minimal HA glue only."""

import logging
from contextlib import asynccontextmanager

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pywiim.exceptions import WiiMConnectionError, WiiMError, WiiMTimeoutError

from .const import DOMAIN
from .coordinator import WiiMCoordinator

_LOGGER = logging.getLogger(__name__)


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

    @asynccontextmanager
    async def wiim_command(self, operation: str):
        """Context manager for consistent WiiM command error handling.

        Classifies errors into transient (connection/timeout) vs persistent
        failures for better log hygiene.
        """
        try:
            yield
        except WiiMError as err:
            # Classification of errors is now minimal - pywiim is expected to
            # provide correct exception types.
            if isinstance(err, (WiiMConnectionError, WiiMTimeoutError)):
                _LOGGER.warning("[%s] %s failed (connection issue): %s", self.name, operation, err)
                raise HomeAssistantError(f"{operation} on {self.name}: device unreachable") from err

            _LOGGER.error("[%s] %s failed: %s", self.name, operation, err, exc_info=True)
            raise HomeAssistantError(f"Failed to {operation}: {err}") from err
