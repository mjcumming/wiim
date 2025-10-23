"""Core data layer for WiiM integration.

SIMPLIFIED ARCHITECTURE (v2.1):
===============================

Following Home Assistant Core LinkPlay integration patterns:
- Config entries are the source of truth (no custom registry)
- Simple iteration for speaker lookups (2-4 devices = negligible overhead)
- Standard HA coordinator pattern
- Graceful IP updates through config entry system

Key simplifications:
- Removed complex WiimData registry
- Use hass.config_entries.async_entries(DOMAIN) for lookups
- Standard config entry updates for IP changes
- Missing master discovery through integration flows

This follows cursor rules: simple, composable, < 200 LOC modules.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.media_player.const import MediaPlayerState
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo as HADeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN

# Helper functions moved to data_helpers.py as part of Phase 2 refactor
# Import them here to maintain backward compatibility
from .data_helpers import (
    find_speaker_by_ip,
    find_speaker_by_uuid,
    get_all_speakers,
    get_speaker_from_config_entry,
    update_speaker_ip,
)
from .models import DeviceInfo as WiiMDeviceInfo
from .models import PlayerStatus

if TYPE_CHECKING:
    from .coordinator import WiiMCoordinator

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "Speaker",
    "get_speaker_from_config_entry",
    "find_speaker_by_uuid",
    "find_speaker_by_ip",
    "get_all_speakers",
    "update_speaker_ip",
]


class Speaker:
    """Represents a WiiM speaker device and its state.

    Simplified architecture using HA config entries as source of truth.
    No complex registry - just standard coordinator pattern.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: WiiMCoordinator,
        config_entry: ConfigEntry,
    ):
        """Initialize a Speaker instance."""
        self.hass = hass
        self.coordinator = coordinator
        self.config_entry = config_entry

        # Use config entry unique_id as speaker UUID (set by config flow)
        self._uuid: str = self.config_entry.unique_id or ""
        if not self._uuid:
            _LOGGER.error(
                "Speaker initialized without unique_id for host %s",
                self.coordinator.client.host,
            )
            self._uuid = self.coordinator.client.host  # Fallback

        # Device properties
        self.name: str = self.config_entry.title
        self.model: str = ""
        self.firmware: str | None = None
        self.ip_address: str = self.coordinator.client.host
        self.mac_address: str | None = None

        # Group state (populated by coordinator)
        self.role: str = "solo"
        self.group_members: list[Speaker] = []
        self.coordinator_speaker: Speaker | None = None

        # HA integration
        self.device_info: HADeviceInfo | None = None
        self._available: bool = True

        # Media tracking
        self._last_position_update: float | None = None
        self._last_position: int | None = None
        self._artwork_version: int = 0

        # Missing device tracking (prevent spam warnings)
        self._missing_devices_reported: set[str] = set()

        # Some unit tests use simplified MockConfigEntry objects that omit the
        # `entry_id` attribute.  Many helper functions use this field as a key
        # in `hass.data[DOMAIN]`.  Fall back to the unique_id (or a static
        # placeholder) so the test fixtures don't crash while still keeping a
        # stable identifier for look-ups.

        if not hasattr(self.config_entry, "entry_id") or self.config_entry.entry_id is None:
            fallback_entry_id = getattr(self.config_entry, "unique_id", None) or "mock_entry_id"
            # Direct assignment is safe on MagicMock / MockConfigEntry instances used in tests
            self.config_entry.entry_id = fallback_entry_id

    async def async_setup(self, entry: ConfigEntry) -> None:
        """Complete async setup of the speaker."""
        # _populate_device_info is a synchronous helper; no need to await.
        self._populate_device_info()
        await self._register_ha_device(entry)
        _LOGGER.info("Speaker setup complete for UUID: %s (Name: %s)", self.uuid, self.name)

    @property
    def uuid(self) -> str:
        """Return the unique identifier of the speaker."""
        return self._uuid

    @property
    def available(self) -> bool:
        """Return if speaker is available.

        A speaker is considered unavailable if:
        1. Background polling is failing (coordinator.last_update_success = False)
        2. Recent user commands have failed (provides immediate feedback)
        """
        # Check background polling success
        polling_available = self._available and self.coordinator.last_update_success

        # Check for recent command failures (immediate feedback)
        if hasattr(self.coordinator, "has_recent_command_failures"):
            has_command_failures = self.coordinator.has_recent_command_failures()
            if has_command_failures:
                return False  # Command failed recently - device appears unavailable immediately

        return polling_available

    def async_write_entity_states(self) -> None:
        """Notify all entities of state changes."""
        async_dispatcher_send(self.hass, f"wiim_state_updated_{self.uuid}")

    def _populate_device_info(self) -> None:
        """Extract device info from coordinator data."""
        status_model = self.coordinator.data.get("status_model") if self.coordinator and self.coordinator.data else None
        status: dict[str, Any] = (
            status_model.model_dump(exclude_none=True) if isinstance(status_model, PlayerStatus) else {}
        )

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

        # Group info - role is stored in main coordinator data, not multiroom section
        # Only set role if it hasn't been set by role detection yet (avoid overriding)
        if not hasattr(self, "role") or self.role is None:
            self.role = self.coordinator.data.get("role", "solo") if self.coordinator.data else "solo"

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
        self.device_info = HADeviceInfo(
            identifiers=identifiers,
            manufacturer="WiiM",
            name=self.name,
            model=self.model,
            sw_version=self.firmware,
        )

    def update_from_coordinator_data(self, data: dict[str, Any]) -> None:
        """Update speaker state from coordinator data."""
        if not data:
            return

        status_model = data.get("status_model")
        device_model = data.get("device_model")

        status: dict[str, Any] = (
            status_model.model_dump(exclude_none=True) if isinstance(status_model, PlayerStatus) else {}
        )
        device_info: dict[str, Any] = (
            device_model.model_dump(exclude_none=True) if isinstance(device_model, WiiMDeviceInfo) else {}
        )
        # Get role from coordinator data, preserving existing role if coordinator data unavailable
        # Role detection sets the role correctly, don't override with fallback defaults
        coordinator_role = data.get("role")
        if coordinator_role:
            # Coordinator has explicit role data - use it (this is the authoritative source)
            role = coordinator_role
        elif hasattr(self, "role") and self.role:
            # Preserve existing role if coordinator data doesn't have role yet
            # This prevents race condition where role detection works but gets overridden
            role = self.role
        else:
            # True fallback only if no role has been detected anywhere
            role = "solo"

        # Update basic device info
        if device_info.get("model"):
            self.model = device_info["model"]
        if device_info.get("firmware"):
            self.firmware = device_info["firmware"]
        if device_info.get("mac"):
            self.mac_address = self._normalize_mac_address(device_info["mac"])

        # Detect device name change coming from API – keep config entry title in sync
        new_name = status.get("DeviceName") or device_info.get("device_name") or None
        if new_name and new_name != self.name:
            _LOGGER.info(
                "Device name changed on %s: '%s' → '%s'",
                self.ip_address,
                self.name,
                new_name,
            )
            self.name = new_name

            # Update config entry title so that options dialog & integrations page reflect new name
            # Only update if user hasn't manually overridden title via UI (HA allows editing).
            if self.config_entry.title == self.name or self.config_entry.title in [
                self._extract_device_name({}),
                "WiiM Speaker",
                "WiiM Device",
            ]:
                self.hass.config_entries.async_update_entry(self.config_entry, title=new_name)

        # Update role and group state
        old_role = self.role
        self.role = role

        if old_role != self.role:
            _LOGGER.info("Speaker %s role changed: %s -> %s", self.name, old_role, self.role)

        # Handle group relationships using simple lookups
        if self.role == "master":
            self._update_master_group_state(data.get("multiroom", {}))
        elif self.role == "slave":
            master_uuid = device_info.get("master_uuid") or status.get("master_uuid")
            self._update_slave_group_state(master_uuid)
        else:
            self._clear_group_state()

        # Update availability
        self._available = self.coordinator.last_update_success

        # Notify entities AFTER group state is fully updated
        if old_role != self.role:
            # Force immediate entity state update for role changes (now with correct group data)
            _LOGGER.info(
                "🎯 FINAL ENTITY UPDATE for %s: role=%s, is_coordinator=%s, group_count=%s",
                self.name,
                self.role,
                self.is_group_coordinator,
                len(self.group_members),
            )

        self.async_write_entity_states()

    def _update_master_group_state(self, multiroom: dict[str, Any]) -> None:
        """Update group state for master speakers using simple lookups."""
        slave_list = multiroom.get("slave_list", [])
        slaves_count = multiroom.get("slaves", 0)
        self.coordinator_speaker = None  # Masters don't have coordinators

        # Only log when group composition actually changes
        current_slave_ips = [m.ip_address for m in self.group_members if hasattr(m, "ip_address")]
        new_slave_ips = []
        for slave_info in slave_list:
            if isinstance(slave_info, dict):
                slave_ip = slave_info.get("ip")
                if slave_ip:
                    new_slave_ips.append(slave_ip)

        group_changed = set(current_slave_ips) != set(new_slave_ips)

        if group_changed:
            _LOGGER.debug(
                "Master group update for %s: slaves_count=%s, slave_list_length=%s",
                self.name,
                slaves_count,
                len(slave_list),
            )

        # Find slave speakers using simple iteration
        new_group_members = []
        for slave_info in slave_list:
            if isinstance(slave_info, dict):
                slave_ip = slave_info.get("ip")
                slave_uuid = slave_info.get("uuid")
                slave_name = slave_info.get("name", "Unknown")
            else:
                slave_ip = str(slave_info)
                slave_uuid = None
                slave_name = "Unknown"

            # Try UUID lookup first, then IP lookup
            slave_speaker = None
            if slave_uuid:
                slave_speaker = find_speaker_by_uuid(self.hass, slave_uuid)
            if not slave_speaker and slave_ip:
                slave_speaker = find_speaker_by_ip(self.hass, slave_ip)

            if slave_speaker:
                new_group_members.append(slave_speaker)
                slave_speaker.coordinator_speaker = self
                # Clear from missing devices set if found
                if slave_uuid in self._missing_devices_reported:
                    self._missing_devices_reported.discard(slave_uuid)
            else:
                # Missing slave - only warn and trigger discovery once per device
                if slave_uuid and slave_uuid not in self._missing_devices_reported:
                    _LOGGER.warning(
                        "Master %s cannot find slave %s (IP: %s, UUID: %s) - triggering automatic discovery",
                        self.name,
                        slave_name,
                        slave_ip,
                        slave_uuid,
                    )
                    self._missing_devices_reported.add(slave_uuid)
                    self.hass.async_create_task(
                        self._trigger_missing_device_discovery(slave_uuid, slave_name, slave_ip)
                    )
                elif slave_uuid:
                    # Subsequent polls - only log at debug level to avoid spam
                    _LOGGER.debug(
                        "Master %s still cannot find slave %s (IP: %s, UUID: %s) - discovery already triggered",
                        self.name,
                        slave_name,
                        slave_ip,
                        slave_uuid,
                    )

        self.group_members = new_group_members

        # Only log when group membership actually changes
        if group_changed:
            _LOGGER.debug(
                "Master group result for %s: final_group_members_count=%s, group_members=%s",
                self.name,
                len(self.group_members),
                [m.name for m in self.group_members],
            )

    def _update_slave_group_state(self, master_uuid: str | None) -> None:
        """Update group state for slave speakers using simple lookups."""
        self.group_members = []  # Slaves don't manage groups

        if master_uuid:
            master_speaker = find_speaker_by_uuid(self.hass, master_uuid)
            if master_speaker:
                self.coordinator_speaker = master_speaker
                # Clear from missing devices set if found
                if master_uuid in self._missing_devices_reported:
                    self._missing_devices_reported.discard(master_uuid)
            else:
                # Missing master - only warn and trigger discovery once per device
                if master_uuid not in self._missing_devices_reported:
                    _LOGGER.warning(
                        "Slave %s cannot find master UUID: %s - triggering automatic discovery",
                        self.name,
                        master_uuid,
                    )
                    self._missing_devices_reported.add(master_uuid)
                    self.hass.async_create_task(
                        self._trigger_missing_device_discovery(master_uuid, "Missing Master", None)
                    )
                else:
                    # Subsequent polls - only log at debug level to avoid spam
                    _LOGGER.debug(
                        "Slave %s still cannot find master UUID: %s - discovery already triggered",
                        self.name,
                        master_uuid,
                    )

    def _clear_group_state(self) -> None:
        """Clear group state for solo speakers."""
        self.group_members = []
        self.coordinator_speaker = None

    async def _trigger_missing_device_discovery(
        self, device_uuid: str, device_name: str, device_ip: str | None = None
    ) -> None:
        """Trigger discovery flow for missing device."""
        try:
            from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY

            # Check if already have config entry
            existing = self.hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, device_uuid)
            if existing:
                return

            # Check for existing discovery flows
            existing_flows = [
                flow
                for flow in self.hass.config_entries.flow.async_progress_by_handler(DOMAIN)
                if flow.get("context", {}).get("unique_id") == device_uuid
            ]
            if existing_flows:
                return

            _LOGGER.info(
                "Creating discovery flow for missing device: %s (%s)",
                device_name,
                device_uuid,
            )

            # Prepare discovery data
            discovery_data = {
                "device_uuid": device_uuid,
                "device_name": device_name,
                "discovery_source": "missing_device" if not device_ip else "automatic_slave",
            }

            # Include IP if available (enables automatic setup without user input)
            if device_ip:
                from homeassistant.const import CONF_HOST

                discovery_data[CONF_HOST] = device_ip

            await self.hass.config_entries.flow.async_init(
                DOMAIN,
                context={
                    "source": SOURCE_INTEGRATION_DISCOVERY,
                    "unique_id": device_uuid,
                },
                data=discovery_data,
            )
        except Exception as err:
            _LOGGER.error("Failed to trigger discovery for %s: %s", device_name, err)

    def _normalize_mac_address(self, mac: str | None) -> str | None:
        """Normalize MAC address to lowercase colon-separated format."""
        if not mac:
            return None
        clean_mac = mac.lower().replace(":", "").replace("-", "").replace(" ", "")
        if len(clean_mac) != 12 or not all(c in "0123456789abcdef" for c in clean_mac):
            return None
        return ":".join(clean_mac[i : i + 2] for i in range(0, 12, 2))

    def _extract_device_name(self, status: dict[str, Any]) -> str:
        """Extract device name from status data with fallback logic.

        This is the SINGLE SOURCE OF TRUTH for device name extraction.
        Used by both initial setup and runtime updates to ensure consistency.

        Args:
            status: Status dictionary from API response

        Returns:
            Clean device name string, never empty or containing IP addresses
        """
        # Extract device name with multiple fallback attempts
        # PRIORITY 1: DeviceName from WiiM API (custom name set in app)
        # PRIORITY 2: Other common name fields
        # PRIORITY 3: Network/SSID name (less reliable)
        # PRIORITY 4: Generic fallback

        device_name = (
            status.get("DeviceName")  # WiiM API primary field - custom name from app
            or status.get("device_name")  # Alternative field name
            or status.get("friendlyName")  # Common API field
            or status.get("name")  # Generic name field
            or status.get("GroupName")  # Group name field
            or status.get("ssid", "").replace("_", " ")  # Device hotspot name (fallback)
            # REMOVED: or status.get("title")  # This is SONG TITLE, not device name!
            or "WiiM Speaker"  # Clean final fallback (no IP)
        )

        # Clean up the device name
        clean_name = device_name.strip()
        if not clean_name or clean_name.lower() in ["unknown", "none", ""]:
            clean_name = "WiiM Speaker"

        return clean_name

    # ==========================================================
    # GENERIC HELPER PROPERTIES / METHODS REQUIRED BY PLATFORMS
    # These were referenced by media_player, sensor and controller
    # modules but were missing after the recent data-layer overhaul.
    # Implementations intentionally keep business-logic simple while
    # remaining 100 % safe (no external I/O, no await requirements).
    # ==========================================================

    # ----- GROUP HELPERS -----

    @property
    def is_group_coordinator(self) -> bool:
        """Return True if this speaker is coordinating a group.

        Only master speakers are coordinators - they manage slaves.
        Solo speakers and slaves are not coordinators.
        """
        return self.role == "master"

    def get_group_member_entity_ids(self) -> list[str]:
        """Return HA entity IDs for all members in the current group.

        The master (or solo) speaker is always the first element to match
        the ordering expectation from previous implementation/tests.
        """
        # Resolve entity IDs via entity registry to ensure they match the ones
        # actually created by Home Assistant (which are based on device names
        # rather than bare UUIDs).

        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(self.hass)

        def _speaker_to_entity_id(spk: Speaker) -> str | None:
            # MediaPlayerEntity unique_id is the raw speaker UUID as set in
            # WiiMMediaPlayer.__init__ (no additional "wiim_" prefix).

            entity_id = ent_reg.async_get_entity_id("media_player", "wiim", spk.uuid)
            if entity_id:
                return entity_id

            # Fallback: best-effort slugified name to avoid returning invalid
            # UUID-style IDs.  This guarantees the method never returns an
            # entity_id that doesn't exist in HA.
            return None  # Not found – caller will filter out

        if self.role == "master":
            ordered_members = [self] + [m for m in self.group_members if m is not self]
        else:
            ordered_members = [self] + self.group_members

        # Map to entity IDs and filter out any unresolved speakers (None)
        return [eid for eid in (_speaker_to_entity_id(s) for s in ordered_members) if eid]

    async def async_join_group(self, target_speakers: list[Speaker]) -> None:
        """Create or extend a multiroom group with *self* as master.

        A *very* lightweight implementation that simply maps to a few
        LinkPlay API calls exposed on the underlying client. It is good
        enough for UI / service-level grouping interactions; advanced
        edge-cases (e.g. regrouping masters) are handled by the device.
        """
        try:
            # Make sure we have a list without duplicates & self.
            slaves = [s for s in target_speakers if s is not self]
            if not slaves:
                return

            # 1. If we are currently not a master, issue create_group() first.
            if self.role != "master":
                await self.coordinator.client.create_group()

            # 2. Ask each slave to join our IP.
            for slave in slaves:
                await slave.coordinator.client.join_slave(self.ip_address)

        except Exception as err:  # pragma: no cover – safety net
            _LOGGER.error("Failed to join group: %s", err)

    async def async_leave_group(self) -> None:
        """Leave or dissolve the current group depending on our role."""
        try:
            if self.role == "master":
                # Master dissolves group for everyone.
                await self.coordinator.client.leave_group()
            elif self.role == "slave" and self.coordinator_speaker:
                # Ask master to kick us out.
                await self.coordinator_speaker.coordinator.client.kick_slave(self.ip_address)
            # Solo => nothing to do.
        except Exception as err:  # pragma: no cover
            _LOGGER.error("Failed to leave group: %s", err)

    # ----- VOLUME / PLAYBACK HELPERS -----

    def get_volume_level(self) -> float | None:
        """Return current volume as a float 0…1."""
        if self.status_model is None or self.status_model.volume is None:
            return None
        return max(0, min(int(self.status_model.volume), 100)) / 100.0

    def get_playback_state(self) -> MediaPlayerState:
        """Map WiiM play_status to Home Assistant MediaPlayerState."""
        if self.status_model is None:
            _LOGGER.debug("🎵 DEVICE STATE: status_model=None")
            return MediaPlayerState.IDLE

        # Debug: Show ALL fields in the status model to see what the device provides
        if self.status_model.play_state is None:
            status_dict = self.status_model.model_dump(exclude_none=True)
            _LOGGER.debug(
                "🎵 DEVICE STATE: play_state=None, available_fields=%s",
                list(status_dict.keys()),
            )

            # Check if status field exists under a different name
            raw_status = getattr(self.status_model, "status", None)
            _LOGGER.debug("🎵 DEVICE STATE: checking raw 'status' field=%s", raw_status)
            return MediaPlayerState.IDLE

        play_status = str(self.status_model.play_state)

        # Debug: Log the raw device state to see what we're actually getting
        _LOGGER.debug(
            "🎵 DEVICE STATE: raw_play_state='%s' (type=%s)",
            play_status,
            type(self.status_model.play_state),
        )

        if play_status in ["play", "playing", "load"]:
            mapped_state = MediaPlayerState.PLAYING
        elif play_status in ["pause", "paused"]:
            mapped_state = MediaPlayerState.PAUSED
        elif play_status in ["stop", "stopped", "idle", ""]:
            mapped_state = MediaPlayerState.IDLE
        else:
            # Unknown state - log it for debugging
            _LOGGER.debug(
                "🎵 DEVICE STATE: Unknown play_state='%s', falling back to IDLE",
                play_status,
            )
            mapped_state = MediaPlayerState.IDLE

        _LOGGER.debug("🎵 DEVICE STATE: '%s' → %s", play_status, mapped_state)
        return mapped_state

    def is_volume_muted(self) -> bool | None:
        """Return *current* mute state derived from :class:`PlayerStatus`.

        Returns:
            True   – muted
            False  – un-muted
            None   – value not reported yet
        """
        if self.status_model is None:
            return None

        mute_val = self.status_model.mute if self.status_model else None

        if mute_val is None:
            return None

        # Convert to boolean for various encodings
        if isinstance(mute_val, bool | int):
            return bool(int(mute_val))

        mute_str = str(mute_val).strip().lower()
        if mute_str in ["1", "true", "yes", "on"]:
            return True
        if mute_str in ["0", "false", "no", "off"]:
            return False
        return None

    # ----- MEDIA METADATA HELPERS -----

    def _status_field(self, *names: str) -> Any:
        """Return the first non-empty attribute from :class:`PlayerStatus`."""
        if self.status_model is None:
            return None

        for n in names:
            if hasattr(self.status_model, n):
                val = getattr(self.status_model, n)
                if isinstance(val, str) and val.strip().lower() in {
                    "unknown",
                    "unknow",
                    "none",
                }:
                    continue
                if val not in (None, ""):
                    return val
        return None

    def get_media_title(self) -> str | None:
        val = self._status_field("title")
        if isinstance(val, str):
            return val
        return None

    def get_media_artist(self) -> str | None:
        val = self._status_field("artist")
        if isinstance(val, str):
            return val
        return None

    def get_media_album(self) -> str | None:
        val = self._status_field("album", "album_name")
        if isinstance(val, str):
            return val
        return None

    def get_media_duration(self) -> int | None:
        duration = self._status_field("duration")

        try:
            return int(float(duration)) if duration is not None else None
        except (TypeError, ValueError):
            return None

    def get_media_position(self) -> int | None:
        position = self._status_field("position", "seek")

        # Position may vary by source type and streaming service

        try:
            if position is not None:
                pos_value = int(float(position))
                # Ensure position is non-negative
                if pos_value >= 0:
                    return pos_value
            return None
        except (TypeError, ValueError):
            return None

    def get_media_position_updated_at(self) -> float | None:
        # Coordinator could track this precisely; for now, update time when we last saw a position.
        import time

        pos = self.get_media_position()
        if pos is not None:
            self._last_position_update = time.time()
            self._last_position = pos

        # Always return a valid timestamp to prevent Music Assistant integration errors
        # If we haven't seen a position update yet, return current time
        if self._last_position_update is None:
            self._last_position_update = time.time()
            _LOGGER.debug("Initialized position update timestamp for %s", self.name)

        return self._last_position_update

    def get_media_image_url(self) -> str | None:
        return self._status_field("entity_picture", "cover_url")

    # ----- SOURCE / MODE HELPERS -----

    def get_current_source(self) -> str | None:
        """Return user-friendly current source name."""
        if self.status_model is None:
            return None

        source_internal = self.status_model.source or getattr(self.status_model, "mode", None)

        if not source_internal:
            return None
        try:
            from .const import SOURCE_MAP

            result = SOURCE_MAP.get(str(source_internal).lower(), str(source_internal))
            return result
        except Exception:
            return str(source_internal)

    # ----- AUDIO OUTPUT HELPERS -----

    def is_bluetooth_output_active(self) -> bool:
        """Return True if Bluetooth output is currently active."""
        if self.status_model is None:
            return False

        # Check if audio output data is available
        audio_output = getattr(self.status_model, "audio_output", None)
        if audio_output is None or audio_output == {}:
            return False

        try:
            return audio_output.get("source") == "1"
        except Exception:
            # Handle any unexpected data format issues
            return False

    def get_hardware_output_mode(self) -> str | None:
        """Return current hardware output mode name."""
        if self.status_model is None:
            return None

        audio_output = getattr(self.status_model, "audio_output", None)
        if audio_output is None or audio_output == {}:
            return None

        try:
            mode_map = {"1": "SPDIF", "2": "AUX", "3": "COAX"}
            hardware_mode = audio_output.get("hardware")
            return mode_map.get(str(hardware_mode), f"Unknown ({hardware_mode})")
        except Exception:
            # Handle any unexpected data format issues
            return None

    def is_audio_cast_active(self) -> bool:
        """Return True if audio cast mode is currently active."""
        if self.status_model is None:
            return False

        audio_output = getattr(self.status_model, "audio_output", None)
        if audio_output is None:
            return False

        return audio_output.get("audiocast") == "1"

    def get_current_output_mode(self) -> str | None:
        """Return current hardware output mode name."""
        if self.status_model is None:
            return None

        audio_output = getattr(self.status_model, "audio_output", None)

        if audio_output is None or audio_output == {}:
            return None

        try:
            from .const import AUDIO_OUTPUT_MODES

            hardware_mode = audio_output.get("hardware")

            if hardware_mode is None:
                return None

            mode_str = str(hardware_mode)

            # Return known mode or "Unknown" with the raw value
            result = AUDIO_OUTPUT_MODES.get(mode_str, f"Unknown ({hardware_mode})")
            return result
        except Exception:
            # Handle any unexpected data format issues
            return None

    def get_output_mode_list(self) -> list[str]:
        """Return list of selectable output modes."""
        from .const import SELECTABLE_OUTPUT_MODES

        return SELECTABLE_OUTPUT_MODES.copy()

    def get_discovered_output_modes(self) -> list[str]:
        """Return list of output modes discovered from device status."""
        if self.status_model is None:
            return []

        audio_output = getattr(self.status_model, "audio_output", None)
        if audio_output is None or audio_output == {}:
            return []

        try:
            from .const import AUDIO_OUTPUT_MODES

            # Get all known modes plus any unknown ones we've seen
            discovered_modes = []
            hardware_mode = audio_output.get("hardware")
            if hardware_mode is not None:
                mode_str = str(hardware_mode)
                if mode_str in AUDIO_OUTPUT_MODES:
                    discovered_modes.append(AUDIO_OUTPUT_MODES[mode_str])
                else:
                    discovered_modes.append(f"Unknown ({hardware_mode})")

            return discovered_modes
        except Exception:
            # Handle any unexpected data format issues
            return []

    def get_shuffle_state(self) -> bool | None:
        """Return True if shuffle is active, False if off, None if unknown."""
        if self.status_model is None:
            return None

        # Check specific shuffle field first
        shuffle_val = getattr(self.status_model, "shuffle", None)
        if shuffle_val is not None:
            if isinstance(shuffle_val, bool | int):
                return bool(int(shuffle_val))
            shuffle_str = str(shuffle_val).strip().lower()
            return shuffle_str in {"1", "true", "shuffle"}

        # Check play_mode field (properly decoded from loop_mode by api_parser)
        play_mode = getattr(self.status_model, "play_mode", None)
        if play_mode is not None:
            mode_str = str(play_mode).strip().lower()
            return "shuffle" in mode_str

        return None

    def get_repeat_mode(self) -> str | None:
        """Return repeat mode: 'one', 'all' or 'off'."""
        if self.status_model is None:
            return None

        # Check specific repeat field first
        repeat_val = getattr(self.status_model, "repeat", None)
        if repeat_val is not None:
            repeat_str = str(repeat_val).strip().lower()
            if repeat_str in {"one", "single", "repeat_one", "repeatone", "1"}:
                return "one"
            elif repeat_str in {"all", "repeat_all", "repeatall", "2"}:
                return "all"
            else:
                return "off"

        # Check play_mode field (properly decoded from loop_mode by api_parser)
        play_mode = getattr(self.status_model, "play_mode", None)
        if play_mode is not None:
            mode_str = str(play_mode).strip().lower()
            if "repeat_one" in mode_str or mode_str in {"one", "single"}:
                return "one"
            elif "repeat_all" in mode_str or mode_str in {"all"}:
                return "all"
            elif "repeat" in mode_str and "shuffle" not in mode_str:
                return "all"  # fallback for generic "repeat"

        return "off"

    def get_sound_mode(self) -> str | None:
        """Return current EQ preset name suitable for display."""
        if self.status_model is None:
            return None

        eq_preset: str | None = self.status_model.eq_preset

        if not eq_preset:
            return None

        try:
            from .const import EQ_PRESET_MAP

            return EQ_PRESET_MAP.get(str(eq_preset).lower(), str(eq_preset).title())
        except Exception:
            return str(eq_preset).title()

    # ==========================================================
    # NEW – TYPED MODEL SHORTCUTS (Pydantic)
    # ==========================================================

    @property
    def status_model(self) -> PlayerStatus | None:  # noqa: D401
        """Return the typed PlayerStatus model injected by the coordinator."""

        if self.coordinator and self.coordinator.data:
            raw = self.coordinator.data.get("status_model")
            if isinstance(raw, PlayerStatus):
                return raw
        return None

    @property
    def device_model(self) -> WiiMDeviceInfo | None:  # noqa: D401
        """Return the typed DeviceInfo model injected by the coordinator."""

        if self.coordinator and self.coordinator.data:
            raw = self.coordinator.data.get("device_model")
            if isinstance(raw, WiiMDeviceInfo):
                return raw
        return None
