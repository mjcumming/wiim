"""Base entity class for WiiM integration - minimal HA glue only."""

import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pywiim.exceptions import WiiMConnectionError, WiiMError, WiiMTimeoutError

from .const import DOMAIN
from .coordinator import WiiMCoordinator

_LOGGER = logging.getLogger(__name__)

# Shown when the remote has not reported a name (it normally reports "WiiM Voice Remote")
REMOTE_DEFAULT_NAME = "WiiM Voice Remote"


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
    if player.eth_mac_address:
        connections.add((CONNECTION_NETWORK_MAC, player.eth_mac_address))

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


def remote_paired(player: Any) -> bool:
    """Return True when the speaker supports a WiiM Voice Remote and one is paired.

    Both values come from pywiim (ADR 0006/0007). ``ble_remote`` keeps its last
    value when a read fails, so one failed poll does not make this False.
    """
    if not player.supports_ble_remote:
        return False
    remote = player.ble_remote
    return remote is not None and remote.paired is True


def remote_possible(player: Any) -> bool:
    """Return False only when pywiim knows the speaker has no remote support.

    ``supports_ble_remote`` is None while the connect-time probe was inconclusive;
    pywiim sets it True on a later successful read (ADR 025), so wait for it.
    """
    client = player.client
    return bool(client) and client.capabilities.get("supports_ble_remote", False) is not False


def format_remote_firmware(firmware: str | None) -> str | None:
    """Show the remote's firmware like the WiiM Home app: ``0054`` as ``54``, all zeros as ``0``.

    Anything that is not all digits is shown as pywiim reports it.
    """
    if not firmware:
        return None
    return str(int(firmware)) if firmware.isdigit() else firmware


def remote_identifier(config_entry: ConfigEntry, player: Any) -> tuple[str, str]:
    """Return the device registry identifier of the entry's WiiM Voice Remote."""
    return (DOMAIN, f"{config_entry.unique_id or player.host}_remote")


def build_remote_device_info(player: Any, config_entry: ConfigEntry) -> DeviceInfo:
    """Build the HA device for the WiiM Voice Remote, linked to its speaker.

    The remote is its own device with the speaker as ``via_device``. Name and
    firmware come from the remote; the BLE MAC is its only connection.
    """
    uuid = config_entry.unique_id or player.host
    remote = player.ble_remote

    device_info = DeviceInfo(
        identifiers={remote_identifier(config_entry, player)},
        via_device=(DOMAIN, uuid),
        manufacturer="WiiM",
        model=REMOTE_DEFAULT_NAME,
        name=(remote.name if remote else None) or REMOTE_DEFAULT_NAME,
        sw_version=format_remote_firmware(remote.firmware if remote else None),
    )
    if remote and remote.mac:
        device_info["connections"] = {(CONNECTION_BLUETOOTH, remote.mac)}
    return device_info


@callback
def async_add_remote_entities(
    coordinator: WiiMCoordinator,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    create_entities: Callable[[], list[Entity]],
) -> None:
    """Add a platform's remote entities once a remote is paired.

    Adds them now when a remote is already paired, otherwise on the first
    coordinator update after pairing. Nothing is removed afterwards: a remote
    that is unpaired or not connected makes its entities unavailable.
    """
    if remote_paired(coordinator.player):
        async_add_entities(create_entities())
        return
    if not remote_possible(coordinator.player):
        return

    remove_listener: Callable[[], None] | None = None
    added = False

    @callback
    def _unsubscribe() -> None:
        """Remove the coordinator listener once, whichever of pairing or unload comes first."""
        nonlocal remove_listener
        if remove_listener is not None:
            remove_listener()
            remove_listener = None

    @callback
    def _add_when_paired() -> None:
        nonlocal added
        if added or not remote_paired(coordinator.player):
            return
        added = True
        _unsubscribe()
        async_add_entities(create_entities())

    remove_listener = coordinator.async_add_listener(_add_when_paired)
    config_entry.async_on_unload(_unsubscribe)


class WiimRemoteEntity(WiimEntity):
    """Base class for entities on the WiiM Voice Remote device."""

    _attr_has_entity_name = True
    # Battery, signal strength and volume step make no sense for a remote that is away
    _requires_connection = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return the remote's own device, linked to the speaker."""
        return build_remote_device_info(self.coordinator.player, self._config_entry)

    @property
    def available(self) -> bool:
        """Unavailable while the speaker, the pairing or (where needed) the connection is down."""
        if not self.coordinator.last_update_success or not remote_paired(self.coordinator.player):
            return False
        return self.coordinator.player.ble_remote.connected or not self._requires_connection
