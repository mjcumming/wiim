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

from .const import DOMAIN, EQ_PRESET_MAP

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
        return next((s for s in self.speakers.values() if s.ip_address == ip), None)

    def get_speaker_by_entity_id(self, entity_id: str) -> Speaker | None:
        """Find speaker by entity ID."""
        return self.entity_id_mappings.get(entity_id)


class Speaker:
    """Represents a WiiM speaker device and its state.

    This class encapsulates all information and business logic related to a single
    WiiM speaker. It manages device properties, group membership, Home Assistant
    device registration, and provides methods for interacting with the speaker
    (e.g., group management, state retrieval). It works in conjunction with
    a `WiiMCoordinator` to receive data updates.
    """

    def __init__(self, hass: HomeAssistant, coordinator: WiiMCoordinator, config_entry: ConfigEntry):
        """Initialize a Speaker instance.

        Args:
            hass: The Home Assistant instance.
            coordinator: The WiiMDataUpdateCoordinator responsible for this speaker.
            config_entry: The config entry for this speaker.
        """
        self.hass = hass
        self.coordinator = coordinator
        self.config_entry = config_entry  # Store config entry

        # The primary UUID should come from the config_entry's unique_id,
        # which was set during config flow from the device's API.
        # This ensures the Speaker's UUID is the one Home Assistant uses for tracking.
        self._uuid: str = self.config_entry.unique_id
        if not self._uuid:
            # This should not happen if config flow is correct
            _LOGGER.error(
                "Speaker initialized without a unique_id from config entry for host %s. This is unexpected.",
                self.coordinator.client.host,
            )
            # Fallback to host or raise error, but ideally, unique_id is always present.
            self._uuid = self.coordinator.client.host  # Unstable fallback

        # --- Device Properties ---
        # These are populated by _populate_from_coordinator_data
        self.name: str = self.config_entry.title  # Initial name from config entry title
        self.model: str = ""
        self.firmware: str | None = None
        self.ip_address: str = self.coordinator.client.host  # Current IP from client
        self.mac_address: str | None = None  # Will be populated from device_info

        # --- Group State ---
        # Reflects the speaker's role and membership in a multiroom audio group.
        # This state is dynamic and updated by the coordinator.
        self.role: str = "solo"  # Current role: "solo", "master", or "slave"
        self.group_members: list[Speaker] = []  # List of Speaker objects in the same group (if master)
        self.coordinator_speaker: Speaker | None = None  # Reference to the master if this speaker is a slave

        # --- Home Assistant Integration ---
        # Manages the speaker's representation in Home Assistant.
        self.device_info: DeviceInfo | None = None  # HA DeviceInfo for registry
        self._available: bool = True  # Internal availability flag, combined with coordinator status

        # --- Media Position Tracking ---
        self._last_position_update: float | None = None  # Timestamp of last position update
        self._last_position: int | None = None  # Last known position in seconds

    async def async_setup(self, entry: ConfigEntry) -> None:
        """Complete the asynchronous setup of the speaker.

        This method populates the speaker's device information from the
        coordinator's initial data and registers the device with the
        Home Assistant device registry.

        Args:
            entry: The ConfigEntry associated with this speaker.
        """
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
        # DO NOT USE 'title' - that's the song title, not device name!
        device_name = (
            status.get("DeviceName")  # WiiM API primary field
            or status.get("device_name")  # Alternative field name
            or status.get("friendlyName")  # Common API field
            or status.get("name")  # Generic name field
            or status.get("GroupName")  # Group name field
            or status.get("ssid", "").replace("_", " ")  # Device hotspot name
            # REMOVED: or status.get("title")  # This is SONG TITLE, not device name!
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

        self.ip_address = self.coordinator.client.host
        self.mac_address = (status.get("MAC") or "").lower().replace(":", "")

        # PRIORITY 1: Use the config entry title (set correctly during config flow)
        # PRIORITY 2: Extract from API status if config entry title is generic
        config_title = self.config_entry.title
        if config_title and config_title not in ["WiiM Speaker", "WiiM Device"]:
            self.name = config_title
            _LOGGER.debug("Using device name from config entry: '%s'", self.name)
        else:
            # Fallback to API extraction only if config entry has generic name
            self.name = self._extract_device_name(status)
            _LOGGER.debug("Device name extracted from API: '%s'", self.name)

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

        _LOGGER.warning(
            "[WiiM] %s: Speaker.update_from_coordinator_data called with status keys=%s, multiroom=%s",
            self.uuid,
            list(status.keys()),
            multiroom,
        )

        # Device name is extracted ONCE during setup, not on every update
        # No need to re-extract device name on every polling cycle

        # Update group state - get role from the coordinator data
        old_role = self.role
        self.role = data.get("role", "solo")  # Role is calculated by coordinator
        _LOGGER.warning("[WiiM] %s: Role update - old_role=%s, new_role=%s", self.uuid, old_role, self.role)

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

    @property
    def uuid(self) -> str:
        """Return the unique identifier of the speaker."""
        return self._uuid

    def get_playback_state(self) -> MediaPlayerState:
        """Calculate current playbook state from coordinator data."""
        if not self.coordinator.data:
            return MediaPlayerState.OFF

        status = self.coordinator.data.get("status", {})
        # Check both 'play_status' (parsed) and 'state' (raw) for compatibility
        state = (status.get("play_status") or status.get("state", "stop")).lower()

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

        # Try volume_level first (parsed float 0-1), then vol (raw integer 0-100)
        volume_level = status.get("volume_level")
        if volume_level is not None:
            return float(volume_level)

        # Fallback to raw volume and convert
        volume = status.get("volume") or status.get("vol")
        if volume is not None:
            try:
                return int(volume) / 100
            except (ValueError, TypeError):
                return None
        return None

    def is_volume_muted(self) -> bool | None:
        """Get current mute state."""
        if not self.coordinator.data:
            return None
        status = self.coordinator.data.get("status", {})

        # Check for mute field - could be "1"/"0", True/False, or "on"/"off"
        mute = status.get("mute")
        if mute is not None:
            if isinstance(mute, bool):
                return mute
            if isinstance(mute, str):
                return mute.lower() in ("1", "on", "true", "yes")
            if isinstance(mute, int):
                return mute != 0
        return None

    # ===== MEDIA METADATA METHODS =====

    def get_media_title(self) -> str | None:
        """Get current track title."""
        if not self.coordinator.data:
            return None
        status = self.coordinator.data.get("status", {})
        return status.get("title") or status.get("Title") or status.get("track_name")

    def get_media_artist(self) -> str | None:
        """Get current artist name."""
        if not self.coordinator.data:
            return None
        status = self.coordinator.data.get("status", {})
        return status.get("artist") or status.get("Artist") or status.get("track_artist")

    def get_media_album(self) -> str | None:
        """Get current album name."""
        if not self.coordinator.data:
            return None
        status = self.coordinator.data.get("status", {})
        return status.get("album") or status.get("Album") or status.get("track_album")

    def get_media_duration(self) -> int | None:
        """Get track duration in seconds."""
        if not self.coordinator.data:
            return None
        status = self.coordinator.data.get("status", {})
        duration = status.get("duration") or status.get("track_duration")
        if duration is not None:
            try:
                return int(duration)
            except (ValueError, TypeError):
                return None
        return None

    def get_media_position(self) -> int | None:
        """Get current position in seconds."""
        if not self.coordinator.data:
            return None
        status = self.coordinator.data.get("status", {})
        position = status.get("position") or status.get("track_position")
        if position is not None:
            try:
                current_position = int(position)
                # Update position tracking if position changed
                if current_position != self._last_position:
                    import time

                    self._last_position = current_position
                    self._last_position_update = time.time()
                return current_position
            except (ValueError, TypeError):
                return None
        return None

    def get_media_position_updated_at(self) -> float | None:
        """Get position update timestamp."""
        # Return actual timestamp when position was last updated
        return self._last_position_update

    def get_media_image_url(self) -> str | None:
        """Get media image URL.

        The API parser already extracts cover art URLs from many fields
        and sets them in the 'entity_picture' field when available.
        """
        if not self.coordinator.data:
            return None
        status = self.coordinator.data.get("status", {})

        # Check entity_picture first - this is what the API parser sets
        # when it finds cover art URLs from the device
        return (
            status.get("entity_picture")
            or status.get("cover")
            or status.get("cover_url")
            or status.get("albumart")
            or status.get("album_art")
            or status.get("artwork_url")
            or status.get("art_url")
            or status.get("thumbnail")
            or status.get("pic_url")
        )

    # ===== SOURCE & AUDIO CONTROL METHODS =====

    def get_current_source(self) -> str | None:
        """Get current input source."""
        if not self.coordinator.data:
            return None
        status = self.coordinator.data.get("status", {})
        return status.get("source") or status.get("input") or status.get("mode")

    def get_shuffle_state(self) -> bool | None:
        """Get current shuffle state."""
        if not self.coordinator.data:
            return None
        status = self.coordinator.data.get("status", {})

        # Check play mode for shuffle
        play_mode = status.get("play_mode") or status.get("playmode")
        if play_mode is not None:
            # WiiM shuffle modes contain "shuffle" in the name
            return "shuffle" in str(play_mode).lower()

        # Fallback to explicit shuffle field
        shuffle = status.get("shuffle")
        if shuffle is not None:
            if isinstance(shuffle, bool):
                return shuffle
            if isinstance(shuffle, str):
                return shuffle.lower() in ("1", "on", "true", "yes")
            if isinstance(shuffle, int):
                return shuffle != 0
        return None

    def get_repeat_mode(self) -> str | None:
        """Get current repeat mode (off/one/all)."""
        if not self.coordinator.data:
            return None
        status = self.coordinator.data.get("status", {})

        # Check play mode for repeat
        play_mode = status.get("play_mode") or status.get("playmode")
        if play_mode is not None:
            play_mode_str = str(play_mode).lower()
            if "repeat_one" in play_mode_str or "single" in play_mode_str:
                return "one"
            elif "repeat_all" in play_mode_str or "repeat" in play_mode_str:
                return "all"
            else:
                return "off"

        # Fallback to explicit repeat field
        repeat = status.get("repeat")
        if repeat is not None:
            repeat_str = str(repeat).lower()
            if repeat_str in ("1", "one", "single"):
                return "one"
            elif repeat_str in ("all", "playlist"):
                return "all"
            else:
                return "off"
        return "off"  # Default to off

    def get_sound_mode(self) -> str | None:
        """Get current EQ preset/sound mode."""
        if not self.coordinator.data:
            return None
        status = self.coordinator.data.get("status", {})

        # Check for EQ preset
        eq_preset = status.get("eq_preset") or status.get("eq") or status.get("equalizer")
        if eq_preset is not None:
            # Convert numeric or string EQ values to friendly names
            eq_str = str(eq_preset).lower()

            # Try direct mapping first
            if eq_str in EQ_PRESET_MAP:
                return EQ_PRESET_MAP[eq_str]

            # Try reverse mapping for display names
            for key, display_name in EQ_PRESET_MAP.items():
                if eq_str == display_name.lower() or eq_str == key:
                    return display_name

            # Fallback to the raw value
            return str(eq_preset)
        return None

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

        NOTE: The multiroom join command is not implemented yet.
        The ConnectMasterAp command is for WiFi AP connection, not multiroom grouping.
        """
        if not speakers:
            _LOGGER.warning("No speakers provided for group join")
            return

        _LOGGER.info("Joining %d speakers to master %s", len(speakers), self.name)

        # TODO: Implement proper multiroom join commands
        # The ConnectMasterAp command is for WiFi, not multiroom grouping
        _LOGGER.error("Multiroom join not implemented - ConnectMasterAp is WiFi command, not grouping")
        raise NotImplementedError("Multiroom join commands not implemented yet")

        # try:
        #     # Send ConnectMasterAp command to each slave
        #     for slave_speaker in speakers:
        #         if slave_speaker is self:
        #             continue  # Skip self

        #         # Send join command to slave device
        #         cmd = f"ConnectMasterAp:JoinGroupMaster:{self.ip_address}:wifi0.0.0.0"
        #         _LOGGER.debug("Sending join command to %s: %s", slave_speaker.name, cmd)

        #         try:
        #             await slave_speaker.coordinator.client.send_command(cmd)
        #             _LOGGER.debug("Successfully sent join command to %s", slave_speaker.name)
        #         except Exception as err:
        #             _LOGGER.error("Failed to join speaker %s: %s", slave_speaker.name, err)
        #             # Continue with other speakers

        #     # Update group states will happen via coordinator polling
        #     # Request immediate refresh to verify group formation
        #     await self.coordinator.async_request_refresh()

        #     # Also refresh slave coordinators to get updated state quickly
        #     for slave_speaker in speakers:
        #         if slave_speaker is not self:
        #             try:
        #                 await slave_speaker.coordinator.async_request_refresh()
        #             except Exception as err:
        #                 _LOGGER.debug("Could not refresh slave coordinator %s: %s", slave_speaker.name, err)

        #     _LOGGER.info("Group join commands sent successfully")

        # except Exception as err:
        #     _LOGGER.error("Failed to join group: %s", err)
        #     raise

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
                cmd = f"multiroom:SlaveKickout:{self.ip_address}"
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

    async def _populate_from_coordinator_data(self) -> None:
        """Populate speaker attributes from the latest coordinator data.

        This method should be called after the coordinator has fetched new data.
        """
        if not self.coordinator.data:
            _LOGGER.debug("Coordinator data not available for %s, skipping population", self.name)
            return

        device_info_data = self.coordinator.data.get("device_info", {})
        status_data = self.coordinator.data.get("status", {})

        # Update name if it has changed on the device
        # The API might provide 'name', 'DeviceName', 'friendlyName', etc.
        # Prefer name from device_info, then status, then keep existing.
        api_device_name = (
            device_info_data.get("name") or device_info_data.get("DeviceName") or status_data.get("name")
        )  # Adjust keys as per actual API response

        if api_device_name and self.name != api_device_name:
            _LOGGER.info(
                "Device name changed for %s: from '%s' to '%s'",
                self.uuid,
                self.name,
                api_device_name,
            )
            self.name = api_device_name
            # Update HA device registry if name changes
            await self._update_device_registry_name()

        self.model = device_info_data.get("model", self.model)
        self.firmware = device_info_data.get("firmware", self.firmware)
        self.mac_address = device_info_data.get("mac", self.mac_address)  # Ensure 'mac' key is correct
        self.ip_address = self.coordinator.client.host  # IP can change, update from client

        # The self._uuid is set from config_entry.unique_id and should be stable.
        # We can verify if the API still reports the same UUID.
        api_uuid = device_info_data.get("uuid")
        if api_uuid and self._uuid != api_uuid:
            _LOGGER.warning(
                "Mismatch between stored UUID (%s) and API reported UUID (%s) for host %s. "
                "The stored UUID from initial setup will be maintained. This might indicate an issue.",
                self._uuid,
                api_uuid,
                self.ip_address,
            )

        # Group role and other attributes are updated by update_from_coordinator_data

    async def _update_device_registry_name(self) -> None:
        """Update the device name in the Home Assistant device registry."""
        try:
            device_registry = dr.async_get(self.hass)
            device_entry = device_registry.async_get_device(identifiers={(DOMAIN, self.uuid)})
            if device_entry and device_entry.name != self.name:
                device_registry.async_update_device(
                    device_entry.id,
                    name=self.name,
                )
                _LOGGER.debug("Updated device name in registry for %s to %s", self.uuid, self.name)

                # Update our stored DeviceInfo
                if self.device_info:
                    self.device_info = DeviceInfo(
                        identifiers=self.device_info["identifiers"],
                        manufacturer=self.device_info["manufacturer"],
                        name=self.name,
                        model=self.device_info["model"],
                        sw_version=self.device_info.get("sw_version"),
                    )
        except Exception as err:
            _LOGGER.warning("Failed to update device registry name: %s", err)


# Helper functions
def get_wiim_data(hass: HomeAssistant) -> WiimData:
    """Get the WiimData instance."""
    return hass.data[DOMAIN]["data"]


def get_speaker_from_config_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> Speaker:
    """Get speaker from config entry with standardized error handling.

    SINGLE SOURCE OF TRUTH for platform setup speaker retrieval.
    All platforms should use this instead of duplicating the access pattern.
    """
    try:
        return hass.data[DOMAIN][config_entry.entry_id]["speaker"]
    except KeyError as err:
        _LOGGER.error("Speaker not found for config entry %s: %s", config_entry.entry_id, err)
        raise RuntimeError(f"Speaker not found for {config_entry.entry_id}") from err


def get_or_create_speaker(hass: HomeAssistant, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> Speaker:
    """Get existing speaker or create new one."""
    data = get_wiim_data(hass)
    uuid = config_entry.unique_id
    if uuid not in data.speakers:
        data.speakers[uuid] = Speaker(hass, coordinator, config_entry)
        _LOGGER.debug("Created new speaker: %s", uuid)
    return data.speakers[uuid]
