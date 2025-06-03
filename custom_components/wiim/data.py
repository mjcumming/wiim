"""Core data layer for WiiM integration."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from homeassistant.components.media_player import MediaPlayerState
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import WiiMCoordinator

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "WiimData",
    "Speaker",
    "get_wiim_data",
    "get_or_create_speaker",
]


@dataclass
class WiimData:
    """Central registry for all WiiM speakers (like SonosData)."""

    hass: HomeAssistant
    speakers: dict[str, Speaker] = field(default_factory=dict)
    entity_id_mappings: dict[str, Speaker] = field(default_factory=dict)
    discovery_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def get_speaker_by_ip(self, ip: str) -> Speaker | None:
        """Find speaker by IP address."""
        return next((s for s in self.speakers.values() if s.ip == ip), None)

    def get_speaker_by_entity_id(self, entity_id: str) -> Speaker | None:
        """Find speaker by entity ID."""
        return self.entity_id_mappings.get(entity_id)


class Speaker:
    """Rich speaker object with business logic (like SonosSpeaker)."""

    def __init__(self, hass: HomeAssistant, uuid: str, coordinator: WiiMCoordinator):
        self.hass = hass
        self.uuid = uuid
        self.coordinator = coordinator

        # Device properties
        self.name: str = ""
        self.model: str = ""
        self.firmware: str | None = None
        self.ip: str = ""
        self.mac: str = ""

        # Group state
        self.role: str = "solo"  # solo/master/slave
        self.group_members: list[Speaker] = []
        self.coordinator_speaker: Speaker | None = None

        # HA integration
        self.device_info: DeviceInfo | None = None
        self._available: bool = True

    async def async_setup(self, entry: ConfigEntry) -> None:
        """Complete speaker setup and HA device registration."""
        await self._populate_device_info()
        await self._register_ha_device(entry)
        _LOGGER.info("Speaker setup complete for UUID: %s (Name: %s)", self.uuid, self.name)

    def _extract_device_name(self, status: dict) -> str:
        """Extract device name from status data with fallback logic.

        This is the SINGLE SOURCE OF TRUTH for device name extraction.
        Used by both initial setup and runtime updates to ensure consistency.

        Args:
            status: Status dictionary from API response

        Returns:
            Clean device name string, never empty or containing IP addresses
        """
        # Extract device name with multiple fallback attempts
        device_name = (
            status.get("DeviceName")  # WiiM API primary field
            or status.get("device_name")  # Alternative field name
            or status.get("GroupName")  # Group name field
            or status.get("ssid", "").replace("_", " ")  # Device hotspot name
            or "WiiM Speaker"  # Clean final fallback (no IP)
        )

        # Clean up the device name
        clean_name = device_name.strip()
        if not clean_name or clean_name.lower() in ["unknown", "none", ""]:
            clean_name = "WiiM Speaker"

        return clean_name

    async def _populate_device_info(self) -> None:
        """Extract device info from coordinator data."""
        status = self.coordinator.data.get("status", {}) if self.coordinator.data else {}

        # Debug: Log available fields for device naming
        _LOGGER.debug(
            "Available status fields for device naming: %s",
            {k: v for k, v in status.items() if any(name in k.lower() for name in ["name", "device", "group", "ssid"])},
        )

        self.ip = self.coordinator.client.host
        self.mac = (status.get("MAC") or "").lower().replace(":", "")

        # Single source of truth for device name extraction
        self.name = self._extract_device_name(status)
        _LOGGER.debug("Device name extracted: '%s'", self.name)

        self.model = status.get("project") or "WiiM Speaker"
        self.firmware = status.get("firmware")

        # Group info
        multiroom = self.coordinator.data.get("multiroom", {}) if self.coordinator.data else {}
        self.role = multiroom.get("role", "solo")

    async def _register_ha_device(self, entry: ConfigEntry) -> None:
        """Register device in HA registry."""
        dev_reg = dr.async_get(self.hass)
        identifiers = {(DOMAIN, self.uuid)}

        dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers=identifiers,
            manufacturer="WiiM",
            name=self.name,
            model=self.model,
            sw_version=self.firmware,
        )

        # Store DeviceInfo for entities
        self.device_info = DeviceInfo(
            identifiers=identifiers,
            manufacturer="WiiM",
            name=self.name,
            model=self.model,
            sw_version=self.firmware,
        )

    def async_write_entity_states(self) -> None:
        """Notify all entities of state changes (event-driven)."""
        async_dispatcher_send(self.hass, f"wiim_state_updated_{self.uuid}")

    def update_from_coordinator_data(self, data: dict) -> None:
        """Update speaker state from coordinator data."""
        status = data.get("status", {})
        multiroom = data.get("multiroom", {})

        # Update device name using single source of truth
        new_name = self._extract_device_name(status)
        if self.name != new_name:
            old_name = self.name
            self.name = new_name
            _LOGGER.debug("Speaker %s name updated: %s -> %s", self.uuid, old_name, new_name)

            # Update device registry with new name
            self._update_device_registry_name(new_name)

        # Update group state
        old_role = self.role
        self.role = multiroom.get("role", "solo")

        # If role changed, notify entities
        if old_role != self.role:
            _LOGGER.debug("Speaker %s role changed: %s -> %s", self.uuid, old_role, self.role)
            self.async_write_entity_states()

    @property
    def available(self) -> bool:
        """Return if speaker is available."""
        return self._available and self.coordinator.last_update_success

    @property
    def is_group_coordinator(self) -> bool:
        """Return if this speaker is a group coordinator."""
        return self.role == "master" or (self.role == "solo" and not self.group_members)

    def get_playback_state(self) -> MediaPlayerState:
        """Calculate current playback state from coordinator data."""
        if not self.coordinator.data:
            return MediaPlayerState.OFF

        status = self.coordinator.data.get("status", {})
        state = status.get("state", "stop").lower()

        if state == "play":
            return MediaPlayerState.PLAYING
        elif state == "pause":
            return MediaPlayerState.PAUSED
        elif state == "stop":
            return MediaPlayerState.IDLE
        else:
            return MediaPlayerState.OFF

    def get_volume_level(self) -> float | None:
        """Get current volume level (0.0-1.0)."""
        if not self.coordinator.data:
            return None
        status = self.coordinator.data.get("status", {})
        volume = status.get("vol")
        return int(volume) / 100 if volume is not None else None

    def get_group_member_entity_ids(self) -> list[str]:
        """Get entity IDs of all group members.

        Returns list with master first (HA convention), then all slaves.
        Returns empty list if not in a group.
        """
        entity_ids = []

        if self.role == "master":
            # Master: self first, then all slaves
            master_entity_id = self._get_entity_id_for_speaker(self)
            if master_entity_id:
                entity_ids.append(master_entity_id)

            # Add slave entity IDs
            for slave in self.group_members:
                if slave is not self:  # Skip self
                    slave_entity_id = self._get_entity_id_for_speaker(slave)
                    if slave_entity_id:
                        entity_ids.append(slave_entity_id)

        elif self.role == "slave" and self.coordinator_speaker:
            # Slave: master first, then self, then other slaves
            master_entity_id = self._get_entity_id_for_speaker(self.coordinator_speaker)
            if master_entity_id:
                entity_ids.append(master_entity_id)

            # Add all slaves (including self)
            for slave in self.coordinator_speaker.group_members:
                if slave is not self.coordinator_speaker:  # Skip master
                    slave_entity_id = self._get_entity_id_for_speaker(slave)
                    if slave_entity_id:
                        entity_ids.append(slave_entity_id)

        return entity_ids

    def _get_entity_id_for_speaker(self, speaker: Speaker) -> str | None:
        """Find entity ID for a given speaker."""
        data = get_wiim_data(self.hass)
        # Reverse lookup in entity_id_mappings
        for entity_id, mapped_speaker in data.entity_id_mappings.items():
            if mapped_speaker is speaker:
                return entity_id
        return None

    def resolve_entity_ids_to_speakers(self, entity_ids: list[str]) -> list[Speaker]:
        """Convert entity IDs to Speaker objects."""
        data = get_wiim_data(self.hass)
        speakers = []

        for entity_id in entity_ids:
            speaker = data.get_speaker_by_entity_id(entity_id)
            if speaker:
                speakers.append(speaker)
            else:
                _LOGGER.warning("Could not resolve entity_id to speaker: %s", entity_id)

        return speakers

    # Group management methods
    async def async_join_group(self, speakers: list[Speaker]) -> None:
        """Join speakers to this speaker as group master.

        This speaker becomes the master, provided speakers become slaves.
        Uses LinkPlay ConnectMasterAp API command.
        """
        if not speakers:
            _LOGGER.warning("No speakers provided for group join")
            return

        _LOGGER.info("Joining %d speakers to master %s", len(speakers), self.name)

        try:
            # Send ConnectMasterAp command to each slave
            for slave_speaker in speakers:
                if slave_speaker is self:
                    continue  # Skip self

                # Send join command to slave device
                cmd = f"ConnectMasterAp:JoinGroupMaster:{self.ip}:wifi0.0.0.0"
                _LOGGER.debug("Sending join command to %s: %s", slave_speaker.name, cmd)

                try:
                    await slave_speaker.coordinator.client.send_command(cmd)
                    _LOGGER.debug("Successfully sent join command to %s", slave_speaker.name)
                except Exception as err:
                    _LOGGER.error("Failed to join speaker %s: %s", slave_speaker.name, err)
                    # Continue with other speakers

            # Update group states will happen via coordinator polling
            # Request immediate refresh to verify group formation
            await self.coordinator.async_request_refresh()

            # Also refresh slave coordinators to get updated state quickly
            for slave_speaker in speakers:
                if slave_speaker is not self:
                    try:
                        await slave_speaker.coordinator.async_request_refresh()
                    except Exception as err:
                        _LOGGER.debug("Could not refresh slave coordinator %s: %s", slave_speaker.name, err)

            _LOGGER.info("Group join commands sent successfully")

        except Exception as err:
            _LOGGER.error("Failed to join group: %s", err)
            raise

    async def async_leave_group(self) -> None:
        """Remove this speaker from its group.

        Handles both slave leaving group and master disbanding group.
        Uses LinkPlay SlaveKickout or Ungroup API commands.
        """
        _LOGGER.info("Speaker %s leaving group (current role: %s)", self.name, self.role)

        try:
            if self.role == "slave" and self.coordinator_speaker:
                # Slave leaving: send SlaveKickout command to master
                master = self.coordinator_speaker
                cmd = f"multiroom:SlaveKickout:{self.ip}"
                _LOGGER.debug("Sending slave kickout command to master %s: %s", master.name, cmd)

                await master.coordinator.client.send_command(cmd)
                _LOGGER.info("Successfully sent leave command for slave %s", self.name)

                # Refresh master coordinator to update group state
                await master.coordinator.async_request_refresh()

            elif self.role == "master":
                # Master leaving: disband entire group
                cmd = "multiroom:Ungroup"
                _LOGGER.debug("Sending ungroup command to master %s: %s", self.name, cmd)

                await self.coordinator.client.send_command(cmd)
                _LOGGER.info("Successfully sent ungroup command for master %s", self.name)

                # Refresh all slave coordinators to update their state
                for slave in self.group_members:
                    if slave is not self:
                        try:
                            await slave.coordinator.async_request_refresh()
                        except Exception as err:
                            _LOGGER.debug("Could not refresh slave coordinator %s: %s", slave.name, err)

            else:
                _LOGGER.warning("Speaker %s not in a group (role: %s), nothing to leave", self.name, self.role)
                return

            # Request immediate refresh for this speaker
            await self.coordinator.async_request_refresh()
            _LOGGER.info("Group leave completed for %s", self.name)

        except Exception as err:
            _LOGGER.error("Failed to leave group: %s", err)
            raise

    def _update_device_registry_name(self, new_name: str) -> None:
        """Update device registry with new name."""
        try:
            dev_reg = dr.async_get(self.hass)
            identifiers = {(DOMAIN, self.uuid)}

            # Find device by identifiers
            device = dev_reg.async_get_device(identifiers=identifiers)
            if device:
                dev_reg.async_update_device(device.id, name=new_name)
                _LOGGER.debug("Updated device registry name for %s: %s", self.uuid, new_name)

                # Update our stored DeviceInfo
                if self.device_info:
                    self.device_info = DeviceInfo(
                        identifiers=self.device_info["identifiers"],
                        manufacturer=self.device_info["manufacturer"],
                        name=new_name,
                        model=self.device_info["model"],
                        sw_version=self.device_info.get("sw_version"),
                    )
        except Exception as err:
            _LOGGER.warning("Failed to update device registry name: %s", err)


# Helper functions
def get_wiim_data(hass: HomeAssistant) -> WiimData:
    """Get the WiimData instance."""
    return hass.data[DOMAIN]["data"]


def get_or_create_speaker(hass: HomeAssistant, uuid: str, coordinator: WiiMCoordinator) -> Speaker:
    """Get existing speaker or create new one."""
    data = get_wiim_data(hass)
    if uuid not in data.speakers:
        data.speakers[uuid] = Speaker(hass, uuid, coordinator)
        _LOGGER.debug("Created new speaker: %s", uuid)
    return data.speakers[uuid]
