"""Core data layer for WiiM integration.

ARCHITECTURAL IMPROVEMENTS (v2.0):
==================================

This module has been enhanced based on comprehensive code review to address
critical issues and implement architectural best practices:

1. CRITICAL FIX: Group Membership Population
   - update_from_coordinator_data() now actually populates self.group_members and self.coordinator_speaker
   - Master speakers maintain authoritative group state via _update_master_group_state()
   - Slave speakers maintain master references via _update_slave_group_state()
   - Group state resolution works incrementally over polling cycles
   - Proper "Cannot find slave/master" logging for troubleshooting

2. CONSOLIDATED UPDATE LOGIC
   - update_from_coordinator_data() is now SINGLE SOURCE OF TRUTH for all updates
   - Removed redundant _populate_from_coordinator_data() method
   - Robust device name extraction with _extract_device_name_from_update()
   - Automatic device registry updates when names change

3. BIDIRECTIONAL ENTITY MAPPING (Performance)
   - WiimData now has O(1) entity ID to Speaker lookup via speaker_to_entity_mappings
   - register_entity()/unregister_entity() maintain bidirectional mappings
   - _get_entity_id_for_speaker() now uses O(1) lookup instead of O(n) loop

4. MAC ADDRESS CONSISTENCY
   - _normalize_mac_address() standardizes to lowercase colon-separated format
   - Consistent formatting for Home Assistant device registry
   - Handles various input formats (with/without colons/dashes)

5. MASTER-MANAGED GROUP STATE ARCHITECTURE
   - Masters resolve slave IPs to Speaker objects using global WiimData registry
   - Slaves maintain simple reference to master Speaker object
   - Clean separation: masters manage groups, slaves reference masters
   - Group state converges naturally over multiple coordinator polling cycles

INTEGRATION FLOW:
================
1. Coordinator polls device API (getStatusEx, getSlaveList)
2. Coordinator calls speaker.update_from_coordinator_data(processed_data)
3. Speaker resolves group relationships using WiimData registry
4. Entity state updates triggered only when significant changes occur
5. Home Assistant group operations use resolved Speaker objects

CRITICAL DEPENDENCIES:
=====================
- Entity registration MUST call wiim_data.register_entity() for group resolution
- All speakers in a group must be discovered before group state can be fully populated
- Master speakers need successful getSlaveList responses to populate group_members
- Slave speakers need master_uuid or master_ip in coordinator data to find masters

This architecture ensures reliable group management while maintaining clean
separation of concerns and efficient performance.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from homeassistant.components.media_player import MediaPlayerState
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
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
    """Central registry for all WiiM speakers (like SonosData).

    Enhanced with comprehensive O(1) lookups for UUID, IP, and entity_id.
    """

    hass: HomeAssistant
    speakers: dict[str, Speaker] = field(default_factory=dict)  # UUID -> Speaker
    entity_id_mappings: dict[str, Speaker] = field(default_factory=dict)  # entity_id -> Speaker
    speaker_to_entity_mappings: dict[Speaker, str] = field(default_factory=dict)  # Speaker -> entity_id
    ip_mappings: dict[str, Speaker] = field(default_factory=dict)  # IP -> Speaker (NEW)
    discovery_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def get_speaker_by_uuid(self, uuid: str) -> Speaker | None:
        """Find speaker by UUID (O(1) lookup).

        This is the primary key lookup since speakers dict is keyed by UUID.
        """
        return self.speakers.get(uuid)

    def get_speaker_by_ip(self, ip: str) -> Speaker | None:
        """Find speaker by IP address (O(1) lookup)."""
        return self.ip_mappings.get(ip)

    def get_speaker_by_entity_id(self, entity_id: str) -> Speaker | None:
        """Find speaker by entity ID (O(1) lookup)."""
        return self.entity_id_mappings.get(entity_id)

    def register_speaker(self, speaker: Speaker) -> None:
        """Register speaker with all lookup indices.

        Ensures consistent cross-referencing between UUID, IP, and entity_id.
        """
        uuid = speaker.uuid
        ip = speaker.ip_address

        # Primary storage by UUID
        self.speakers[uuid] = speaker

        # IP address mapping for multiroom lookups
        if ip:
            # Remove old IP mapping if speaker IP changed
            old_ip = None
            for existing_ip, existing_speaker in self.ip_mappings.items():
                if existing_speaker is speaker and existing_ip != ip:
                    old_ip = existing_ip
                    break
            if old_ip:
                self.ip_mappings.pop(old_ip, None)
                _LOGGER.debug("Updated IP mapping for %s: %s -> %s", speaker.name, old_ip, ip)

            self.ip_mappings[ip] = speaker

        _LOGGER.debug("Registered speaker %s: UUID=%s, IP=%s", speaker.name, uuid, ip)

    def unregister_speaker(self, speaker: Speaker) -> None:
        """Remove speaker from all lookup indices."""
        uuid = speaker.uuid
        ip = speaker.ip_address

        # Remove from primary storage
        self.speakers.pop(uuid, None)

        # Remove IP mapping
        if ip:
            self.ip_mappings.pop(ip, None)

        # Remove entity mapping
        entity_id = self.speaker_to_entity_mappings.pop(speaker, None)
        if entity_id:
            self.entity_id_mappings.pop(entity_id, None)

        _LOGGER.debug("Unregistered speaker %s: UUID=%s, IP=%s", speaker.name, uuid, ip)

    def register_entity(self, entity_id: str, speaker: Speaker) -> None:
        """Register bidirectional entity ID to Speaker mapping."""
        self.entity_id_mappings[entity_id] = speaker
        self.speaker_to_entity_mappings[speaker] = entity_id

    def unregister_entity(self, entity_id: str) -> None:
        """Remove entity ID to Speaker mapping."""
        if entity_id in self.entity_id_mappings:
            speaker = self.entity_id_mappings.pop(entity_id)
            self.speaker_to_entity_mappings.pop(speaker, None)

    def get_entity_id_for_speaker(self, speaker: Speaker) -> str | None:
        """Get entity ID for speaker (O(1) lookup)."""
        return self.speaker_to_entity_mappings.get(speaker)

    def validate_speaker_mappings(self) -> dict[str, list[str]]:
        """Validate all speaker mappings for consistency.

        Returns dict of issues found for debugging.
        """
        issues = {"missing_ip_mappings": [], "orphaned_ip_mappings": [], "inconsistent_entity_mappings": []}

        # Check that all speakers have IP mappings
        for uuid, speaker in self.speakers.items():
            if speaker.ip_address and speaker.ip_address not in self.ip_mappings:
                issues["missing_ip_mappings"].append(f"{speaker.name} ({uuid}) missing IP {speaker.ip_address}")

        # Check for orphaned IP mappings
        for ip, speaker in self.ip_mappings.items():
            if speaker.uuid not in self.speakers:
                issues["orphaned_ip_mappings"].append(f"IP {ip} -> orphaned speaker {speaker.name}")

        # Check entity mapping consistency
        for entity_id, speaker in self.entity_id_mappings.items():
            if self.speaker_to_entity_mappings.get(speaker) != entity_id:
                issues["inconsistent_entity_mappings"].append(
                    f"Entity {entity_id} -> {speaker.name} mapping inconsistency"
                )

        return issues

    def update_speaker_ip(self, speaker: Speaker, new_ip: str) -> None:
        """Update speaker's IP address and refresh lookup indices."""
        old_ip = speaker.ip_address

        # Remove old IP mapping
        if old_ip and old_ip in self.ip_mappings:
            self.ip_mappings.pop(old_ip, None)

        # Update speaker's IP
        speaker.ip_address = new_ip

        # Add new IP mapping
        if new_ip:
            self.ip_mappings[new_ip] = speaker

        _LOGGER.debug("Updated speaker %s IP mapping: %s -> %s", speaker.name, old_ip, new_ip)


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
        self._uuid: str = self.config_entry.unique_id or ""
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

        # Ensure speaker is properly registered in all lookup indices
        wiim_data = get_wiim_data(self.hass)
        wiim_data.register_speaker(self)

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

    def _normalize_mac_address(self, mac: str | None) -> str | None:
        """Normalize MAC address to lowercase colon-separated format.

        Args:
            mac: MAC address in any format (with/without colons/dashes)

        Returns:
            MAC address in lowercase colon-separated format (aa:bb:cc:dd:ee:ff)
            or None if invalid
        """
        if not mac:
            return None

        # Remove existing separators and convert to lowercase
        clean_mac = mac.lower().replace(":", "").replace("-", "").replace(" ", "")

        if len(clean_mac) != 12 or not all(c in "0123456789abcdef" for c in clean_mac):
            _LOGGER.warning("Invalid MAC address format: %s", mac)
            return None

        # Insert colons every 2 characters
        return ":".join(clean_mac[i : i + 2] for i in range(0, 12, 2))

    def _extract_device_name_from_update(self, device_info: dict, status: dict) -> str | None:
        """Extract device name during coordinator updates.

        Uses the same robust extraction logic as initial setup.

        Args:
            device_info: Device info section from coordinator data
            status: Status section from coordinator data

        Returns:
            Extracted device name or None if no change needed
        """
        # Combine both sources for extraction
        combined_data = {**status, **device_info}

        # Try to extract name from device_info first, then fall back to status
        new_name = (
            device_info.get("name") or device_info.get("DeviceName") or status.get("name") or status.get("DeviceName")
        )

        # If no direct name found, use robust extraction
        if not new_name:
            new_name = self._extract_device_name(combined_data)

        return new_name if new_name != self.name else None

    async def _populate_device_info(self) -> None:
        """Extract device info from coordinator data."""
        status = self.coordinator.data.get("status", {}) if self.coordinator.data else {}

        # Debug: Log available fields for device naming
        _LOGGER.debug(
            "Available status fields for device naming: %s",
            {k: v for k, v in status.items() if any(name in k.lower() for name in ["name", "device", "group", "ssid"])},
        )

        self.ip_address = self.coordinator.client.host
        self.mac_address = self._normalize_mac_address(status.get("MAC"))

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
        """Update speaker state from comprehensive coordinator data.

        SINGLE SOURCE OF TRUTH for all coordinator data updates.

        This method processes all data from the coordinator including:
        - Device information updates (with robust name extraction)
        - Group role and multiroom state changes (CRITICAL: actual Speaker object population)
        - Status and availability updates
        - Track and metadata changes (triggers entity updates for cover art)
        - Trigger entity state updates when needed

        ARCHITECTURAL NOTES:
        - Master speakers manage group state (populate self.group_members)
        - Slave speakers maintain reference to master (populate self.coordinator_speaker)
        - Group state resolution uses incremental discovery over polling cycles
        """
        if not data:
            _LOGGER.debug("No coordinator data to update for %s", self.uuid)
            return

        _LOGGER.debug("=== SPEAKER UPDATE FROM COORDINATOR START for %s ===", self.name)

        # Extract data sections
        status = data.get("status", {})
        device_info = data.get("device_info", {})
        multiroom = data.get("multiroom", {})
        metadata = data.get("metadata", {})
        eq_info = data.get("eq", {})
        polling_info = data.get("polling", {})
        role = data.get("role", "solo")  # Role calculated by coordinator from getStatusEx

        _LOGGER.debug("Speaker %s processing coordinator data sections: %s", self.name, list(data.keys()))
        _LOGGER.debug("Speaker %s role from coordinator: %s", self.name, role)
        _LOGGER.debug("Speaker %s multiroom data: %s", self.name, multiroom)

        # Track if any significant changes occurred
        changes_made = False

        # 1. Update device information with robust name extraction
        new_name = self._extract_device_name_from_update(device_info, status)
        if new_name:
            _LOGGER.info("Device name updated: %s -> %s", self.name, new_name)
            self.name = new_name
            changes_made = True
            # Schedule device registry update - handle case where no event loop exists (tests)
            try:
                import asyncio

                asyncio.create_task(self._update_device_registry_name())
            except RuntimeError:
                # No event loop running (likely in tests) - skip device registry update
                _LOGGER.debug("No event loop running, skipping device registry update for %s", self.name)

        # Update other device properties
        if device_info.get("model"):
            self.model = device_info["model"]
        elif status.get("project"):
            self.model = status["project"]

        if device_info.get("firmware"):
            self.firmware = device_info["firmware"]
        elif status.get("firmware"):
            self.firmware = status["firmware"]

        if device_info.get("mac"):
            normalized_mac = self._normalize_mac_address(device_info["mac"])
            if normalized_mac != self.mac_address:
                self.mac_address = normalized_mac
        elif status.get("MAC"):
            normalized_mac = self._normalize_mac_address(status["MAC"])
            if normalized_mac != self.mac_address:
                self.mac_address = normalized_mac

        # 2. CRITICAL: Update group role and populate group relationships
        old_role = self.role
        self.role = role

        if old_role != self.role:
            _LOGGER.info("Speaker %s role changed: %s -> %s", self.uuid, old_role, self.role)
            changes_made = True

        # 3. CRITICAL FIX: Actually populate group member relationships
        _LOGGER.debug("Speaker %s updating group state for role: %s", self.name, self.role)

        if self.role == "master":
            _LOGGER.debug("Speaker %s is MASTER - updating master group state", self.name)
            self._update_master_group_state(multiroom)
        elif self.role == "slave":
            _LOGGER.debug("Speaker %s is SLAVE - updating slave group state", self.name)
            # CRITICAL FIX: Get master info from device_info where getStatusEx puts it
            master_uuid = device_info.get("master_uuid")
            master_ip = device_info.get("master_ip")
            self._update_slave_group_state(master_uuid, master_ip)

            # CRITICAL FIX: Force source re-detection for slaves after master is established
            # This ensures "Following [Master Name]" is displayed instead of generic "Multiroom"
            if self.coordinator_speaker:
                _LOGGER.info("🎵 Slave %s master established, forcing source re-detection", self.name)
                changes_made = True  # Ensure entity update is triggered
        else:  # solo
            _LOGGER.debug("Speaker %s is SOLO - clearing group state", self.name)
            self._clear_group_state()

        # 4. Update availability based on coordinator success
        old_available = self._available
        self._available = self.coordinator.last_update_success

        if old_available != self._available:
            _LOGGER.debug("Speaker %s availability changed: %s -> %s", self.uuid, old_available, self._available)
            changes_made = True

        # 5. CRITICAL FIX: Check for track/metadata changes to trigger cover art updates
        track_changed = self._check_track_metadata_changes(metadata, status)
        if track_changed:
            _LOGGER.debug("Track metadata changed for %s, triggering entity update", self.name)
            changes_made = True

        # 6. Store polling diagnostics for sensor entities
        if polling_info:
            # This data is used by diagnostic sensors
            _LOGGER.debug(
                "Updated polling info: interval=%.1fs, playing=%s",
                polling_info.get("interval", 0),
                polling_info.get("is_playing", False),
            )

        # 7. Log metadata and EQ updates for debugging
        if metadata:
            current_title = metadata.get("title")
            if current_title:
                _LOGGER.debug("Current track: %s", current_title)

        if eq_info:
            eq_enabled = eq_info.get("eq_enabled")
            if eq_enabled is not None:
                _LOGGER.debug("EQ enabled: %s", eq_enabled)

        # 8. Notify entities of state changes if significant changes occurred
        if changes_made:
            _LOGGER.debug("Significant changes detected, notifying entities for %s", self.uuid)
            self.async_write_entity_states()
        else:
            # Reduce noise - only log at debug level when no changes
            _LOGGER.debug("No significant changes for %s, skipping entity notification", self.uuid)

        _LOGGER.debug("=== SPEAKER UPDATE FROM COORDINATOR END for %s ===", self.name)

    def _check_track_metadata_changes(self, metadata: dict, status: dict) -> bool:
        """Check if track metadata has changed to trigger entity updates.

        This ensures cover art and track info updates are reflected in the UI.
        """
        # Initialize _last_track_metadata if it doesn't exist
        if not hasattr(self, "_last_track_metadata"):
            self._last_track_metadata: dict[str, Any] = {}

        # Extract current track info from both metadata and status
        current_metadata = {}

        # Check metadata section first (coordinator's enhanced data)
        if metadata:
            current_metadata.update(
                {
                    "title": metadata.get("title"),
                    "artist": metadata.get("artist"),
                    "album": metadata.get("album"),
                    "entity_picture": metadata.get("entity_picture"),
                    "cover_url": metadata.get("cover_url"),
                }
            )

        # Then check status section (direct API data)
        if status:
            # Only update if we don't already have these from metadata
            if not current_metadata.get("title"):
                current_metadata["title"] = status.get("title")
            if not current_metadata.get("artist"):
                current_metadata["artist"] = status.get("artist")
            if not current_metadata.get("album"):
                current_metadata["album"] = status.get("album")
            if not current_metadata.get("entity_picture"):
                current_metadata["entity_picture"] = status.get("entity_picture")

        # Remove None values for comparison
        current_metadata = {k: v for k, v in current_metadata.items() if v is not None}

        # Check if anything changed
        metadata_changed = current_metadata != self._last_track_metadata

        if metadata_changed:
            # Log what changed for debugging - but only important changes at info level
            for key in set(current_metadata.keys()) | set(self._last_track_metadata.keys()):
                old_val = self._last_track_metadata.get(key)
                new_val = current_metadata.get(key)
                if old_val != new_val:
                    if key == "entity_picture":
                        _LOGGER.info("🎨 Cover art changed for %s: %s -> %s", self.name, old_val, new_val)
                    elif key in ["title", "artist"]:
                        # Important metadata changes at info level
                        _LOGGER.info("🎵 %s changed for %s: %s -> %s", key.title(), self.name, old_val, new_val)
                    else:
                        # Less important changes at debug level
                        _LOGGER.debug("🎵 %s changed for %s: %s -> %s", key.title(), self.name, old_val, new_val)

            # Update stored metadata
            self._last_track_metadata = current_metadata.copy()

        return metadata_changed

    def _update_master_group_state(self, multiroom: dict) -> None:
        """Update group state for master speakers.

        CRITICAL: Masters maintain authoritative group state by resolving
        slave IPs to Speaker objects using the global registry.
        """
        _LOGGER.debug("=== MASTER GROUP STATE UPDATE START for %s ===", self.name)

        # Initialize missing slaves tracking if not already present
        if not hasattr(self, "_missing_slaves_reported"):
            self._missing_slaves_reported: set[str] = set()

        slave_list = multiroom.get("slave_list", [])
        slave_count = multiroom.get("slave_count", 0)
        slaves_field = multiroom.get("slaves", [])

        _LOGGER.debug("Master %s multiroom input data:", self.name)
        _LOGGER.debug("  - slave_list: %s", slave_list)
        _LOGGER.debug("  - slave_count: %s", slave_count)
        _LOGGER.debug("  - slaves: %s", slaves_field)

        # Use slave_list if available, otherwise fall back to slaves field
        actual_slave_list = slave_list if slave_list else slaves_field
        _LOGGER.debug("Master %s using actual_slave_list: %s", self.name, actual_slave_list)

        _LOGGER.debug("Master %s processing %d slaves from multiroom data", self.name, len(actual_slave_list))

        # Clear coordinator reference (masters don't have one)
        old_coordinator = self.coordinator_speaker
        self.coordinator_speaker = None
        if old_coordinator:
            _LOGGER.debug("Master %s cleared coordinator reference (was: %s)", self.name, old_coordinator.name)

        # Resolve slave IPs/UUIDs to Speaker objects
        wiim_data = get_wiim_data(self.hass)
        new_group_members = []
        _LOGGER.debug("Master %s available speakers in registry: %s", self.name, list(wiim_data.speakers.keys()))

        for i, slave_info in enumerate(actual_slave_list):
            _LOGGER.debug("Master %s processing slave %d: %s", self.name, i, slave_info)

            # slave_info could be {"ip": "192.168.1.101", "uuid": "...", "name": "Kitchen"}
            # or just an IP string - handle both formats
            if isinstance(slave_info, dict):
                slave_ip = slave_info.get("ip")
                slave_uuid = slave_info.get("uuid")
                slave_name = slave_info.get("name", "Unknown")
            else:
                # Assume it's just an IP string
                slave_ip = str(slave_info)
                slave_uuid = None
                slave_name = "Unknown"

            _LOGGER.debug(
                "Master %s slave %d details: ip='%s', uuid='%s', name='%s'",
                self.name,
                i,
                slave_ip,
                slave_uuid,
                slave_name,
            )

            # Try to find slave by UUID first, then by IP
            slave_speaker = None
            if slave_uuid:
                slave_speaker = wiim_data.get_speaker_by_uuid(slave_uuid)
                _LOGGER.debug(
                    "Master %s UUID lookup for '%s': %s",
                    self.name,
                    slave_uuid,
                    slave_speaker.name if slave_speaker else "Not found",
                )

            if not slave_speaker and slave_ip:
                slave_speaker = wiim_data.get_speaker_by_ip(slave_ip)
                _LOGGER.debug(
                    "Master %s IP lookup for '%s': %s",
                    self.name,
                    slave_ip,
                    slave_speaker.name if slave_speaker else "Not found",
                )

            if slave_speaker:
                new_group_members.append(slave_speaker)

                # Clear from missing slaves tracking since we found it
                missing_slave_key = f"{slave_ip}:{slave_uuid}"
                if missing_slave_key in self._missing_slaves_reported:
                    self._missing_slaves_reported.discard(missing_slave_key)
                    _LOGGER.debug("Cleared missing slave tracking for %s - now found in registry", slave_name)

                # Update slave's coordinator reference to this master
                old_slave_coordinator = slave_speaker.coordinator_speaker
                slave_speaker.coordinator_speaker = self

                # Only log when there's an actual change
                if old_slave_coordinator != self:
                    _LOGGER.info(
                        "Master %s linked to slave %s (IP: %s) - slave coordinator: %s -> %s",
                        self.name,
                        slave_speaker.name,
                        slave_ip,
                        old_slave_coordinator.name if old_slave_coordinator else "None",
                        self.name,
                    )
                else:
                    _LOGGER.debug(
                        "Master %s already linked to slave %s (IP: %s) - no change needed",
                        self.name,
                        slave_speaker.name,
                        slave_ip,
                    )
            else:
                # Track missing slaves to avoid spam logging and repeated discovery attempts
                missing_slave_key = f"{slave_ip}:{slave_uuid}"

                if missing_slave_key not in self._missing_slaves_reported:
                    _LOGGER.warning(
                        "Master %s cannot find slave speaker for %s (IP: %s, UUID: %s) in registry - triggering auto-discovery",
                        self.name,
                        slave_name,
                        slave_ip,
                        slave_uuid,
                    )
                    _LOGGER.debug(
                        "Available speaker IPs in registry: %s", [s.ip_address for s in wiim_data.speakers.values()]
                    )

                    # Mark as reported to avoid spam
                    self._missing_slaves_reported.add(missing_slave_key)

                    # Trigger automatic discovery for missing slave devices
                    if slave_ip:
                        _LOGGER.info(
                            "Master %s triggering discovery for missing slave at %s (%s)",
                            self.name,
                            slave_ip,
                            slave_name,
                        )
                        self.hass.async_create_task(self._trigger_slave_discovery(slave_ip, slave_uuid, slave_name))
                else:
                    # Already reported and discovery triggered, just debug log
                    _LOGGER.debug(
                        "Master %s still missing slave %s (IP: %s) - discovery already triggered",
                        self.name,
                        slave_name,
                        slave_ip,
                    )

        # Update the group members list
        old_count = len(self.group_members)
        old_member_names = [s.name for s in self.group_members]
        self.group_members = new_group_members
        new_member_names = [s.name for s in new_group_members]

        if old_count != len(new_group_members) or old_member_names != new_member_names:
            _LOGGER.info(
                "Master %s group membership changed: %d -> %d slaves (%s -> %s)",
                self.name,
                old_count,
                len(new_group_members),
                old_member_names,
                new_member_names,
            )
        else:
            _LOGGER.debug(
                "Master %s group membership unchanged: %d slaves (%s)",
                self.name,
                len(new_group_members),
                new_member_names,
            )

        _LOGGER.debug("=== MASTER GROUP STATE UPDATE END for %s ===", self.name)

    def _update_slave_group_state(self, master_uuid: str | None, master_ip: str | None) -> None:
        """Update group state for slave speakers.

        CRITICAL: Slaves maintain reference to their master Speaker object.
        """
        _LOGGER.debug("=== SLAVE GROUP STATE UPDATE START for %s ===", self.name)
        _LOGGER.debug("Slave %s processing master reference (UUID: %s, IP: %s)", self.name, master_uuid, master_ip)

        # Clear group members list (slaves don't manage this)
        old_group_count = len(self.group_members)
        self.group_members = []
        if old_group_count > 0:
            _LOGGER.debug(
                "Slave %s cleared %d group members (slaves don't manage group lists)", self.name, old_group_count
            )

        # Find master Speaker object
        wiim_data = get_wiim_data(self.hass)
        master_speaker = None

        available_uuids = list(wiim_data.speakers.keys())
        available_ips = [s.ip_address for s in wiim_data.speakers.values()]
        _LOGGER.debug("Slave %s registry lookup diagnostics:", self.name)
        _LOGGER.debug("  - Available UUIDs in registry: %s", available_uuids)
        _LOGGER.debug("  - Available IPs in registry: %s", available_ips)
        _LOGGER.debug("  - Looking for master UUID: '%s'", master_uuid)
        _LOGGER.debug("  - Looking for master IP: '%s'", master_ip)

        # Try to find master by UUID first - with case-insensitive matching
        if master_uuid:
            # Use new O(1) UUID lookup
            master_speaker = wiim_data.get_speaker_by_uuid(master_uuid)
            _LOGGER.debug(
                "UUID lookup result for '%s': %s",
                master_uuid,
                master_speaker.name if master_speaker else "Not found",
            )

            # If direct match fails, try case-insensitive search
            if not master_speaker:
                master_uuid_lower = master_uuid.lower()
                for uuid_key, speaker in wiim_data.speakers.items():
                    if uuid_key.lower() == master_uuid_lower:
                        master_speaker = speaker
                        _LOGGER.debug("Case-insensitive UUID match found: '%s' matches '%s'", master_uuid, uuid_key)
                        break

                if not master_speaker:
                    _LOGGER.debug("No case-insensitive UUID match found for '%s'", master_uuid)

        # If UUID lookup failed, try IP lookup
        if not master_speaker and master_ip:
            master_speaker = wiim_data.get_speaker_by_ip(master_ip)
            _LOGGER.debug(
                "IP lookup result for '%s': %s", master_ip, master_speaker.name if master_speaker else "Not found"
            )

        if master_speaker:
            old_master = self.coordinator_speaker
            self.coordinator_speaker = master_speaker

            if old_master != master_speaker:
                _LOGGER.info(
                    "Slave %s master changed: %s -> %s",
                    self.name,
                    old_master.name if old_master else "None",
                    master_speaker.name,
                )
            else:
                _LOGGER.debug("Slave %s master unchanged: %s", self.name, master_speaker.name)
        else:
            if master_uuid or master_ip:
                _LOGGER.warning(
                    "LOOKUP FAILURE: Slave %s cannot find master speaker in registry:",
                    self.name,
                )
                _LOGGER.warning("  - Master UUID: '%s'", master_uuid)
                _LOGGER.warning("  - Master IP: '%s'", master_ip)
                _LOGGER.warning("  - Available UUIDs: %s", available_uuids)
                _LOGGER.warning("  - Available IPs: %s", available_ips)
                _LOGGER.warning("  - Registry speaker names: %s", [s.name for s in wiim_data.speakers.values()])
            else:
                _LOGGER.debug("Slave %s has no master UUID or IP specified", self.name)
            # Keep existing coordinator_speaker reference if lookup fails
            # This prevents breaking group state due to temporary lookup failures
            if self.coordinator_speaker:
                _LOGGER.debug(
                    "Slave %s keeping existing master reference: %s", self.name, self.coordinator_speaker.name
                )

        _LOGGER.debug("=== SLAVE GROUP STATE UPDATE END for %s ===", self.name)

    def _clear_group_state(self) -> None:
        """Clear all group state for solo speakers."""
        _LOGGER.debug("=== CLEAR GROUP STATE START for %s ===", self.name)

        old_role = "master" if self.group_members else ("slave" if self.coordinator_speaker else "solo")
        old_member_count = len(self.group_members)
        old_coordinator = self.coordinator_speaker

        if self.group_members or self.coordinator_speaker:
            _LOGGER.debug(
                "Clearing group state for solo speaker %s (was %s with %d members, coordinator: %s)",
                self.name,
                old_role,
                old_member_count,
                old_coordinator.name if old_coordinator else "None",
            )

        self.group_members = []
        self.coordinator_speaker = None

        _LOGGER.debug("=== CLEAR GROUP STATE END for %s ===", self.name)

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
        """Calculate current playback state from coordinator data."""
        if not self.coordinator.data:
            return MediaPlayerState.OFF

        status = self.coordinator.data.get("status", {})
        # Check both 'play_status' (parsed) and 'state' (raw) for compatibility
        state = (status.get("play_status") or status.get("state", "stop")).lower()

        # Handle primary stable states
        if state == "play":
            return MediaPlayerState.PLAYING
        elif state == "pause":
            return MediaPlayerState.PAUSED
        elif state == "stop":
            return MediaPlayerState.IDLE

        # Handle loading states - keep as PLAYING for better UX
        if state in ["load", "loading", "loaded"]:
            _LOGGER.debug("🎵 Loading state '%s' for %s -> PLAYING", state, self.name)
            return MediaPlayerState.PLAYING

        # Handle other transitional states (return to IDLE)
        transitional_states = {
            "connecting",
            "connect",
            "connected",  # Service connection
            "buffering",
            "buffer",
            "buffered",  # Content buffering
            "seeking",
            "seek",  # Position seeking
            "switching",
            "switch",  # Source switching
            "initializing",
            "init",  # Device initialization
            "preparing",
            "prepare",  # Content preparation
            "starting",
            "start",  # Playback starting
            "transitioning",
            "transition",  # Generic transition
            "none",  # No active state - treat as idle
        }

        if state in transitional_states:
            # Transitional state - return IDLE as safe default
            _LOGGER.debug("🎵 Transitional state '%s' for %s -> IDLE", state, self.name)
            return MediaPlayerState.IDLE

        # Handle unknown states (log warning but don't spam)
        # Rate limit unknown state warnings to reduce log spam
        if not hasattr(self, "_last_unknown_state_warning"):
            self._last_unknown_state_warning = {}

        import time

        current_time = time.time()
        warning_key = f"{state}_{self.name}"

        if (
            current_time - self._last_unknown_state_warning.get(warning_key, 0) > 300
        ):  # Only warn once per 5 minutes per state per device
            _LOGGER.warning(
                "🎵 UNKNOWN PLAY STATE for %s: '%s' (raw status: play_status='%s', state='%s', status='%s') - suppressing further warnings for 5min",
                self.name,
                state,
                status.get("play_status"),
                status.get("state"),
                status.get("status"),
            )
            self._last_unknown_state_warning[warning_key] = current_time
        else:
            _LOGGER.debug("🎵 Unknown play state '%s' for %s (warning suppressed)", state, self.name)
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
        """Get current track title with garbage text filtering."""
        if not self.coordinator.data:
            return None
        status = self.coordinator.data.get("status", {})
        title = status.get("title") or status.get("Title") or status.get("track_name")

        # Filter out garbage text that shouldn't be displayed
        if title and self._is_valid_media_text(title):
            return title
        return None

    def get_media_artist(self) -> str | None:
        """Get current artist name with garbage text filtering."""
        if not self.coordinator.data:
            return None
        status = self.coordinator.data.get("status", {})
        artist = status.get("artist") or status.get("Artist") or status.get("track_artist")

        # Filter out garbage text that shouldn't be displayed
        if artist and self._is_valid_media_text(artist):
            return artist
        return None

    def get_media_album(self) -> str | None:
        """Get current album name with garbage text filtering."""
        if not self.coordinator.data:
            return None
        status = self.coordinator.data.get("status", {})
        album = status.get("album") or status.get("Album") or status.get("track_album")

        # Filter out garbage text that shouldn't be displayed
        if album and self._is_valid_media_text(album):
            return album
        return None

    def _is_valid_media_text(self, text: str) -> bool:
        """Check if text is valid media information (not garbage/technical identifier).

        Returns False for garbage text that shouldn't be displayed in UI.
        """
        if not text or not text.strip():
            return False

        text_lower = text.lower().strip()

        # Filter out common garbage/placeholder text from WiiM devices
        garbage_patterns = [
            "unknow",  # Common WiiM garbage text
            "unknown",
            "n/a",
            "none",
            "null",
            "undefined",
            "default",
            "system",
            "device",
            "player",
        ]

        if text_lower in garbage_patterns:
            return False

        # Filter out "wiim" followed by IP address with spaces (e.g., "wiim 192 168 1 68")
        if text_lower.startswith("wiim "):
            remainder = text_lower[5:].strip()
            # Check if it looks like an IP with spaces (4 numbers separated by spaces)
            parts = remainder.split()
            if len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts):
                return False

        # Filter out UUID-like patterns (wiim + hex string)
        if text_lower.startswith("wiim ") and len(text_lower) > 20:
            uuid_part = text_lower[5:].strip()
            if len(uuid_part) >= 20 and all(c in "0123456789abcdef" for c in uuid_part.replace("-", "")):
                return False

        # Filter out long hex strings (32+ chars of just hex)
        if len(text_lower) >= 32 and all(c in "0123456789abcdef-" for c in text_lower):
            return False

        # Filter out very short strings that are likely technical
        if len(text.strip()) <= 2:
            return False

        return True

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

        Enhanced to prioritize coordinator's processed metadata where artwork URLs
        are now systematically extracted and standardized to 'entity_picture'.
        """
        if not self.coordinator.data:
            _LOGGER.debug("No coordinator data available for media image URL")
            return None

        # PRIORITY 1: Check entity_picture from the processed metadata by the coordinator
        # The enhanced coordinator now systematically finds artwork URLs and puts them here
        metadata_from_coord = self.coordinator.data.get("metadata", {})
        image_url = metadata_from_coord.get("entity_picture")

        if image_url:
            _LOGGER.debug("Found media image URL from coordinator metadata: %s for %s", image_url, self.name)
            return image_url

        # PRIORITY 2: Check status section entity_picture (coordinator might put it here too)
        status_from_coord = self.coordinator.data.get("status", {})
        image_url = status_from_coord.get("entity_picture")

        if image_url:
            _LOGGER.debug("Found media image URL from status entity_picture: %s for %s", image_url, self.name)
            return image_url

        # PRIORITY 3: Fallback to checking raw status fields
        # (though coordinator should have already processed these into metadata.entity_picture)
        fallback_fields = [
            "cover",
            "cover_url",
            "albumart",
            "albumArtURI",
            "albumArtUri",
            "albumarturi",
            "art_url",
            "artwork_url",
            "pic_url",
            "thumbnail",
        ]

        for artwork_field in fallback_fields:
            image_url = status_from_coord.get(artwork_field)
            if image_url:
                _LOGGER.debug(
                    "Found media image URL from fallback status field '%s': %s for %s",
                    artwork_field,
                    image_url,
                    self.name,
                )
                return image_url

        # Debug: Log what fields are actually available
        available_fields = {
            k: v
            for k, v in status_from_coord.items()
            if any(art_field in k.lower() for art_field in ["cover", "art", "pic", "thumb", "image"])
        }
        if available_fields:
            _LOGGER.debug("Available image-related fields in status for %s: %s", self.name, available_fields)

        _LOGGER.debug("No media image URL found for %s", self.name)
        return None

    # ===== SOURCE & AUDIO CONTROL METHODS =====

    def get_current_source(self) -> str | None:
        """Get current source with smart master/slave handling.

        Returns user-friendly source names:
        - Masters: Show actual source (WiFi, Bluetooth, etc.)
        - Slaves: Show "Following [Master Name]"
        """
        if not self.coordinator.data:
            _LOGGER.debug("🎵 No coordinator data for %s", self.name)
            return None

        status = self.coordinator.data.get("status", {})
        mode = status.get("mode")

        # Debug logging to understand what's happening
        _LOGGER.debug(
            "🎵 Source detection for %s: mode='%s', role='%s', status keys: %s",
            self.name,
            mode,
            self.role,
            list(status.keys())[:10],
        )

        if mode is None:
            _LOGGER.warning("🎵 No mode field found for %s in status: %s", self.name, status)
            return None

        # Special handling for slave devices in multiroom groups
        if self.role == "slave" and str(mode) == "99":
            # Slave devices should show they're following the master
            _LOGGER.debug(
                "🎵 Slave source detection: role=%s, coordinator_speaker=%s",
                self.role,
                self.coordinator_speaker.name if self.coordinator_speaker else "None",
            )
            if self.coordinator_speaker:
                following_text = f"Following {self.coordinator_speaker.name}"
                _LOGGER.info("🎵 Slave %s showing source: '%s'", self.name, following_text)
                return following_text
            else:
                _LOGGER.warning("🎵 Slave %s has no coordinator_speaker, showing generic source", self.name)
                return "Multiroom Slave"

        # For masters and solo devices, map mode to user-friendly source names
        mode_map = {
            "0": "Idle",
            "1": "AirPlay",
            "2": "DLNA",
            "10": "WiFi",  # Network streaming (Amazon Music, Spotify via WiFi, etc.)
            "11": "USB",
            "20": "Network",
            "31": "Spotify Connect",
            "40": "Line In",
            "41": "Bluetooth",
            "43": "Optical",
            "47": "Line In 2",
            "51": "USB DAC",
            "99": "Multiroom",  # Should not happen for masters, but fallback
        }

        source = mode_map.get(str(mode))
        if source:
            _LOGGER.info("🎵 Source from mode='%s' -> '%s' for %s (role: %s)", mode, source, self.name, self.role)
            return source
        else:
            _LOGGER.warning("🎵 Unknown mode '%s' for %s", mode, self.name)
            return f"Unknown ({mode})"

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
        """Find entity ID for a given speaker using O(1) lookup."""
        data = get_wiim_data(self.hass)
        return data.get_entity_id_for_speaker(speaker)

    def resolve_entity_ids_to_speakers(self, entity_ids: list[str]) -> list[Speaker]:
        """Convert entity IDs to Speaker objects with enhanced error reporting."""
        data = get_wiim_data(self.hass)
        speakers = []
        failed_entities = []

        for entity_id in entity_ids:
            speaker = data.get_speaker_by_entity_id(entity_id)
            if speaker:
                speakers.append(speaker)
            else:
                failed_entities.append(entity_id)

        # Log basic error info for debugging
        if failed_entities:
            available_count = len(data.entity_id_mappings)
            _LOGGER.warning(
                "Could not resolve entity_ids %s to speakers. Available entities: %d", failed_entities, available_count
            )

        return speakers

    # Group management methods
    async def async_join_group(self, speakers: list[Speaker]) -> None:
        """Join speakers to this speaker as group master using LinkPlay multiroom API.

        This speaker becomes the master, provided speakers become slaves.
        Uses the documented LinkPlay multiroom commands from the API guide.
        """
        if not speakers:
            _LOGGER.warning("No speakers provided for group join")
            return

        _LOGGER.info("Creating multiroom group: %s (master) + %d slaves", self.name, len(speakers))

        try:
            # Step 1: Make this device a multiroom master
            _LOGGER.debug("Setting %s as multiroom master", self.name)
            await self.coordinator.client.create_group()  # Sends setMultiroom:Master

            # Step 2: Add each slave to the group using the new join_slave method
            _LOGGER.debug("Adding %d slaves to group", len(speakers))

            successful_joins = 0
            for slave_speaker in speakers:
                if slave_speaker is self:
                    continue  # Skip self

                try:
                    _LOGGER.debug("Joining slave %s to master %s", slave_speaker.name, self.name)
                    # Use the new join_slave API method with setMultiroom:Slave:<master_ip>
                    await slave_speaker.coordinator.client.join_slave(self.ip_address)
                    successful_joins += 1
                    _LOGGER.info("Successfully joined slave %s to master %s", slave_speaker.name, self.name)
                except Exception as slave_err:
                    _LOGGER.error("Failed to join slave %s: %s", slave_speaker.name, slave_err)
                    # Continue with other slaves

            if successful_joins == 0:
                raise Exception("Failed to join any slaves to the group")

            _LOGGER.info("Successfully created group with %d/%d slaves", successful_joins, len(speakers))

            # Refresh all coordinators to update group state
            await self.coordinator.async_request_refresh()

            for slave_speaker in speakers:
                if slave_speaker is not self:
                    try:
                        await slave_speaker.coordinator.async_request_refresh()
                    except Exception as refresh_err:
                        _LOGGER.debug("Could not refresh slave coordinator %s: %s", slave_speaker.name, refresh_err)

        except Exception as err:
            _LOGGER.error("Failed to create multiroom group: %s", err)
            # Try to cleanup - remove master status if group creation failed
            try:
                await self.coordinator.client.leave_group()  # Send multiroom:Ungroup
            except Exception as cleanup_err:
                _LOGGER.debug("Failed to cleanup after group creation failure: %s", cleanup_err)
            raise

    async def async_leave_group(self) -> None:
        """Remove this speaker from its group using LinkPlay multiroom API.

        Handles both slave leaving group and master disbanding group.
        Uses documented LinkPlay SlaveKickout or Ungroup API commands.
        """
        _LOGGER.info("Speaker %s leaving group (current role: %s)", self.name, self.role)

        try:
            if self.role == "slave" and self.coordinator_speaker:
                # Slave leaving: send SlaveKickout command to master
                master = self.coordinator_speaker
                _LOGGER.debug("Sending slave kickout to master %s for slave %s", master.name, self.name)

                # Use the documented SlaveKickout command on the master
                await master.coordinator.client.kick_slave(self.ip_address)
                _LOGGER.info("Successfully sent slave kickout command for %s", self.name)

                # Refresh master coordinator to update group state
                await master.coordinator.async_request_refresh()

            elif self.role == "master":
                # Master leaving: disband entire group using Ungroup command
                _LOGGER.debug("Disbanding group for master %s", self.name)

                await self.coordinator.client.leave_group()  # Sends multiroom:Ungroup
                _LOGGER.info("Successfully disbanded group for master %s", self.name)

                # Refresh all former slave coordinators to update their state
                if hasattr(self, "group_members") and self.group_members:
                    for slave in self.group_members:
                        if slave is not self:
                            try:
                                await slave.coordinator.async_request_refresh()
                            except Exception as err:
                                _LOGGER.debug("Could not refresh former slave coordinator %s: %s", slave.name, err)

            else:
                _LOGGER.warning("Speaker %s not in a group (role: %s), nothing to leave", self.name, self.role)
                return

            # Request immediate refresh for this speaker to update role
            await self.coordinator.async_request_refresh()
            _LOGGER.info("Group leave completed for %s", self.name)

        except Exception as err:
            _LOGGER.error("Failed to leave group for %s: %s", self.name, err)
            raise

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

    async def _trigger_slave_discovery(self, ip: str, uuid: str | None, name: str) -> None:
        """Trigger automatic discovery for a missing slave device."""
        try:
            _LOGGER.info("🔍 Master %s initiating automatic discovery for slave %s at %s", self.name, name, ip)

            # Import here to avoid circular imports
            from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY

            # Check if we already have a config entry for this device
            existing_entries = [
                entry
                for entry in self.hass.config_entries.async_entries(DOMAIN)
                if entry.data.get(CONF_HOST) == ip or (uuid and entry.unique_id == uuid)
            ]

            if existing_entries:
                _LOGGER.debug("Slave device %s at %s already has config entry, skipping discovery", name, ip)
                return

            # Check for existing flows for this device
            existing_flows = [
                flow
                for flow in self.hass.config_entries.flow.async_progress_by_handler(DOMAIN)
                if flow.get("context", {}).get("unique_id") == uuid or flow.get("context", {}).get("unique_id") == ip
            ]

            if existing_flows:
                _LOGGER.debug("Discovery flow already in progress for slave %s at %s, skipping", name, ip)
                return

            # Trigger automatic integration discovery flow for the slave device
            _LOGGER.info("✅ Creating automatic discovery flow for slave %s at %s (UUID: %s)", name, ip, uuid)

            discovery_data = {
                CONF_HOST: ip,
                "device_name": name,
                "device_uuid": uuid,
                "discovery_source": "slave_detection",
            }

            # Create integration discovery flow - this will be handled by async_step_integration_discovery
            self.hass.async_create_task(
                self.hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={
                        "source": SOURCE_INTEGRATION_DISCOVERY,
                        "unique_id": uuid or ip,  # Use UUID if available, fallback to IP
                    },
                    data=discovery_data,
                )
            )

            _LOGGER.info("🎉 Automatic discovery flow initiated for slave %s at %s", name, ip)

        except Exception as err:
            _LOGGER.error("❌ Failed to trigger discovery for slave %s at %s: %s", name, ip, err)


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
    if uuid is None:
        raise ValueError(f"Config entry {config_entry.entry_id} has no unique_id")
    if uuid not in data.speakers:
        speaker = Speaker(hass, coordinator, config_entry)
        data.register_speaker(speaker)  # Use new registration method
        _LOGGER.debug("Created new speaker: %s", uuid)
    return data.speakers[uuid]
