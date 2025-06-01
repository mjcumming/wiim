"""State management utility for WiiM devices.

Handles complex state resolution logic for master/slave relationships
and effective status determination.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from ..coordinator import WiiMCoordinator

_LOGGER = logging.getLogger(__name__)


class StateManager:
    """Manages state resolution for WiiM devices, especially in group configurations."""

    def __init__(self, coordinator: WiiMCoordinator, hass: HomeAssistant) -> None:
        """Initialize state manager."""
        self.coordinator = coordinator
        self.hass = hass

    def get_effective_status(self) -> dict[str, Any]:
        """Get effective status, handling master/slave relationships."""
        role = self.coordinator.data.get("role") if self.coordinator.data else "solo"

        _LOGGER.debug("[WiiM] %s: role=%s", self.coordinator.client.host, role)

        if role == "slave":
            return self._get_slave_effective_status()

        # For solo and master devices, return own status
        status = self.coordinator.data.get("status", {}) if self.coordinator.data else {}
        _LOGGER.debug("[WiiM] %s: returning own status: %s", self.coordinator.client.host, status)
        return status

    def _get_slave_effective_status(self) -> dict[str, Any]:
        """Get effective status for slave devices by mirroring master status."""
        master_id = self.coordinator.client.group_master
        multiroom = self.coordinator.data.get("multiroom", {}) if self.coordinator.data else {}
        my_ip = self.coordinator.client.host
        my_uuid = self.coordinator.data.get("status", {}).get("device_id") if self.coordinator.data else None

        _LOGGER.debug(
            "[WiiM] Slave %s: group_master=%s, multiroom=%s, my_ip=%s, my_uuid=%s",
            self.coordinator.client.host,
            master_id,
            multiroom,
            my_ip,
            my_uuid,
        )

        # If group_master is set, try to match by IP or UUID
        if master_id:
            master_coord = self._find_master_by_id(master_id)
            if master_coord:
                status = master_coord.data.get("status", {}) if master_coord.data else {}
                _LOGGER.debug(
                    "[WiiM] Slave %s: mirroring master's status by id: %s",
                    self.coordinator.client.host,
                    status,
                )
                return status

        # If group_master is None, search all coordinators for a master whose slave_list includes this device
        _LOGGER.debug(
            "[WiiM] Slave %s: searching for master by slave_list (my_ip=%s, my_uuid=%s)",
            self.coordinator.client.host,
            my_ip,
            my_uuid,
        )

        master_coord = self._find_master_by_slave_list(my_ip, my_uuid)
        if master_coord:
            return master_coord.data.get("status", {}) if master_coord.data else {}

        # Could not locate the master in current coordinators – try to
        # automatically start a config-flow for it if we know its IP.
        _LOGGER.debug(
            "[WiiM] Slave %s: could not find master to mirror (master not yet set up)",
            self.coordinator.client.host,
        )

        self._attempt_master_discovery(master_id, multiroom)
        return {}

    def _find_master_by_id(self, master_id: str) -> WiiMCoordinator | None:
        """Find master coordinator by master ID (IP or UUID)."""
        for coord in self._get_all_coordinators():
            host = coord.client.host
            uuid = coord.data.get("status", {}).get("device_id") if coord.data else None
            _LOGGER.debug(
                "[WiiM] Slave %s: checking coord host=%s, uuid=%s against master_id=%s",
                self.coordinator.client.host,
                host,
                uuid,
                master_id,
            )
            if host == master_id or uuid == master_id:
                return coord
        return None

    def _find_master_by_slave_list(self, my_ip: str, my_uuid: str | None) -> WiiMCoordinator | None:
        """Find master coordinator by checking slave lists."""
        for coord in self._get_all_coordinators():
            # Check if this coordinator is a master
            if not coord.data or coord.data.get("role") != "master":
                continue

            # Check master's multiroom info for this slave
            master_multiroom = coord.data.get("multiroom", {})
            slave_list = master_multiroom.get("slave_list", [])
            _LOGGER.debug(
                "[WiiM] Slave %s: checking master %s slave_list=%s",
                self.coordinator.client.host,
                coord.client.host,
                slave_list,
            )

            for slave in slave_list:
                if isinstance(slave, dict):
                    slave_ip = slave.get("ip")
                    slave_uuid = slave.get("uuid")
                    _LOGGER.debug(
                        "[WiiM] Slave %s: comparing to slave_ip=%s, slave_uuid=%s",
                        self.coordinator.client.host,
                        slave_ip,
                        slave_uuid,
                    )
                    if (my_ip and my_ip == slave_ip) or (my_uuid and my_uuid == slave_uuid):
                        _LOGGER.debug(
                            "[WiiM] Slave %s: found master %s by slave_list",
                            self.coordinator.client.host,
                            coord.client.host,
                        )
                        return coord
        return None

    def _attempt_master_discovery(self, master_id: str | None, multiroom: dict[str, Any]) -> None:
        """Attempt to discover and import an unknown master device."""
        # If the device advertised the master IP/UUID, attempt an import.
        potential_master = master_id or multiroom.get("master_ip") or multiroom.get("master")
        if potential_master and isinstance(potential_master, str) and "." in potential_master:
            master_ip = potential_master
            # Check if we already have a coordinator for that IP
            if not any(hasattr(c, "client") and c.client.host == master_ip for c in self._get_all_coordinators()):
                _LOGGER.debug(
                    "[WiiM] Slave %s: launching import flow for unknown master %s",
                    self.coordinator.client.host,
                    master_ip,
                )
                # Schedule without awaiting – running inside property getter
                self.hass.async_create_task(
                    self.hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={"source": "import"},
                        data={"host": master_ip},
                    )
                )

    def _get_all_coordinators(self) -> list[WiiMCoordinator]:
        """Get all coordinators from hass.data."""
        coordinators = []
        for entry_data in self.hass.data.get(DOMAIN, {}).values():
            if isinstance(entry_data, dict) and "coordinator" in entry_data:
                coord = entry_data["coordinator"]
                if hasattr(coord, "client"):
                    coordinators.append(coord)
        return coordinators
