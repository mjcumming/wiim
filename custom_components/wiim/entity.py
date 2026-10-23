"""Base entity class for WiiM integration - minimal HA glue only."""

import logging
from contextlib import asynccontextmanager
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pywiim.exceptions import WiiMConnectionError, WiiMError, WiiMTimeoutError

from .const import DOMAIN
from .coordinator import WiiMCoordinator

_LOGGER = logging.getLogger(__name__)


def build_device_info(player: Any, config_entry: ConfigEntry) -> DeviceInfo:
    """Build HA device info from the pywiim player.

    Shared by the device registry call in ``__init__`` and ``WiimEntity.device_info``
    so both write the same values. Every key must be an ``async_get_or_create``
    parameter, because ``__init__`` passes this as keyword arguments.
    """
    uuid = config_entry.unique_id or player.host
    device_info = player.device_info

    # Friendly name (e.g. "WiiM Pro Plus"); the raw project code goes in model_id
    model = player.model_name or player.model or "WiiM Speaker"
    model_id = player.model if player.model and player.model != model else None

    connections: set[tuple[str, str]] = set()
    mac_address = getattr(device_info, "mac", None) if device_info else None
    if mac_address:
        connections.add((CONNECTION_NETWORK_MAC, mac_address))

    # Endpoint pywiim connected with (protocol://host:port); not known before the first probe
    endpoint = player.client.discovered_endpoint if player.client else None
    configuration_url = endpoint if isinstance(endpoint, str) and endpoint else f"https://{player.host}"

    return DeviceInfo(
        identifiers={(DOMAIN, uuid)},
        manufacturer="WiiM",
        name=player.name or config_entry.title or "WiiM Speaker",
        model=model,
        model_id=model_id,
        sw_version=player.firmware,  # Device firmware (LinkPlay)
        hw_version=getattr(device_info, "hardware", None) if device_info else None,
        configuration_url=configuration_url,
        serial_number=None,  # Explicit None clears the IP older versions stored here
        connections=connections if connections else None,  # MAC address as connection
    )


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
        return build_device_info(self.coordinator.player, self._config_entry)

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
                _LOGGER.debug("[%s] %s failed (connection issue): %s", self.name, operation, err)
                raise HomeAssistantError(f"{operation} on {self.name}: device unreachable") from err

            _LOGGER.error("[%s] %s failed: %s", self.name, operation, err, exc_info=True)
            raise HomeAssistantError(f"Failed to {operation}: {err}") from err
