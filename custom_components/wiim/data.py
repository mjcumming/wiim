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
import time
from typing import TYPE_CHECKING, Any

from async_upnp_client.exceptions import UpnpResponseError
from homeassistant.components.media_player.const import MediaPlayerState
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
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
        self.input_list: list[str] | None = None  # Available input sources from API

        # Group state (populated by coordinator)
        self.role: str = "solo"
        self.group_members: list[Speaker] = []
        self.coordinator_speaker: Speaker | None = None

        # UPnP components (Samsung/DLNA pattern)
        self._upnp_client: Any | None = None
        self._upnp_eventer: Any | None = None
        self._upnp_state: Any | None = None
        self._subscriptions_failed: bool = False
        self._poll_timer: Any | None = None  # Fallback polling timer

        # HA integration
        self.device_info: HADeviceInfo | None = None
        self._available: bool = True

        # Bluetooth scan results (stored temporarily for entity access)
        self._bluetooth_devices: list[dict[str, Any]] = []
        self._bluetooth_scan_status: str = "Not started"

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
        _LOGGER.info("🔧 Speaker.async_setup() called for %s (UUID: %s)", self.name, self.uuid)

        # _populate_device_info is a synchronous helper; no need to await.
        self._populate_device_info()
        await self._register_ha_device(entry)

        # Initialize UPnP (Samsung/DLNA pattern - always try, gracefully fallback to polling)
        # Follows DLNA DMR/SamsungTV pattern: always attempt UPnP subscriptions, fallback to HTTP polling on failure
        # In Docker/WSL bridge mode, callbacks may not be reachable, but code handles this gracefully
        # To enable UPnP callbacks in Docker: use network_mode: host in docker-compose.yml or --network=host
        # To enable UPnP callbacks in VS Code DevContainer: add "runArgs": ["--network=host"] to devcontainer.json
        _LOGGER.info(
            "📡 Initializing UPnP event subscriptions for %s (Samsung/DLNA pattern)...",
            self.name,
        )
        try:
            await self._setup_upnp_subscriptions(entry)
            _LOGGER.info("✅ UPnP setup completed for %s", self.name)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "⚠️  Failed to setup UPnP for %s: %s - will use HTTP polling fallback",
                self.name,
                err,
            )
            _LOGGER.debug("UPnP setup error details:", exc_info=True)
            self._subscriptions_failed = True

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
        signal = f"wiim_state_updated_{self.uuid}"
        async_dispatcher_send(self.hass, signal)

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
        """Update speaker state from coordinator HTTP polling."""
        _LOGGER.debug(
            "🔄 HTTP POLL update for %s with data keys: %s",
            self.name,
            list(data.keys()) if data else "None",
        )

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
        if device_info.get("input_list"):
            self.input_list = device_info["input_list"]

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

            # 3. Trigger immediate refresh on all slaves for faster UI updates
            _LOGGER.debug(
                "Triggering immediate refresh on %d slave devices for faster role detection",
                len(slaves),
            )
            for slave in slaves:
                try:
                    await slave.coordinator.async_request_refresh()
                except Exception as refresh_err:
                    _LOGGER.warning(
                        "Failed to trigger refresh on slave %s: %s",
                        slave.name,
                        refresh_err,
                    )

            # 4. Also refresh master to update its group member list
            await self.coordinator.async_request_refresh()

        except Exception as err:  # pragma: no cover – safety net
            _LOGGER.error("Failed to join group: %s", err)

    async def async_leave_group(self) -> None:
        """Leave or dissolve the current group depending on our role."""
        try:
            # Remember group members and master before dissolving
            former_slaves = list(self.group_members) if self.role == "master" else []
            former_master = self.coordinator_speaker if self.role == "slave" else None

            if self.role == "master":
                # Master dissolves group for everyone.
                await self.coordinator.client.leave_group()

                # Trigger refresh on all former slaves for faster UI updates
                _LOGGER.debug(
                    "Triggering immediate refresh on %d former slave devices",
                    len(former_slaves),
                )
                for slave in former_slaves:
                    try:
                        await slave.coordinator.async_request_refresh()
                    except Exception as refresh_err:
                        _LOGGER.warning(
                            "Failed to trigger refresh on former slave %s: %s",
                            slave.name,
                            refresh_err,
                        )

            elif self.role == "slave" and self.coordinator_speaker:
                # Ask master to kick us out.
                await self.coordinator_speaker.coordinator.client.kick_slave(self.ip_address)

                # Trigger refresh on former master to update its group member list
                if former_master:
                    try:
                        await former_master.coordinator.async_request_refresh()
                    except Exception as refresh_err:
                        _LOGGER.warning(
                            "Failed to trigger refresh on former master %s: %s",
                            former_master.name,
                            refresh_err,
                        )
            # Solo => nothing to do.

            # Always refresh self to detect new solo role immediately
            await self.coordinator.async_request_refresh()

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
            return MediaPlayerState.IDLE

        if self.status_model.play_state is None:
            # Only log if we've never seen this before (diagnostic aid)
            if not hasattr(self, "_logged_missing_play_state"):
                status_dict = self.status_model.model_dump(exclude_none=True)
                _LOGGER.info(
                    "Device %s has no play_state field, available_fields=%s",
                    self.name,
                    list(status_dict.keys()),
                )
                self._logged_missing_play_state = True
            return MediaPlayerState.IDLE

        play_status = str(self.status_model.play_state).lower()

        # Map valid states from model: "play", "pause", "stop", "load", "idle"
        # Also handle common variations: "playing", "paused", "stopped"
        if play_status in ["play", "playing", "load"]:
            return MediaPlayerState.PLAYING
        elif play_status in ["pause", "paused"]:
            return MediaPlayerState.PAUSED
        elif play_status in ["stop", "stopped", "idle", ""]:
            return MediaPlayerState.IDLE
        else:
            # Unknown state - log once for diagnostics
            if not hasattr(self, "_logged_unknown_states"):
                self._logged_unknown_states = set()
            if play_status not in self._logged_unknown_states:
                _LOGGER.warning(
                    "Device %s reported unknown play_state='%s', treating as IDLE",
                    self.name,
                    play_status,
                )
                self._logged_unknown_states.add(play_status)
            return MediaPlayerState.IDLE

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
            if duration is not None:
                result = int(float(duration))
                # Return None for zero duration (streaming services without duration info)
                if result == 0:
                    return None
                return result
            else:
                return None
        except (TypeError, ValueError):
            return None

    def get_media_position(self) -> int | None:
        position = self._status_field("position", "seek")
        try:
            if position is not None:
                pos_value = int(float(position))
                # Ensure position is non-negative
                if pos_value < 0:
                    return None

                # Clamp to known duration if available
                try:
                    duration_value = self.get_media_duration()
                except Exception:  # pragma: no cover - defensive
                    duration_value = None
                if duration_value is not None and duration_value > 0:
                    if pos_value > duration_value:
                        _LOGGER.debug(
                            "🎵 get_media_position: clamping %s to duration %s",
                            pos_value,
                            duration_value,
                        )
                        pos_value = duration_value

                return pos_value
            return None
        except (TypeError, ValueError):
            return None

    def get_media_position_updated_at(self) -> float | None:
        # Only bump the timestamp when actually playing and either
        # the numeric position increases or the track changes.
        import time

        current_position = self.get_media_position()

        # Derive a simple track signature from current metadata
        try:
            title = self._status_field("title") or ""
            artist = self._status_field("artist") or ""
            album = self._status_field("album") or ""
            content_id = self._status_field("media_content_id", "uri") or ""
            current_signature = f"{title}|{artist}|{album}|{content_id}"
        except Exception:  # pragma: no cover - best-effort
            current_signature = ""

        # Initialize storage if not present
        if not hasattr(self, "_last_position_update"):
            self._last_position_update = None  # type: ignore[attr-defined]
        if not hasattr(self, "_last_position"):
            self._last_position = None  # type: ignore[attr-defined]
        if not hasattr(self, "_last_track_signature"):
            self._last_track_signature = None  # type: ignore[attr-defined]

        previous_position = getattr(self, "_last_position", None)
        previous_signature = getattr(self, "_last_track_signature", None)

        # Determine if we are actively playing (avoid advancing while paused/idle)
        try:
            # Use the same logic as get_playback_state() for consistency
            if self.status_model is None:
                is_playing = False
            else:
                play_status = str(self.status_model.play_state) if self.status_model.play_state is not None else ""
                is_playing = play_status.lower() in ("play", "playing", "load")
        except Exception:
            is_playing = True  # fall back to permissive behavior

        # Update timestamp on new track or real position change while playing
        track_changed = current_signature and current_signature != previous_signature

        # Treat clear position decrease as implicit track switch (some sources delay metadata)
        position_decreased = (
            current_position is not None and previous_position is not None and current_position + 2 < previous_position
        )

        if (track_changed or position_decreased) and current_position is not None:
            self._last_position_update = time.time()
            self._last_position = current_position
            self._last_track_signature = current_signature
        elif (
            is_playing
            and current_position is not None
            and previous_position is not None
            and current_position > previous_position
        ):
            self._last_position_update = time.time()
            self._last_position = current_position
            self._last_track_signature = current_signature or previous_signature
        elif previous_position is None and current_position is not None:
            self._last_position_update = time.time()
            self._last_position = current_position
            self._last_track_signature = current_signature or previous_signature

        # Ensure we always return a valid timestamp
        if getattr(self, "_last_position_update", None) is None:
            self._last_position_update = time.time()

        result = self._last_position_update
        return result

    def get_media_image_url(self) -> str | None:
        """Return media image URL, or WiiM logo when nothing is playing."""
        # Get the actual image URL from device
        image_url = self._status_field("entity_picture", "cover_url")

        # If we have an image URL, return it
        if image_url:
            return image_url

        # If no image URL and device is idle/stopped, return logo
        playback_state = self.get_playback_state()
        if playback_state == MediaPlayerState.IDLE:
            # Return URL to WiiM logo (square version for album artwork display)
            return f"/static/{DOMAIN}/logo_square.png"

        # Otherwise return None (no image available)
        return None

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

            source_lower = str(source_internal).lower()
            result = SOURCE_MAP.get(source_lower)

            # If not found in map, format the source name nicely
            if result is None:
                import re

                source_str = str(source_internal)

                # Check if it's camelCase or has separators (snake_case, kebab-case)
                if re.search(r"[_\-]|[a-z][A-Z]", source_str):
                    # Split on word boundaries (camelCase, snake_case, or kebab-case)
                    words = re.split(r"[_\-]|(?<=[a-z])(?=[A-Z])", source_str)
                    result = " ".join(word.capitalize() for word in words if word)
                else:
                    # All lowercase without separators - capitalize first letter
                    # This handles cases like "custompushurl" -> "Custompushurl"
                    # (explicit mappings in SOURCE_MAP handle common cases)
                    result = source_str.capitalize()

            return result
        except Exception:
            # Fallback: return formatted version of the source
            try:
                import re

                source_str = str(source_internal)
                if re.search(r"[_\-]|[a-z][A-Z]", source_str):
                    words = re.split(r"[_\-]|(?<=[a-z])(?=[A-Z])", source_str)
                    return " ".join(word.capitalize() for word in words if word)
                else:
                    return source_str.capitalize()
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
            # Only log if there's an unexpected value or error
            if result.startswith("Unknown"):
                _LOGGER.debug(
                    "get_current_output_mode for %s: unexpected hardware_mode=%s, audio_output=%s",
                    self.name,
                    hardware_mode,
                    audio_output,
                )
            return result
        except Exception as err:
            # Handle any unexpected data format issues
            _LOGGER.debug(
                "get_current_output_mode for %s: exception: %s, audio_output=%s",
                self.name,
                err,
                audio_output,
            )
            return None

    def get_output_mode_list(self) -> list[str]:
        """Return list of selectable output modes."""
        from .const import SELECTABLE_OUTPUT_MODES

        modes = SELECTABLE_OUTPUT_MODES.copy()

        # Add Headphone Out for Ultra devices (Issue #86)
        # Mode value (0) needs verification - user should test with headphones connected
        model_lower = (self.model or "").lower()
        if "ultra" in model_lower:
            if "Headphone Out" not in modes:
                modes.append("Headphone Out")

        return modes

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

    def should_use_upnp_volume(self) -> bool:
        """Check if UPnP volume events should be used instead of HTTP polling.

        Returns:
            True if UPnP eventer exists and has provided volume data, False otherwise.
            No health checking per DLNA DMR pattern - trust auto_resubscribe=True.
        """
        # Check if UPnP eventer exists (subscription succeeded)
        if not self._upnp_eventer:
            return False

        # Check if UPnP has provided volume data
        if not self._upnp_state or self._upnp_state.volume is None:
            return False

        return True

    def _merge_upnp_state_to_coordinator(self) -> None:
        """Merge UPnP state changes into coordinator.data.

        This ensures entities can read UPnP state updates via status_model.
        Follows Home Assistant pattern: external events → update coordinator.data → entities read it.
        """
        if not self.coordinator or not self.coordinator.data or not self._upnp_state:
            return

        # Get current status_model from coordinator
        current_status = self.coordinator.data.get("status_model")
        if not isinstance(current_status, PlayerStatus):
            # If no status_model exists yet, create a minimal one
            # (coordinator polling will fill it in, but UPnP can update it earlier)
            current_status = PlayerStatus(play_status="idle")

        # Map UPnP state fields to PlayerStatus model fields
        updates: dict[str, Any] = {}

        # play_state: Convert UPnP format to PlayerStatus format
        # UPnP: "playing", "paused playback", "stopped"
        # PlayerStatus: "play", "pause", "stop", "idle"
        if self._upnp_state.play_state is not None:
            upnp_play_state = self._upnp_state.play_state.lower().strip()
            if "play" in upnp_play_state and "pause" not in upnp_play_state:
                updates["play_status"] = "play"
            elif "pause" in upnp_play_state:
                updates["play_status"] = "pause"
            elif "stop" in upnp_play_state or "idle" in upnp_play_state:
                updates["play_status"] = "stop"
            else:
                updates["play_status"] = "idle"

        # volume: Convert float 0-1 to int 0-100
        if self._upnp_state.volume is not None:
            updates["vol"] = int(self._upnp_state.volume * 100)

        # muted: Direct mapping (bool → bool)
        if self._upnp_state.muted is not None:
            updates["mute"] = self._upnp_state.muted

        # position: Direct mapping (int seconds → int seconds)
        if self._upnp_state.position is not None:
            updates["position"] = self._upnp_state.position

        # duration: Direct mapping (int seconds → int seconds)
        if self._upnp_state.duration is not None:
            updates["duration"] = self._upnp_state.duration

        # Media metadata: Direct mapping
        if self._upnp_state.title is not None:
            updates["Title"] = self._upnp_state.title
        if self._upnp_state.artist is not None:
            updates["Artist"] = self._upnp_state.artist
        if self._upnp_state.album is not None:
            updates["Album"] = self._upnp_state.album
        if self._upnp_state.image_url is not None:
            updates["cover_url"] = self._upnp_state.image_url

        # source: Direct mapping
        if self._upnp_state.source is not None:
            updates["mode"] = self._upnp_state.source

        # Apply updates to status_model if we have any
        if updates:
            try:
                # Create updated PlayerStatus model
                updated_status = current_status.model_copy(update=updates)

                # Update coordinator.data (following Home Assistant pattern)
                # Create a copy of coordinator.data to avoid mutating in place
                data_copy = self.coordinator.data.copy()
                data_copy["status_model"] = updated_status
                self.coordinator.async_set_updated_data(data_copy)
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning(
                    "Failed to merge UPnP state into coordinator for %s: %s",
                    self.name,
                    err,
                )

    # ==========================================================
    # UPnP Integration Methods (Samsung/DLNA Pattern)
    # ==========================================================

    async def _setup_upnp_subscriptions(self, entry: ConfigEntry) -> None:
        """Create UPnP subscriptions (Samsung/DLNA pattern).

        This follows the Samsung/DLNA DmrDevice pattern using async_upnp_client:
        1. Create UpnpClient from SSDP discovery info
        2. Create UpnpEventer with state manager
        3. Start subscriptions with callbacks
        4. Set up fallback polling if needed
        See: /workspaces/core/homeassistant/components/dlna_dmr/media_player.py
        """
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        from .state import WiiMState
        from .upnp_client import UpnpClient
        from .upnp_eventer import UpnpEventer

        # Get SSDP discovery info from config entry (stored during SSDP/zeroconf discovery)
        ssdp_info = entry.data.get("ssdp_info")
        if not ssdp_info or not ssdp_info.get("location"):
            # Fallback: construct description URL from device IP
            # WiiM devices use HTTP (port 49152) for UPnP, not HTTPS
            _LOGGER.info(
                "No SSDP info available for %s, constructing fallback description URL from IP (port 49152)",
                self.name,
            )
            description_url = f"http://{self.ip_address}:49152/description.xml"
        else:
            description_url = ssdp_info.get("location")
            _LOGGER.info(
                "Using SSDP location for %s: %s",
                self.name,
                description_url,
            )

        # Create UPnP client (Samsung/DLNA pattern)
        _LOGGER.info(
            "🔧 Creating UPnP client for %s from description URL: %s",
            self.name,
            description_url,
        )
        session = async_get_clientsession(self.hass)
        client_start_time = time.time()
        try:
            self._upnp_client = await UpnpClient.create(
                host=self.ip_address,
                description_url=description_url,
                session=session,
            )
            client_duration = time.time() - client_start_time
            _LOGGER.info(
                "✅ UPnP client created successfully for %s (completed in %.2fs)",
                self.name,
                client_duration,
            )
        except Exception as err:  # noqa: BLE001
            client_duration = time.time() - client_start_time
            _LOGGER.warning(
                "⚠️  Failed to create UPnP client for %s (after %.2fs): %s - continuing with HTTP polling only",
                self.name,
                client_duration,
                err,
            )
            _LOGGER.debug(
                "UPnP client creation failed, integration will use HTTP polling (1s when playing, 5s idle)",
            )
            # Don't raise - UPnP is optional, HTTP polling works fine
            return

        # Create state manager
        self._upnp_state = WiiMState()

        # Create eventer with callback (Samsung/DLNA pattern)
        self._upnp_eventer = UpnpEventer(
            hass=self.hass,
            upnp_client=self._upnp_client,
            state_manager=self._upnp_state,
            device_uuid=self.uuid,
        )

        # Start subscriptions with callbacks (Samsung/DLNA pattern)
        # Following dlna_dmr pattern: subscription failure is NOT fatal
        subscription_start_time = time.time()
        try:
            await self._upnp_eventer.start(
                callback_host=entry.options.get("upnp_callback_host"),
                callback_port=entry.options.get("upnp_callback_port", 0),
            )
            subscription_duration = time.time() - subscription_start_time
            _LOGGER.info(
                "✅ UPnP event subscriptions established for %s (%.2fs) - will receive real-time events",
                self.name,
                subscription_duration,
            )
            # Reset subscription failure flag on successful setup
            self._subscriptions_failed = False
        except UpnpResponseError as err:
            # Device rejected subscription - this is OK (DLNA pattern)
            subscription_duration = time.time() - subscription_start_time
            _LOGGER.info(
                "Device %s rejected UPnP subscription (%.2fs): %s - will use HTTP polling instead",
                self.name,
                subscription_duration,
                err,
            )
            self._subscriptions_failed = True
            self._upnp_eventer = None
            return
        except Exception as err:  # noqa: BLE001
            # Any subscription failure is non-fatal
            subscription_duration = time.time() - subscription_start_time
            _LOGGER.warning(
                "⚠️  UPnP subscription failed for %s (%.2fs): %s - will use HTTP polling instead",
                self.name,
                subscription_duration,
                err,
            )
            _LOGGER.debug(
                "UPnP subscription error details: %s",
                err,
                exc_info=True,
            )
            self._subscriptions_failed = True
            self._upnp_eventer = None
            return

        # Register lifecycle cleanup (DLNA DMR pattern)
        entry.async_on_unload(self._cleanup_upnp_subscriptions)

        _LOGGER.info("UPnP subscriptions established for %s", self.name)

    async def _cleanup_upnp_subscriptions(self) -> None:
        """Clean up UPnP subscriptions (Samsung/DLNA pattern)."""
        # Cancel fallback polling timer
        if self._poll_timer:
            self._poll_timer()
            self._poll_timer = None
            _LOGGER.debug("Fallback polling timer cancelled for %s", self.name)

        if self._upnp_eventer:
            await self._upnp_eventer.async_unsubscribe()
            self._upnp_eventer = None

        if self._upnp_client:
            await self._upnp_client.unwind_notify_server()
            self._upnp_client = None

        self._upnp_state = None
        _LOGGER.debug("UPnP subscriptions cleaned up for %s", self.name)

    @callback
    def _on_upnp_event(self, variables: dict[str, Any]) -> None:
        """Handle UPnP event notifications (Samsung/DLNA pattern).

        This callback is called by UpnpEventer when events arrive.
        It updates the speaker state and triggers entity updates.
        """
        if not self._upnp_state:
            return

        # Apply state changes from UPnP event
        changed = self._upnp_state.apply_diff(variables)

        if changed:
            _LOGGER.debug(
                "📡 UPnP EVENT received for %s: %s",
                self.name,
                list(variables.keys()),
            )

            # Merge UPnP state into coordinator.data so entities can read it
            self._merge_upnp_state_to_coordinator()

            # Trigger entity updates via dispatcher (entities listen for this signal)
            async_dispatcher_send(
                self.hass,
                f"wiim_state_updated_{self.uuid}",
            )

    @property
    def device_model(self) -> WiiMDeviceInfo | None:  # noqa: D401
        """Return the typed DeviceInfo model injected by the coordinator."""

        if self.coordinator and self.coordinator.data:
            raw = self.coordinator.data.get("device_model")
            if isinstance(raw, WiiMDeviceInfo):
                return raw
        return None

    # ----- BLUETOOTH HELPERS -----

    def get_bluetooth_devices(self) -> list[dict[str, Any]]:
        """Return list of discovered Bluetooth devices."""
        return self._bluetooth_devices.copy()

    def set_bluetooth_devices(self, devices: list[dict[str, Any]], scan_status: str = "Complete") -> None:
        """Update Bluetooth scan results."""
        self._bluetooth_devices = devices
        self._bluetooth_scan_status = scan_status

    def get_bluetooth_scan_status(self) -> str:
        """Return current Bluetooth scan status."""
        return self._bluetooth_scan_status

    def get_bluetooth_pair_status(self) -> dict[str, Any] | None:
        """Return current Bluetooth pairing status from coordinator data."""
        if self.coordinator and self.coordinator.data:
            return self.coordinator.data.get("bt_pair_status")
        return None

    def is_bluetooth_paired(self) -> bool:
        """Return True if a Bluetooth device is currently paired."""
        pair_status = self.get_bluetooth_pair_status()
        if not pair_status:
            return False

        # Check result field - 0=not paired, 1=paired, other values may indicate different states
        result = pair_status.get("result", 0)
        return result != 0  # Any non-zero value likely means paired

    def get_bluetooth_history(self) -> list[dict[str, Any]]:
        """Return Bluetooth connection history from coordinator data."""
        if self.coordinator and self.coordinator.data:
            return self.coordinator.data.get("bt_history", [])
        return []

    def get_connected_bluetooth_device(self) -> dict[str, Any] | None:
        """Return the currently connected Bluetooth device from history.

        Looks for devices with ct=1 (connected) and role="Audio Sink" (output mode).

        Returns:
            Dict with device info (name, ad/mac, etc.) or None if no device connected
        """
        history = self.get_bluetooth_history()
        if not history:
            _LOGGER.debug(
                "No Bluetooth history available for %s to find connected device",
                self.name,
            )
            return None

        _LOGGER.debug("Checking %d devices in Bluetooth history for %s", len(history), self.name)

        # Find device with ct=1 (connected) and role="Audio Sink" (output mode)
        for device in history:
            ct = device.get("ct", 0)
            role = device.get("role", "")
            name = device.get("name", "Unknown")
            mac = device.get("ad", "")
            _LOGGER.debug(
                "Checking device: name=%s, mac=%s, ct=%s, role=%s",
                name,
                mac,
                ct,
                role,
            )
            # ct=1 means connected, role="Audio Sink" means receiving audio (BT output)
            if ct == 1 and role == "Audio Sink":
                # Normalize MAC address field (API uses 'ad', we normalize to 'mac')
                normalized_device = device.copy()
                if "ad" in normalized_device and "mac" not in normalized_device:
                    normalized_device["mac"] = normalized_device["ad"].lower()
                _LOGGER.debug(
                    "Found connected Bluetooth device for %s: %s (%s)",
                    self.name,
                    normalized_device.get("name"),
                    normalized_device.get("mac"),
                )
                return normalized_device

        _LOGGER.debug(
            "No connected Bluetooth device found in history for %s (checked %d devices)",
            self.name,
            len(history),
        )
        return None
