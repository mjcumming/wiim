"""WiiM Device Registry Service.

Provides centralized, high-performance device management with O(1) lookups.
Eliminates the need for expensive coordinator scanning operations.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from ..coordinator import WiiMCoordinator

_LOGGER = logging.getLogger(__name__)


class WiiMDeviceRegistry:
    """Singleton service for managing WiiM device references.

    Provides O(1) device lookups by UUID, IP, or MAC address.
    Eliminates expensive coordinator scanning operations.
    """

    _instance: WiiMDeviceRegistry | None = None

    def __new__(cls, hass: HomeAssistant) -> WiiMDeviceRegistry:
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the registry."""
        # Use hasattr to check if already initialized
        if hasattr(self, "_devices_by_uuid"):
            return

        self.hass = hass
        self._devices_by_uuid: dict[str, WiiMCoordinator] = {}
        self._devices_by_ip: dict[str, WiiMCoordinator] = {}
        self._devices_by_mac: dict[str, WiiMCoordinator] = {}
        self._group_states: dict[str, GroupState] = {}

        _LOGGER.debug("[WiiM] Device registry initialized")

    def register_device(self, coordinator: WiiMCoordinator) -> None:
        """Register a device coordinator for fast lookups.

        Called once during device setup, not during operation.
        """
        # Get identifiers from coordinator data
        data = coordinator.data
        if not data or "status" not in data:
            _LOGGER.warning("[WiiM] Cannot register device %s - no status data", coordinator.client.host)
            return

        status = data["status"]
        uuid = status.get("uuid")
        ip = coordinator.client.host
        mac = status.get("MAC")

        # Register by IP (always available)
        self._devices_by_ip[ip] = coordinator
        _LOGGER.debug("[WiiM] Registered device by IP: %s", ip)

        # Register by UUID (preferred identifier)
        if uuid:
            self._devices_by_uuid[uuid] = coordinator
            _LOGGER.debug("[WiiM] Registered device by UUID: %s", uuid)

        # Register by MAC (stable identifier)
        if mac:
            normalized_mac = self._normalize_mac(mac)
            self._devices_by_mac[normalized_mac] = coordinator
            _LOGGER.debug("[WiiM] Registered device by MAC: %s", normalized_mac)

    def unregister_device(self, coordinator: WiiMCoordinator) -> None:
        """Unregister a device coordinator."""
        ip = coordinator.client.host

        # Remove from all registries
        self._devices_by_ip.pop(ip, None)

        # Find and remove by UUID
        uuid_to_remove = None
        for uuid, coord in self._devices_by_uuid.items():
            if coord == coordinator:
                uuid_to_remove = uuid
                break
        if uuid_to_remove:
            self._devices_by_uuid.pop(uuid_to_remove, None)

        # Find and remove by MAC
        mac_to_remove = None
        for mac, coord in self._devices_by_mac.items():
            if coord == coordinator:
                mac_to_remove = mac
                break
        if mac_to_remove:
            self._devices_by_mac.pop(mac_to_remove, None)

        # Remove group state
        self._group_states.pop(ip, None)

        _LOGGER.debug("[WiiM] Unregistered device: %s", ip)

    def get_device_by_uuid(self, uuid: str) -> WiiMCoordinator | None:
        """Get device by UUID - O(1) lookup."""
        return self._devices_by_uuid.get(uuid)

    def get_device_by_ip(self, ip: str) -> WiiMCoordinator | None:
        """Get device by IP address - O(1) lookup."""
        return self._devices_by_ip.get(ip)

    def get_device_by_mac(self, mac: str) -> WiiMCoordinator | None:
        """Get device by MAC address - O(1) lookup."""
        normalized_mac = self._normalize_mac(mac)
        return self._devices_by_mac.get(normalized_mac)

    def get_all_devices(self) -> list[WiiMCoordinator]:
        """Get all registered devices."""
        return list(self._devices_by_ip.values())

    def get_group_state(self, device_key: str) -> GroupState | None:
        """Get cached group state for a device."""
        return self._group_states.get(device_key)

    def set_group_state(self, device_key: str, group_state: GroupState) -> None:
        """Cache group state for a device."""
        self._group_states[device_key] = group_state

    def find_master_by_uuid(self, master_uuid: str) -> WiiMCoordinator | None:
        """Find master device by its UUID."""
        return self.get_device_by_uuid(master_uuid)

    @staticmethod
    def _normalize_mac(mac: str) -> str:
        """Normalize MAC address to lowercase without separators."""
        if not mac:
            return ""
        return mac.lower().replace(":", "").replace("-", "").replace(" ", "")

    def get_registry_stats(self) -> dict[str, Any]:
        """Get registry statistics for debugging."""
        return {
            "devices_by_uuid": len(self._devices_by_uuid),
            "devices_by_ip": len(self._devices_by_ip),
            "devices_by_mac": len(self._devices_by_mac),
            "group_states": len(self._group_states),
        }


class GroupState:
    """Represents the cached group state of a device."""

    def __init__(
        self,
        role: str,
        master_uuid: str | None = None,
        group_members: list[str] | None = None,
        group_leader: str | None = None,
    ) -> None:
        """Initialize group state."""
        self.role = role
        self.master_uuid = master_uuid
        self.group_members = group_members or []
        self.group_leader = group_leader
        self.last_updated = self._current_time()

    def update(
        self,
        role: str,
        master_uuid: str | None = None,
        group_members: list[str] | None = None,
        group_leader: str | None = None,
    ) -> bool:
        """Update group state. Returns True if changed."""
        changed = (
            self.role != role
            or self.master_uuid != master_uuid
            or self.group_members != (group_members or [])
            or self.group_leader != group_leader
        )

        if changed:
            self.role = role
            self.master_uuid = master_uuid
            self.group_members = group_members or []
            self.group_leader = group_leader
            self.last_updated = self._current_time()

        return changed

    @staticmethod
    def _current_time() -> float:
        """Get current time for timestamps."""
        import time

        return time.time()


def get_device_registry(hass: HomeAssistant) -> WiiMDeviceRegistry:
    """Get the singleton device registry instance."""
    return WiiMDeviceRegistry(hass)


def create_master_device_uuid(master_uuid: str) -> str:
    """Create stable UUID for master group entities."""
    return f"{master_uuid}_group_master"
