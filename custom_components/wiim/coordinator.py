"""WiiM coordinator for handling device updates and groups."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WiiMClient, WiiMError
from .const import DEFAULT_POLL_INTERVAL, DOMAIN
from .services.device_registry import get_device_registry
from .services.group_state_manager import create_group_state_manager
from .utils.discovery import async_discover_slaves
from .utils.state_manager import StateManager

_LOGGER = logging.getLogger(__name__)


class WiiMCoordinator(DataUpdateCoordinator):
    """WiiM coordinator with efficient group management.

    This class now uses:
    - Device registry for O(1) device lookups
    - Group state manager for cached group memberships
    - Event-driven updates only when state changes

    Performance improvements:
    - No more expensive coordinator scanning
    - Cached group member calculations
    - State change detection prevents unnecessary work
    """

    def __init__(
        self,
        hass: HomeAssistant,
        client: WiiMClient,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
    ) -> None:
        """Initialize WiiM coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{client._host}",
            update_interval=timedelta(seconds=poll_interval),
        )
        self.client = client
        self.hass = hass

        # High-performance services
        self.device_registry = get_device_registry(hass)
        self.group_state_manager = create_group_state_manager(self, hass)

        # Legacy state manager (for backward compatibility)
        self._state_manager = StateManager(self, hass)

        # Legacy group tracking (gradually being phased out)
        self._group_members: set[str] = set()
        self._is_ha_group_leader = False
        self._ha_group_members: set[str] = set()

        # Poll management
        self._base_poll_interval = poll_interval
        self._consecutive_failures = 0
        self._imported_hosts: set[str] = set()

        # Group registry (legacy, being phased out)
        self._groups: dict[str, dict] = {}

        # Meta info and capability tracking
        self._last_title = None
        self._last_meta_info = {}
        self._meta_info_unsupported = False
        self._status_unsupported = False
        self._logged_entity_not_found_for_ha_group = False

        # Device capabilities
        self.eq_supported: bool = True
        self.eq_enabled: bool = False
        self.eq_presets: list[str] = []
        self.source_supported: bool = True

        # Adaptive polling state
        self._last_play_state = None
        self._last_play_time = None
        self._eq_poll_counter = 0
        self._idle_timeout = 600

        # Device info cache
        self._device_info: dict[str, Any] = {}

        _LOGGER.debug("[WiiM] Coordinator initialized for %s", client.host)

    @property
    def device_uuid(self) -> str | None:
        """Get device UUID from status data."""
        if self.data and isinstance(self.data, dict):
            status = self.data.get("status", {})
            return status.get("uuid")
        return None

    @property
    def device_name(self) -> str:
        """Get device name from status data."""
        if self.data and isinstance(self.data, dict):
            status = self.data.get("status", {})
            return status.get("device_name") or status.get("DeviceName") or self.client.host
        return self.client.host

    def has_slaves(self) -> bool:
        """Check if this device has slaves (making it a master)."""
        if self.data and isinstance(self.data, dict):
            multiroom = self.data.get("multiroom", {})
            return multiroom.get("slaves", 0) > 0
        return False

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data from WiiM device with efficient group management."""
        try:
            # Fetch device data (unchanged from original)
            player_status: dict[str, Any] = {}
            basic_status: dict[str, Any] = {}
            multiroom: dict[str, Any] = {}

            # 1) Player status (getPlayerStatus)
            try:
                player_status = await self.client.get_player_status() or {}
            except WiiMError as err:
                _LOGGER.debug("[WiiM] get_player_status failed on %s: %s", self.client.host, err)
                player_status = {}

            # 2) Basic status (getStatusEx)
            if self._status_unsupported:
                basic_status = {}
            else:
                try:
                    basic_status = await self.client.get_status() or {}
                except WiiMError as err:
                    _LOGGER.debug("[WiiM] get_status unsupported on %s: %s", self.client.host, err)
                    basic_status = {}
                    self._status_unsupported = True

            # 3) Multiroom info
            try:
                multiroom = await self.client.get_multiroom_info() or {}
            except WiiMError as err:
                _LOGGER.debug("[WiiM] get_multiroom_info failed on %s: %s", self.client.host, err)
                multiroom = {}

            # Early exit if all endpoints failed
            if not player_status and not basic_status and not multiroom:
                raise WiiMError("All status endpoints failed")

            # Merge status data
            status = {**basic_status, **player_status}

            # Fetch device info on first update
            if not self._device_info:
                try:
                    self._device_info = await self.client.get_device_info() or {}
                except WiiMError as err:
                    _LOGGER.debug("[WiiM] get_device_info failed on %s: %s", self.client.host, err)
                    self._device_info = {}

            if self._device_info:
                status.update(self._device_info)

            # Adaptive polling logic (unchanged)
            current_title = status.get("title")
            current_play_state = status.get("play_status")

            now = asyncio.get_running_loop().time()
            if current_play_state != self._last_play_state:
                self._last_play_state = current_play_state
                self._last_play_time = now

            if current_play_state == "play":
                self.update_interval = timedelta(seconds=1)
            elif self._last_play_time and (now - self._last_play_time) < self._idle_timeout:
                self.update_interval = timedelta(seconds=5)
            else:
                self.update_interval = timedelta(seconds=10)

            # Meta info handling (unchanged)
            if not self._meta_info_unsupported and (current_title != self._last_title or not self._last_meta_info):
                try:
                    meta_info = await self.client.get_meta_info()
                    if not meta_info:
                        self._meta_info_unsupported = True
                    else:
                        self._last_title = current_title
                        self._last_meta_info = meta_info
                except WiiMError as meta_err:
                    _LOGGER.debug("[WiiM] get_meta_info failed on %s: %s", self.client.host, meta_err)
                    meta_info = self._last_meta_info
            else:
                meta_info = self._last_meta_info

            if meta_info:
                status["album"] = meta_info.get("album")
                status["title"] = meta_info.get("title")
                status["artist"] = meta_info.get("artist")
                cover = meta_info.get("albumArtURI")
                if cover:
                    title = meta_info.get("title") or ""
                    artist = meta_info.get("artist") or ""
                    album = meta_info.get("album") or ""
                    cache_key = f"{title}-{artist}-{album}"
                    from urllib.parse import quote

                    if cache_key and "?" not in cover:
                        cover = f"{cover}?cache={quote(cache_key)}"
                status["entity_picture"] = cover

            # EQ information (unchanged)
            self._eq_poll_counter += 1
            if self.eq_supported and self._eq_poll_counter >= 3:
                self._eq_poll_counter = 0
                try:
                    eq_enabled = await self.client.get_eq_status()
                    self.eq_enabled = eq_enabled
                    status["eq_enabled"] = eq_enabled

                    eq_info = await self.client.get_eq()
                    if eq_info:
                        mode_raw = eq_info.get("mode")
                        if mode_raw is not None:
                            preset = self.client._EQ_NUMERIC_MAP.get(str(mode_raw), mode_raw)
                            status["eq_preset"] = preset

                        if "custom" in eq_info and isinstance(eq_info["custom"], list):
                            status["eq_custom"] = eq_info["custom"]

                    if not self.eq_presets:
                        self.eq_presets = await self.client.get_eq_presets()
                        status["eq_presets"] = self.eq_presets

                except Exception as eq_err:
                    if isinstance(eq_err, Exception) and "unknown command" in str(eq_err).lower():
                        if self.eq_supported:
                            _LOGGER.info("[WiiM] %s: getEQ not supported", self.client.host)
                        self.eq_supported = False
                    _LOGGER.debug("[WiiM] get_eq failed on %s: %s", self.client.host, eq_err)

            # Parse sources (unchanged)
            plm_support = status.get("plm_support", "0")
            sources = self._parse_plm_support(plm_support)
            status["sources"] = sources

            # Streaming service (unchanged)
            vendor_raw = str(status.get("vendor", "")).strip()
            if vendor_raw and vendor_raw.lower() not in ("", "unknown", "unknow"):
                vendor_clean = vendor_raw.split(":", 1)[0]
                status["streaming_service"] = vendor_clean.title()

            # ** NEW: Efficient group state management **
            # Use the new group state manager to detect changes
            group_state_changed = self.group_state_manager.update_from_status(status, multiroom)

            # Get the detected role from the state manager
            role = self.group_state_manager.get_current_role()

            if group_state_changed:
                _LOGGER.debug("[WiiM] %s: Group state changed, new role: %s", self.client.host, role)

                # Register/update device in registry after first successful data fetch
                self.device_registry.register_device(self)

                # Trigger state updates for all group members when group composition changes
                await self._propagate_group_state_changes(role, multiroom)
            else:
                # Even if role didn't change, ensure device is registered
                if not self.device_registry.get_device_by_ip(self.client.host):
                    self.device_registry.register_device(self)

            # Reset consecutive failures on successful update
            if self._consecutive_failures > 0:
                self._consecutive_failures = 0
                if (
                    self.update_interval is not None
                    and self.update_interval.total_seconds() != self._base_poll_interval
                ):
                    self.update_interval = timedelta(seconds=self._base_poll_interval)

            # Legacy group management (keeping for backward compatibility)
            self._group_members = {entry.get("ip") for entry in multiroom.get("slave_list", []) if entry.get("ip")}
            await self._async_trigger_slave_discovery()

            # Override source for non-slaves showing 'follower'
            if role != "slave" and status.get("source") == "follower":
                _LOGGER.debug(
                    "[WiiM] %s: Overriding stray 'follower' source with 'wifi' (role=%s)", self.client.host, role
                )
                status["source"] = "wifi"

            # Build final result
            result = {
                "status": status,
                "multiroom": multiroom,
                "role": role,
                "ha_group": {
                    "is_leader": self._is_ha_group_leader,
                    "members": list(self._ha_group_members),
                },
            }

            _LOGGER.debug("[WiiM] %s: Successfully updated data, role=%s", self.client.host, role)
            return result

        except WiiMError as err:
            self._consecutive_failures += 1
            _LOGGER.warning(
                "[WiiM] %s: Update failed (attempt %d): %s", self.client.host, self._consecutive_failures, err
            )

            if self._consecutive_failures >= 3:
                new_interval = min(self._base_poll_interval * (2 ** (self._consecutive_failures - 2)), 60)
                if self.update_interval is None or new_interval != self.update_interval.total_seconds():
                    self.update_interval = timedelta(seconds=new_interval)

            raise UpdateFailed(f"Error updating WiiM device: {err}") from err

    # ** NEW: High-performance group member access **
    def get_cached_group_members(self) -> list[str]:
        """Get cached group members with O(1) performance."""
        return self.group_state_manager.get_cached_group_members()

    def get_cached_group_leader(self) -> str | None:
        """Get cached group leader with O(1) performance."""
        return self.group_state_manager.get_cached_group_leader()

    def get_current_role(self) -> str:
        """Get current device role with O(1) performance."""
        return self.group_state_manager.get_current_role()

    # Legacy methods (keeping for backward compatibility)
    def _parse_plm_support(self, plm_support: str) -> list[str]:
        """Parse plm_support bitmask into list of available sources."""
        try:
            mask = int(plm_support, 16)
            sources = []

            if mask & 0x1:
                sources.append("line_in")
            if mask & 0x2:
                sources.append("bluetooth")
            if mask & 0x4:
                sources.append("usb")
            if mask & 0x8:
                sources.append("optical")
            if mask & 0x20:
                sources.append("coaxial")
            if mask & 0x80:
                sources.append("line_in_2")
            if mask & 0x8000:
                sources.append("usbdac")

            sources.extend(["wifi", "airplay", "dlna"])
            return sources
        except (ValueError, TypeError):
            _LOGGER.error("[WiiM] Failed to parse plm_support: %s", plm_support)
            return []

    async def _async_trigger_slave_discovery(self) -> None:
        """Trigger discovery of slave devices."""
        if not self.data or not self.data.get("multiroom"):
            return

        multiroom = self.data["multiroom"]
        slave_list = multiroom.get("slave_list", [])

        if not slave_list:
            return

        slave_ips = []
        for slave in slave_list:
            if isinstance(slave, dict) and slave.get("ip"):
                slave_ips.append(slave["ip"])

        if slave_ips:
            try:
                await async_discover_slaves(self.hass, slave_ips)
            except Exception as err:
                _LOGGER.debug("Failed to trigger slave discovery: %s", err)

    # Legacy properties and methods (keeping for backward compatibility)
    @property
    def is_wiim_master(self) -> bool:
        """Return whether this device is a WiiM multiroom master."""
        return self.client.is_master

    @property
    def is_wiim_slave(self) -> bool:
        """Return whether this device is a WiiM multiroom slave."""
        return self.client.is_slave

    @property
    def wiim_group_members(self) -> set[str]:
        """Return set of WiiM group member IPs."""
        return self._group_members

    @property
    def is_ha_group_leader(self) -> bool:
        """Return whether this device is a HA media player group leader."""
        return self._is_ha_group_leader

    @property
    def ha_group_members(self) -> set[str]:
        """Return set of HA group member entity IDs."""
        return self._ha_group_members

    @property
    def groups(self) -> dict:
        """Return the current group registry."""
        return self._groups

    @property
    def friendly_name(self) -> str:
        """Return a human-friendly name for the device."""
        status = self.data.get("status", {}) if isinstance(self.data, dict) else {}
        return status.get("device_name") or status.get("DeviceName") or self.client.host

    # Group management methods (legacy compatibility)
    async def create_wiim_group(self) -> None:
        """Create a WiiM multiroom group."""
        try:
            await self.client.create_group()
            await self.async_refresh()
        except WiiMError as err:
            _LOGGER.error("[WiiM] Failed to create WiiM group for %s: %s", self.client.host, err)
            raise

    async def delete_wiim_group(self) -> None:
        """Delete the WiiM multiroom group."""
        try:
            await self.client.delete_group()
            await self.async_refresh()
        except WiiMError as err:
            _LOGGER.error("[WiiM] Failed to delete WiiM group for %s: %s", self.client.host, err)
            raise

    async def join_wiim_group(self, master_ip: str) -> None:
        """Join a WiiM multiroom group."""
        try:
            await self.client.join_group(master_ip)
            await self.async_refresh()
        except WiiMError as err:
            _LOGGER.error("[WiiM] Failed to join WiiM group: %s", err)
            raise

    async def leave_wiim_group(self) -> None:
        """Leave the WiiM multiroom group."""
        try:
            await self.client.leave_group()
            await self.async_refresh()
        except WiiMError as err:
            _LOGGER.error("[WiiM] Failed to leave WiiM group: %s", err)
            raise

    async def _propagate_group_state_changes(self, role: str, multiroom: dict[str, Any]) -> None:
        """Propagate group state changes to all group members to ensure UI updates."""
        _LOGGER.debug("[WiiM] %s: Propagating group state changes for role=%s", self.client.host, role)

        # Get all affected IPs (both current slaves and potentially previous slaves)
        affected_ips = set()

        # Add current slaves
        if role == "master":
            for slave in multiroom.get("slave_list", []):
                if isinstance(slave, dict) and slave.get("ip"):
                    affected_ips.add(slave["ip"])

        # Add self
        affected_ips.add(self.client.host)

        # For slaves, also try to update the master
        if role == "slave":
            master_ip = self.data.get("status", {}).get("master_ip") if self.data else None
            if master_ip:
                affected_ips.add(master_ip)

        _LOGGER.info(
            "[WiiM] %s: Group state change affects %d devices: %s",
            self.client.host,
            len(affected_ips),
            list(affected_ips),
        )

        # Trigger async refresh for all affected coordinators
        for ip in affected_ips:
            coord = self.device_registry.get_device_by_ip(ip)
            if coord:
                try:
                    # Force clear cached group state to ensure fresh calculation
                    coord.group_state_manager._current_state = None
                    _LOGGER.debug("[WiiM] %s: Cleared cached group state for %s", self.client.host, ip)

                    # Always trigger refresh for group members to recalculate group state
                    # Even for self, since cache was cleared and needs recalculation
                    self.hass.async_create_task(coord.async_request_refresh())
                    _LOGGER.debug("[WiiM] %s: Triggered refresh for group member %s", self.client.host, ip)
                except Exception as err:
                    _LOGGER.debug("[WiiM] %s: Failed to trigger refresh for %s: %s", self.client.host, ip, err)
