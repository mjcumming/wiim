"""Device registry for WiiM integration.

Single source of truth for device roles and group relationships.
Replaces multiple redundant state management systems.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from .coordinator import WiiMCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class DeviceState:
    """State of a single WiiM device."""

    ip: str
    role: Literal["solo", "master", "slave"] = "solo"
    master_ip: str | None = None
    slaves: set[str] = field(default_factory=set)
    coordinator: WiiMCoordinator | None = None


class WiiMDeviceRegistry:
    """Single source of truth for WiiM device states and group relationships."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the device registry."""
        self.hass = hass
        self.devices: dict[str, DeviceState] = {}

    def register_device(self, coordinator: WiiMCoordinator) -> None:
        """Register a device coordinator with the registry."""
        device_ip = coordinator.client.host
        if device_ip not in self.devices:
            self.devices[device_ip] = DeviceState(ip=device_ip, coordinator=coordinator)
        else:
            self.devices[device_ip].coordinator = coordinator
        _LOGGER.debug("[WiiM] Registered device: %s", device_ip)

    def unregister_device(self, device_ip: str) -> None:
        """Unregister a device from the registry."""
        if device_ip in self.devices:
            # Remove as slave from any master
            device = self.devices[device_ip]
            if device.role == "slave" and device.master_ip:
                master_device = self.devices.get(device.master_ip)
                if master_device:
                    master_device.slaves.discard(device_ip)
                    if not master_device.slaves:
                        master_device.role = "solo"

            # Remove all slaves if this was a master
            if device.role == "master":
                for slave_ip in device.slaves.copy():
                    slave_device = self.devices.get(slave_ip)
                    if slave_device:
                        slave_device.role = "solo"
                        slave_device.master_ip = None

            del self.devices[device_ip]
            _LOGGER.debug("[WiiM] Unregistered device: %s", device_ip)

    def get_device_role(self, device_ip: str) -> str:
        """Get the role of a device."""
        return self.devices.get(device_ip, DeviceState(ip=device_ip)).role

    def get_master_ip(self, slave_ip: str) -> str | None:
        """Get the master IP for a slave device."""
        device = self.devices.get(slave_ip)
        return device.master_ip if device and device.role == "slave" else None

    def get_slave_ips(self, master_ip: str) -> set[str]:
        """Get slave IPs for a master device."""
        device = self.devices.get(master_ip)
        return device.slaves.copy() if device and device.role == "master" else set()

    def get_coordinator(self, device_ip: str) -> WiiMCoordinator | None:
        """Get coordinator for a device."""
        device = self.devices.get(device_ip)
        return device.coordinator if device else None

    def get_all_device_ips(self) -> list[str]:
        """Get all registered device IPs."""
        return list(self.devices.keys())

    async def handle_role_change(self, device_ip: str, old_role: str, new_role: str, status: dict) -> bool:
        """Handle role change for a device. Returns True if changes were made."""
        _LOGGER.debug("[WiiM] %s: Role change %s -> %s", device_ip, old_role, new_role)

        changes_made = False

        # Ensure device exists in registry
        if device_ip not in self.devices:
            coordinator = self._find_coordinator_for_ip(device_ip)
            self.devices[device_ip] = DeviceState(ip=device_ip, coordinator=coordinator)

        device = self.devices[device_ip]

        # Handle leaving slave role
        if old_role == "slave" and new_role != "slave":
            changes_made |= await self._handle_leaves_slave(device_ip)

        # Handle becoming slave
        if new_role == "slave":
            changes_made |= await self._handle_becomes_slave(device_ip, status)

        # Handle becoming potential master or solo
        if new_role in ["solo", "master"]:
            changes_made |= await self._verify_master_status(device_ip)

        # Update device role
        if device.role != new_role:
            device.role = new_role
            changes_made = True

        if changes_made:
            _LOGGER.info("[WiiM] %s: Updated role to %s", device_ip, new_role)

        return changes_made

    async def _handle_becomes_slave(self, device_ip: str, status: dict) -> bool:
        """Handle device becoming a slave."""
        # Extract master info from status (group > 0 indicates slave)
        group_field = status.get("group", "0")
        if group_field == "0":
            _LOGGER.warning("[WiiM] %s: Called _handle_becomes_slave but group=0", device_ip)
            return False

        # For slaves, try to find master IP/UUID from status or multiroom data
        master_ip = status.get("master_ip")
        master_uuid = status.get("master_uuid")

        # If no master_ip in status, try to find by UUID across all devices
        if not master_ip and master_uuid:
            for other_ip, other_device in self.devices.items():
                if other_device.coordinator and other_device.coordinator.data:
                    other_status = other_device.coordinator.data.get("status", {})
                    if other_status.get("uuid") == master_uuid:
                        master_ip = other_ip
                        break

        if not master_ip:
            _LOGGER.warning(
                "[WiiM] %s: Slave without discoverable master (group=%s, master_uuid=%s)",
                device_ip,
                group_field,
                master_uuid,
            )
            return False

        device = self.devices[device_ip]
        changes_made = False

        # Update slave device
        if device.master_ip != master_ip:
            device.master_ip = master_ip
            device.role = "slave"
            device.slaves.clear()  # Slaves can't have slaves
            changes_made = True

        # Ensure master device exists and update it
        if master_ip not in self.devices:
            master_coordinator = self._find_coordinator_for_ip(master_ip)
            self.devices[master_ip] = DeviceState(ip=master_ip, role="master", coordinator=master_coordinator)
            changes_made = True

        master_device = self.devices[master_ip]
        if device_ip not in master_device.slaves:
            master_device.slaves.add(device_ip)
            master_device.role = "master"
            changes_made = True

        _LOGGER.debug("[WiiM] %s: Became slave of %s", device_ip, master_ip)
        return changes_made

    async def _handle_leaves_slave(self, device_ip: str) -> bool:
        """Handle device leaving slave role."""
        device = self.devices.get(device_ip)
        if not device or device.role != "slave":
            return False

        changes_made = False
        master_ip = device.master_ip

        # Remove from master's slave list
        if master_ip and master_ip in self.devices:
            master_device = self.devices[master_ip]
            if device_ip in master_device.slaves:
                master_device.slaves.remove(device_ip)
                changes_made = True

                # If master has no more slaves, demote to solo
                if not master_device.slaves:
                    master_device.role = "solo"
                    _LOGGER.debug("[WiiM] %s: Demoted to solo (no more slaves)", master_ip)

        # Clear slave's master reference
        device.master_ip = None
        device.role = "solo"  # Will be updated to master if it has slaves
        changes_made = True

        _LOGGER.debug("[WiiM] %s: Left slave role", device_ip)
        return changes_made

    async def _verify_master_status(self, device_ip: str) -> bool:
        """Verify master status by calling getSlaveList API."""
        coordinator = self.get_coordinator(device_ip)
        if not coordinator:
            return False

        try:
            # Call getSlaveList to get authoritative slave information
            multiroom = await coordinator.client.get_multiroom_info()
            slave_count = multiroom.get("slaves", 0)
            slave_list = multiroom.get("slave_list", [])

            device = self.devices[device_ip]
            changes_made = False

            if slave_count == 0:
                # No slaves, device should be solo
                if device.role != "solo":
                    device.role = "solo"
                    device.slaves.clear()
                    changes_made = True
                    _LOGGER.debug("[WiiM] %s: Verified as solo (no slaves)", device_ip)
            else:
                # Has slaves, device should be master
                new_slave_ips = {slave["ip"] for slave in slave_list if isinstance(slave, dict) and slave.get("ip")}

                if device.role != "master" or device.slaves != new_slave_ips:
                    device.role = "master"
                    old_slaves = device.slaves.copy()
                    device.slaves = new_slave_ips
                    changes_made = True

                    # Update slave devices
                    for slave_ip in new_slave_ips:
                        if slave_ip not in self.devices:
                            slave_coordinator = self._find_coordinator_for_ip(slave_ip)
                            self.devices[slave_ip] = DeviceState(
                                ip=slave_ip, role="slave", master_ip=device_ip, coordinator=slave_coordinator
                            )
                        else:
                            slave_device = self.devices[slave_ip]
                            slave_device.role = "slave"
                            slave_device.master_ip = device_ip
                            slave_device.slaves.clear()

                    # Clean up removed slaves
                    for old_slave_ip in old_slaves - new_slave_ips:
                        if old_slave_ip in self.devices:
                            old_slave = self.devices[old_slave_ip]
                            old_slave.role = "solo"
                            old_slave.master_ip = None

                    _LOGGER.debug("[WiiM] %s: Verified as master with slaves: %s", device_ip, new_slave_ips)

            return changes_made

        except Exception as err:
            _LOGGER.debug("[WiiM] %s: Failed to verify master status: %s", device_ip, err)
            return False

    def _find_coordinator_for_ip(self, device_ip: str) -> WiiMCoordinator | None:
        """Find coordinator for a device IP."""
        from .const import DOMAIN

        for entry_data in self.hass.data.get(DOMAIN, {}).values():
            if isinstance(entry_data, dict) and "coordinator" in entry_data:
                coord = entry_data["coordinator"]
                if hasattr(coord, "client") and coord.client.host == device_ip:
                    return coord
        return None

    def get_group_members_for_device(self, device_ip: str) -> list[str]:
        """Get group member entity IDs for a device."""
        device = self.devices.get(device_ip)
        if not device:
            return []

        def ip_to_entity_id(ip: str) -> str:
            return f"media_player.wiim_{ip.replace('.', '_')}"

        if device.role == "master":
            # Master + all slaves
            members = [ip_to_entity_id(device_ip)]
            members.extend(ip_to_entity_id(slave_ip) for slave_ip in device.slaves)
            return members

        elif device.role == "slave" and device.master_ip:
            # All devices in the group (master + all slaves)
            master_device = self.devices.get(device.master_ip)
            if master_device:
                members = [ip_to_entity_id(device.master_ip)]
                members.extend(ip_to_entity_id(slave_ip) for slave_ip in master_device.slaves)
                return members

        return []  # Solo device has no group members

    def get_group_leader_for_device(self, device_ip: str) -> str | None:
        """Get group leader entity ID for a device."""
        device = self.devices.get(device_ip)
        if not device:
            return None

        if device.role == "master":
            return f"media_player.wiim_{device_ip.replace('.', '_')}"
        elif device.role == "slave" and device.master_ip:
            return f"media_player.wiim_{device.master_ip.replace('.', '_')}"

        return None  # Solo device has no leader


# Global registry instance
_registry: WiiMDeviceRegistry | None = None


def get_device_registry(hass: HomeAssistant) -> WiiMDeviceRegistry:
    """Get the global device registry instance."""
    global _registry
    if _registry is None:
        _registry = WiiMDeviceRegistry(hass)
    return _registry
