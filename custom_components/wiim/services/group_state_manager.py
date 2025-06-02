"""Group State Manager for WiiM Integration.

Handles state change detection and cached group membership management.
Only performs expensive operations when device roles actually change.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry

from ..const import DOMAIN
from .device_registry import GroupState, get_device_registry

if TYPE_CHECKING:
    from ..coordinator import WiiMCoordinator

_LOGGER = logging.getLogger(__name__)


class GroupStateManager:
    """Manages group state changes and cached memberships for a device."""

    def __init__(self, coordinator: WiiMCoordinator, hass: HomeAssistant) -> None:
        """Initialize the group state manager."""
        self.coordinator = coordinator
        self.hass = hass
        self.device_registry = get_device_registry(hass)

        # Current cached state
        self._current_state: GroupState | None = None

        _LOGGER.debug("[WiiM] Group state manager initialized for %s", coordinator.client.host)

    def update_from_status(self, status: dict, multiroom: dict) -> bool:
        """Update group state from coordinator data.

        Returns True if group state changed and cache needs updating.
        """
        # Detect current role using the simple WiiM API fields
        new_role = self._detect_role(status, multiroom)
        new_master_uuid = status.get("master_uuid") if new_role == "slave" else None

        # Check if state changed
        if self._current_state is None:
            # First time - initialize state
            self._current_state = GroupState(role=new_role, master_uuid=new_master_uuid)
            self._update_cached_members(new_role, multiroom)
            self._cache_state()
            return True

        # Check for role or master changes
        if self._current_state.role != new_role or self._current_state.master_uuid != new_master_uuid:
            _LOGGER.debug(
                "[WiiM] %s: Role changed from %s to %s (master: %s -> %s)",
                self.coordinator.client.host,
                self._current_state.role,
                new_role,
                self._current_state.master_uuid,
                new_master_uuid,
            )

            # Update state and recalculate members
            self._current_state.role = new_role
            self._current_state.master_uuid = new_master_uuid
            self._update_cached_members(new_role, multiroom)
            self._cache_state()
            return True

        return False

    def get_cached_group_members(self) -> list[str]:
        """Get cached group members (entity IDs)."""
        if self._current_state is None:
            return []
        return self._current_state.group_members.copy()

    def get_cached_group_leader(self) -> str | None:
        """Get cached group leader entity ID."""
        if self._current_state is None:
            return None
        return self._current_state.group_leader

    def get_current_role(self) -> str:
        """Get current device role."""
        if self._current_state is None:
            return "solo"
        return self._current_state.role

    def _detect_role(self, status: dict, multiroom: dict) -> str:
        """Detect device role using simple WiiM API indicators."""
        # Use the simple group field that WiiM provides
        if status.get("group") == "1":
            return "slave"

        # Check if we have slaves (making us a master)
        if multiroom.get("slaves", 0) > 0:
            return "master"

        # Default to solo
        return "solo"

    def _update_cached_members(self, role: str, multiroom: dict) -> None:
        """Update cached group members based on role."""
        if role == "solo":
            self._current_state.group_members = []
            self._current_state.group_leader = None

        elif role == "master":
            # For masters, include self + all slaves
            members = [self._get_own_entity_id()]
            leader = self._get_own_entity_id()

            # Add slave entity IDs
            slave_list = multiroom.get("slave_list", [])
            for slave in slave_list:
                if isinstance(slave, dict) and slave.get("ip"):
                    slave_entity_id = self._find_entity_id_by_ip(slave["ip"])
                    if slave_entity_id:
                        members.append(slave_entity_id)

            self._current_state.group_members = members
            self._current_state.group_leader = leader

        elif role == "slave":
            # For slaves, find master and get full group
            master_uuid = self._current_state.master_uuid
            if master_uuid:
                master_coord = self.device_registry.get_device_by_uuid(master_uuid)
                if master_coord and master_coord.data:
                    master_multiroom = master_coord.data.get("multiroom", {})
                    members = [self._find_entity_id_by_ip(master_coord.client.host)]
                    leader = self._find_entity_id_by_ip(master_coord.client.host)

                    # Add all slaves from master's list
                    slave_list = master_multiroom.get("slave_list", [])
                    for slave in slave_list:
                        if isinstance(slave, dict) and slave.get("ip"):
                            slave_entity_id = self._find_entity_id_by_ip(slave["ip"])
                            if slave_entity_id:
                                members.append(slave_entity_id)

                    self._current_state.group_members = [m for m in members if m]  # Filter None values
                    self._current_state.group_leader = leader
                else:
                    # Fallback if master not found
                    self._current_state.group_members = [self._get_own_entity_id()]
                    self._current_state.group_leader = None

    def _get_own_entity_id(self) -> str:
        """Get this device's entity ID."""
        # Use IP-based entity ID pattern
        ip_normalized = self.coordinator.client.host.replace(".", "_")
        return f"media_player.wiim_{ip_normalized}"

    def _find_entity_id_by_ip(self, ip: str) -> str | None:
        """Find entity ID for a given IP address."""
        # First try device registry lookup
        coordinator = self.device_registry.get_device_by_ip(ip)
        if coordinator:
            # Try to find entity using entity registry
            entity_registry_inst = entity_registry.async_get(self.hass)

            # Look for WiiM entities that might match this IP
            for entity_entry in entity_registry_inst.entities.values():
                if (
                    entity_entry.platform == DOMAIN
                    and entity_entry.entity_id.startswith("media_player.")
                    and ip.replace(".", "_") in entity_entry.entity_id
                ):
                    return entity_entry.entity_id

        # Fallback to expected entity ID pattern
        ip_normalized = ip.replace(".", "_")
        return f"media_player.wiim_{ip_normalized}"

    def _cache_state(self) -> None:
        """Cache the current state in the device registry."""
        if self._current_state:
            self.device_registry.set_group_state(self.coordinator.client.host, self._current_state)


def create_group_state_manager(coordinator: WiiMCoordinator, hass: HomeAssistant) -> GroupStateManager:
    """Factory function to create a group state manager."""
    return GroupStateManager(coordinator, hass)
