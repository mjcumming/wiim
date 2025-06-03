"""Device registry for WiiM integration.

Single source of truth for device roles and group relationships.
UUID-based with multiple lookup methods (UUID, IP, MAC, entity name).
Follows Home Assistant best practices for device management.
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
    """State of a single WiiM device - UUID-based."""

    uuid: str  # PRIMARY KEY - immutable device identifier
    ip: str  # Current IP address (can change)
    mac: str  # Hardware MAC address
    device_name: str  # User-friendly device name
    entity_id: str | None = None  # Actual HA entity ID
    role: Literal["solo", "master", "slave", "virtual_master"] = "solo"
    master_uuid: str | None = None  # Reference master by UUID
    slave_uuids: set[str] = field(default_factory=set)  # Slave UUIDs
    coordinator: WiiMCoordinator | None = None


class WiiMDeviceRegistry:
    """Enhanced UUID-based device registry with multiple lookup methods."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the device registry."""
        self.hass = hass

        # Primary storage: UUID → DeviceState
        self.devices: dict[str, DeviceState] = {}

        # Lookup indexes for fast access
        self._ip_to_uuid: dict[str, str] = {}
        self._mac_to_uuid: dict[str, str] = {}
        self._entity_to_uuid: dict[str, str] = {}

    def register_device(self, coordinator: WiiMCoordinator) -> None:
        """Register a device coordinator with the registry."""
        # Extract device identifiers from coordinator data
        status = coordinator.data.get("status", {}) if coordinator.data else {}

        # Handle cases where status might be incomplete (e.g., during testing)
        if not status:
            _LOGGER.warning("[WiiM] %s: No status data available for device registration", coordinator.client.host)
            # Create minimal device entry for testing/fallback
            status = {
                "uuid": f"fallback_{coordinator.client.host.replace('.', '_')}",
                "DeviceName": f"WiiM Device {coordinator.client.host}",
                "device_name": f"WiiM Device {coordinator.client.host}",
                "MAC": "00:00:00:00:00:00",
            }

        uuid = status.get("uuid")
        ip = coordinator.client.host
        mac = status.get("MAC", "").lower().replace(":", "")
        device_name = status.get("DeviceName") or status.get("device_name") or f"WiiM_{ip.replace('.', '_')}"

        if not uuid:
            _LOGGER.warning("[WiiM] %s: No UUID found, using IP as fallback", ip)
            uuid = f"ip_{ip.replace('.', '_')}"

        # Find actual entity ID for this device
        entity_id = self._find_entity_id_for_device(ip, mac, device_name)

        # Create or update device state
        if uuid in self.devices:
            device = self.devices[uuid]
            # Update mutable fields
            old_ip = device.ip
            device.ip = ip
            device.mac = mac
            device.device_name = device_name
            device.entity_id = entity_id
            device.coordinator = coordinator

            # Update IP index if changed
            if old_ip != ip:
                self._ip_to_uuid.pop(old_ip, None)
                self._ip_to_uuid[ip] = uuid
        else:
            # Create new device
            device = DeviceState(
                uuid=uuid, ip=ip, mac=mac, device_name=device_name, entity_id=entity_id, coordinator=coordinator
            )
            self.devices[uuid] = device

        # Update lookup indexes
        self._ip_to_uuid[ip] = uuid
        if mac:
            self._mac_to_uuid[mac] = uuid
        if entity_id:
            self._entity_to_uuid[entity_id] = uuid

        _LOGGER.debug("[WiiM] Registered device: %s (UUID: %s, IP: %s, Entity: %s)", device_name, uuid, ip, entity_id)

    def unregister_device(self, identifier: str) -> None:
        """Unregister a device by any identifier (UUID, IP, MAC, entity)."""
        device = self.find_device(identifier)
        if not device:
            return

        uuid = device.uuid

        # Handle group cleanup
        if device.role == "slave" and device.master_uuid:
            master_device = self.devices.get(device.master_uuid)
            if master_device:
                master_device.slave_uuids.discard(uuid)
                if not master_device.slave_uuids:
                    master_device.role = "solo"

        # Remove all slaves if this was a master
        if device.role == "master":
            for slave_uuid in device.slave_uuids.copy():
                slave_device = self.devices.get(slave_uuid)
                if slave_device:
                    slave_device.role = "solo"
                    slave_device.master_uuid = None

        # Remove from lookup indexes
        self._ip_to_uuid.pop(device.ip, None)
        if device.mac:
            self._mac_to_uuid.pop(device.mac, None)
        if device.entity_id:
            self._entity_to_uuid.pop(device.entity_id, None)

        # Remove from primary storage
        del self.devices[uuid]
        _LOGGER.debug("[WiiM] Unregistered device: %s (UUID: %s)", device.device_name, uuid)

    # =========================================================================
    # Multiple Lookup Methods
    # =========================================================================

    def find_device_by_uuid(self, uuid: str) -> DeviceState | None:
        """Find device by UUID (primary lookup)."""
        return self.devices.get(uuid)

    def find_device_by_ip(self, ip: str) -> DeviceState | None:
        """Find device by IP address."""
        uuid = self._ip_to_uuid.get(ip)
        return self.devices.get(uuid) if uuid else None

    def find_device_by_mac(self, mac: str) -> DeviceState | None:
        """Find device by MAC address."""
        mac_clean = mac.lower().replace(":", "")
        uuid = self._mac_to_uuid.get(mac_clean)
        return self.devices.get(uuid) if uuid else None

    def find_device_by_entity_name(self, entity_id: str) -> DeviceState | None:
        """Find device by entity ID."""
        uuid = self._entity_to_uuid.get(entity_id)
        if uuid:
            return self.devices.get(uuid)

        # Fallback: try to match by device name pattern in entity ID
        for device in self.devices.values():
            if device.device_name and device.device_name.lower().replace(" ", "_") in entity_id.lower():
                # Update the entity mapping for future lookups
                self._entity_to_uuid[entity_id] = device.uuid
                device.entity_id = entity_id
                return device
        return None

    def find_device(self, identifier: str) -> DeviceState | None:
        """Universal device lookup - tries all methods until one works."""
        # Try UUID first (most efficient)
        if device := self.find_device_by_uuid(identifier):
            return device

        # Try entity ID
        if identifier.startswith("media_player."):
            if device := self.find_device_by_entity_name(identifier):
                return device

        # Try IP address pattern
        if "." in identifier and not identifier.startswith("media_player."):
            if device := self.find_device_by_ip(identifier):
                return device

        # Try MAC address pattern
        if ":" in identifier or len(identifier) == 12:
            if device := self.find_device_by_mac(identifier):
                return device

        return None

    def find_coordinator(self, identifier: str) -> WiiMCoordinator | None:
        """Find coordinator by any identifier."""
        device = self.find_device(identifier)
        return device.coordinator if device else None

    # =========================================================================
    # Group Management (UUID-based)
    # =========================================================================

    def get_device_role(self, identifier: str) -> str:
        """Get the role of a device by any identifier."""
        device = self.find_device(identifier)
        return device.role if device else "solo"

    def get_master_device(self, slave_identifier: str) -> DeviceState | None:
        """Get the master device for a slave."""
        slave_device = self.find_device(slave_identifier)
        if slave_device and slave_device.role == "slave" and slave_device.master_uuid:
            return self.devices.get(slave_device.master_uuid)
        return None

    def get_slave_devices(self, master_identifier: str) -> list[DeviceState]:
        """Get slave devices for a master."""
        master_device = self.find_device(master_identifier)
        if master_device and master_device.role == "master":
            return [self.devices[uuid] for uuid in master_device.slave_uuids if uuid in self.devices]
        return []

    def get_group_members_for_device(self, identifier: str) -> list[str]:
        """Get group member entity IDs for a device."""
        device = self.find_device(identifier)
        if not device:
            return []

        members = []

        if device.role == "master":
            # Master + all slaves
            if device.entity_id:
                members.append(device.entity_id)
            for slave_device in self.get_slave_devices(device.uuid):
                if slave_device.entity_id:
                    members.append(slave_device.entity_id)

        elif device.role == "slave":
            # All devices in the group (master + all slaves)
            master_device = self.get_master_device(device.uuid)
            if master_device:
                if master_device.entity_id:
                    members.append(master_device.entity_id)
                for slave_device in self.get_slave_devices(master_device.uuid):
                    if slave_device.entity_id:
                        members.append(slave_device.entity_id)

        elif device.role == "virtual_master":
            # Virtual master represents the group - return physical group members
            # Find the actual master device this virtual entity represents
            physical_master_uuid = device.uuid.replace("virtual_", "")
            physical_master = self.devices.get(physical_master_uuid)
            if physical_master:
                return self.get_group_members_for_device(physical_master.uuid)

        return members

    def get_group_leader_for_device(self, identifier: str) -> str | None:
        """Get group leader entity ID for a device."""
        device = self.find_device(identifier)
        if not device:
            return None

        if device.role == "master":
            return device.entity_id
        elif device.role == "slave":
            master_device = self.get_master_device(device.uuid)
            return master_device.entity_id if master_device else None

        return None  # Solo device has no leader

    def get_all_device_ips(self) -> list[str]:
        """Get all registered device IPs."""
        return [device.ip for device in self.devices.values()]

    def get_all_devices(self) -> list[DeviceState]:
        """Get all registered devices."""
        return list(self.devices.values())

    # =========================================================================
    # Role Management (UUID-based)
    # =========================================================================

    async def handle_role_change(self, device_ip: str, old_role: str, new_role: str, status: dict) -> bool:
        """Handle role change for a device. Returns True if changes were made."""
        device = self.find_device_by_ip(device_ip)
        if not device:
            # Auto-register device if not found
            coordinator = self._find_coordinator_for_ip(device_ip)
            if coordinator:
                self.register_device(coordinator)
                device = self.find_device_by_ip(device_ip)

        if not device:
            _LOGGER.warning("[WiiM] %s: Cannot handle role change, device not found", device_ip)
            return False

        _LOGGER.debug("[WiiM] %s (%s): Role change %s -> %s", device.device_name, device.uuid, old_role, new_role)

        changes_made = False

        # Handle leaving slave role
        if old_role == "slave" and new_role != "slave":
            changes_made |= await self._handle_leaves_slave(device.uuid)

        # Handle becoming slave
        if new_role == "slave":
            changes_made |= await self._handle_becomes_slave(device.uuid, status)

        # Handle becoming potential master or solo
        if new_role in ["solo", "master"]:
            changes_made |= await self._verify_master_status(device.uuid)

        # Update device role
        if device.role != new_role:
            device.role = new_role
            changes_made = True

        if changes_made:
            _LOGGER.info("[WiiM] %s (%s): Updated role to %s", device.device_name, device.uuid, new_role)

        return changes_made

    async def _handle_becomes_slave(self, device_uuid: str, status: dict) -> bool:
        """Handle device becoming a slave."""
        device = self.devices.get(device_uuid)
        if not device:
            return False

        # Extract master info from status
        group_field = status.get("group", "0")
        if group_field == "0":
            _LOGGER.warning("[WiiM] %s: Called _handle_becomes_slave but group=0", device.device_name)
            return False

        master_uuid = status.get("master_uuid")
        master_ip = status.get("master_ip")

        # Try to find master by UUID first
        master_device = None
        if master_uuid:
            master_device = self.devices.get(master_uuid)

        # Fallback: find master by IP
        if not master_device and master_ip:
            master_device = self.find_device_by_ip(master_ip)

        if not master_device:
            _LOGGER.warning(
                "[WiiM] %s: Slave without discoverable master (group=%s, master_uuid=%s, master_ip=%s)",
                device.device_name,
                group_field,
                master_uuid,
                master_ip,
            )
            return False

        changes_made = False

        # Update slave device
        if device.master_uuid != master_device.uuid:
            device.master_uuid = master_device.uuid
            device.role = "slave"
            device.slave_uuids.clear()  # Slaves can't have slaves
            changes_made = True

        # Update master device
        if device_uuid not in master_device.slave_uuids:
            master_device.slave_uuids.add(device_uuid)
            master_device.role = "master"
            changes_made = True

        _LOGGER.debug("[WiiM] %s: Became slave of %s", device.device_name, master_device.device_name)
        return changes_made

    async def _handle_leaves_slave(self, device_uuid: str) -> bool:
        """Handle device leaving slave role."""
        device = self.devices.get(device_uuid)
        if not device or device.role != "slave":
            return False

        changes_made = False
        master_uuid = device.master_uuid

        # Remove from master's slave list
        if master_uuid and master_uuid in self.devices:
            master_device = self.devices[master_uuid]
            if device_uuid in master_device.slave_uuids:
                master_device.slave_uuids.remove(device_uuid)
                changes_made = True

                # If master has no more slaves, demote to solo
                if not master_device.slave_uuids:
                    master_device.role = "solo"
                    _LOGGER.debug("[WiiM] %s: Demoted to solo (no more slaves)", master_device.device_name)

        # Clear slave's master reference
        device.master_uuid = None
        device.role = "solo"  # Will be updated to master if it has slaves
        changes_made = True

        _LOGGER.debug("[WiiM] %s: Left slave role", device.device_name)
        return changes_made

    async def _verify_master_status(self, device_uuid: str) -> bool:
        """Verify master status by calling getSlaveList API."""
        device = self.devices.get(device_uuid)
        if not device or not device.coordinator:
            return False

        try:
            # Call getSlaveList to get authoritative slave information
            multiroom = await device.coordinator.client.get_multiroom_info()
            slave_count = multiroom.get("slaves", 0)
            slave_list = multiroom.get("slave_list", [])

            changes_made = False

            if slave_count == 0:
                # No slaves, device should be solo
                if device.role != "solo":
                    device.role = "solo"
                    device.slave_uuids.clear()
                    changes_made = True
                    _LOGGER.debug("[WiiM] %s: Verified as solo (no slaves)", device.device_name)
            else:
                # Has slaves, device should be master
                new_slave_uuids = set()

                for slave_info in slave_list:
                    if isinstance(slave_info, dict) and slave_info.get("ip"):
                        slave_ip = slave_info["ip"]
                        slave_device = self.find_device_by_ip(slave_ip)
                        if slave_device:
                            new_slave_uuids.add(slave_device.uuid)

                if device.role != "master" or device.slave_uuids != new_slave_uuids:
                    device.role = "master"
                    old_slaves = device.slave_uuids.copy()
                    device.slave_uuids = new_slave_uuids
                    changes_made = True

                    # Update slave devices
                    for slave_uuid in new_slave_uuids:
                        if slave_uuid in self.devices:
                            slave_device = self.devices[slave_uuid]
                            slave_device.role = "slave"
                            slave_device.master_uuid = device_uuid
                            slave_device.slave_uuids.clear()

                    # Clean up removed slaves
                    for old_slave_uuid in old_slaves - new_slave_uuids:
                        if old_slave_uuid in self.devices:
                            old_slave = self.devices[old_slave_uuid]
                            old_slave.role = "solo"
                            old_slave.master_uuid = None

                    _LOGGER.debug(
                        "[WiiM] %s: Verified as master with %d slaves", device.device_name, len(new_slave_uuids)
                    )

            return changes_made

        except Exception as err:
            _LOGGER.debug("[WiiM] %s: Failed to verify master status: %s", device.device_name, err)
            return False

    # =========================================================================
    # Compatibility Methods (for existing code)
    # =========================================================================

    def get_master_ip(self, slave_identifier: str) -> str | None:
        """Get the master IP for a slave device (compatibility method)."""
        master_device = self.get_master_device(slave_identifier)
        return master_device.ip if master_device else None

    def get_coordinator(self, identifier: str) -> WiiMCoordinator | None:
        """Get coordinator by identifier (compatibility method)."""
        return self.find_coordinator(identifier)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _find_coordinator_for_ip(self, device_ip: str) -> WiiMCoordinator | None:
        """Find coordinator for a device IP."""
        from .const import DOMAIN

        for entry_data in self.hass.data.get(DOMAIN, {}).values():
            if isinstance(entry_data, dict) and "coordinator" in entry_data:
                coord = entry_data["coordinator"]
                if hasattr(coord, "client") and coord.client.host == device_ip:
                    return coord
        return None

    def _find_entity_id_for_device(self, ip: str, mac: str, device_name: str) -> str | None:
        """Find the actual entity ID for a device using multiple strategies."""
        # During testing or early initialization, states might not be available
        try:
            # Strategy 1: Look for device name pattern
            if device_name:
                name_pattern = device_name.lower().replace(" ", "_")
                for entity_id in self.hass.states.async_entity_ids("media_player"):
                    if (
                        entity_id.startswith(f"media_player.{name_pattern}")
                        and entity_id.startswith("media_player.wiim") is False
                    ):  # Avoid old IP-based names
                        return entity_id

            # Strategy 2: Look for IP-based pattern (legacy)
            ip_pattern = f"media_player.wiim_{ip.replace('.', '_')}"
            if self.hass.states.get(ip_pattern):
                return ip_pattern

            # Strategy 3: Look for MAC-based pattern
            if mac:
                mac_pattern = f"media_player.wiim_{mac}"
                if self.hass.states.get(mac_pattern):
                    return mac_pattern
        except (AttributeError, RuntimeError):
            # During testing or early initialization, states might not be available
            _LOGGER.debug("[WiiM] States not available during entity ID search for %s", ip)

        return None

    # =========================================================================
    # Virtual Entity Management
    # =========================================================================

    def register_virtual_device(self, master_device: DeviceState, virtual_entity_id: str) -> DeviceState:
        """Register a virtual group master device."""
        virtual_uuid = f"virtual_{master_device.uuid}"

        virtual_device = DeviceState(
            uuid=virtual_uuid,
            ip=master_device.ip,
            mac=master_device.mac,
            device_name=f"{master_device.device_name} (Group)",
            entity_id=virtual_entity_id,
            role="virtual_master",
            coordinator=master_device.coordinator,
        )

        # Register in primary storage and indexes
        self.devices[virtual_uuid] = virtual_device
        self._entity_to_uuid[virtual_entity_id] = virtual_uuid

        _LOGGER.debug(
            "[WiiM] Registered virtual device: %s (UUID: %s, Entity: %s)",
            virtual_device.device_name,
            virtual_uuid,
            virtual_entity_id,
        )

        return virtual_device

    def unregister_virtual_device(self, master_uuid: str) -> None:
        """Unregister a virtual group master device."""
        virtual_uuid = f"virtual_{master_uuid}"
        virtual_device = self.devices.get(virtual_uuid)

        if virtual_device:
            # Remove from indexes
            if virtual_device.entity_id:
                self._entity_to_uuid.pop(virtual_device.entity_id, None)

            # Remove from primary storage
            del self.devices[virtual_uuid]
            _LOGGER.debug("[WiiM] Unregistered virtual device: %s", virtual_device.device_name)

    def get_virtual_device_for_master(self, master_uuid: str) -> DeviceState | None:
        """Get virtual device for a master UUID."""
        virtual_uuid = f"virtual_{master_uuid}"
        return self.devices.get(virtual_uuid)

    # =========================================================================
    # Entity Naming Standardization
    # =========================================================================

    def generate_entity_id(self, device: DeviceState) -> str:
        """Generate standardized entity ID for a device."""
        if device.role == "virtual_master":
            base_name = device.device_name.replace(" (Group)", "")
            return f"media_player.{self._sanitize_name(base_name)}_group"
        else:
            return f"media_player.{self._sanitize_name(device.device_name)}"

    def _sanitize_name(self, name: str) -> str:
        """Convert device name to entity-safe format."""
        return name.lower().replace(" ", "_").replace("-", "_").replace(".", "_")

    def update_entity_id_for_device(self, identifier: str, new_entity_id: str) -> bool:
        """Update the entity ID for a device."""
        device = self.find_device(identifier)
        if not device:
            return False

        # Remove old entity mapping
        if device.entity_id:
            self._entity_to_uuid.pop(device.entity_id, None)

        # Update device and add new mapping
        device.entity_id = new_entity_id
        self._entity_to_uuid[new_entity_id] = device.uuid

        _LOGGER.debug("[WiiM] Updated entity ID for %s: %s", device.device_name, new_entity_id)
        return True

    # =========================================================================
    # Enhanced Group Management
    # =========================================================================


# Global registry instance
_registry: WiiMDeviceRegistry | None = None


def get_device_registry(hass: HomeAssistant) -> WiiMDeviceRegistry:
    """Get the global device registry instance."""
    global _registry
    if _registry is None:
        _registry = WiiMDeviceRegistry(hass)
    return _registry
