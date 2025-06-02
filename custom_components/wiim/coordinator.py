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
from .device_registry import get_device_registry

_LOGGER = logging.getLogger(__name__)


class WiiMCoordinator(DataUpdateCoordinator):
    """WiiM coordinator with efficient group management.

    This class now uses:
    - Device registry for O(1) device lookups and role tracking
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

        # High-performance device registry
        self.device_registry = get_device_registry(hass)

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

    def _detect_role_from_status(self, status: dict, multiroom: dict) -> str:
        """Detect device role from status data."""
        # Device is slave if group field > 0
        if status.get("group", "0") != "0":
            return "slave"

        # Device is master if it has slaves
        if multiroom.get("slaves", 0) > 0:
            return "master"

        # Default to solo
        return "solo"

    def _extract_master_info_for_slave(self, status: dict, multiroom: dict) -> dict:
        """Extract master information when device is a slave."""
        # Add master information to status for registry
        if status.get("group", "0") != "0":
            # Try to extract master info from various fields
            if "master_ip" not in status:
                # Look for master_uuid and try to match with known devices
                master_uuid = status.get("master_uuid")
                if master_uuid:
                    status["master_uuid"] = master_uuid
                    # The registry will handle IP lookup by UUID
        return status

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

            # ** NEW: Efficient role change detection and registry update **
            old_role = self.device_registry.get_device_role(self.client.host)
            new_role = self._detect_role_from_status(status, multiroom)

            # Extract master info for slaves
            if new_role == "slave":
                status = self._extract_master_info_for_slave(status, multiroom)

            # Register device in registry on first update
            self.device_registry.register_device(self)

            # Handle role changes
            role_changed = False
            if old_role != new_role:
                role_changed = await self.device_registry.handle_role_change(
                    self.client.host, old_role, new_role, status
                )

                if role_changed:
                    _LOGGER.debug("[WiiM] %s: Role changed %s -> %s", self.client.host, old_role, new_role)
                    # Trigger state updates for affected devices
                    await self._propagate_group_state_changes(new_role, multiroom)

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
            if new_role != "slave" and status.get("source") == "follower":
                _LOGGER.debug(
                    "[WiiM] %s: Overriding stray 'follower' source with 'wifi' (role=%s)", self.client.host, new_role
                )
                status["source"] = "wifi"

            # Build final result
            result = {
                "status": status,
                "multiroom": multiroom,
                "role": new_role,
                "ha_group": {
                    "is_leader": self._is_ha_group_leader,
                    "members": list(self._ha_group_members),
                },
            }

            _LOGGER.debug("[WiiM] %s: Successfully updated data, role=%s", self.client.host, new_role)
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
        return self.device_registry.get_group_members_for_device(self.client.host)

    def get_cached_group_leader(self) -> str | None:
        """Get cached group leader with O(1) performance."""
        return self.device_registry.get_group_leader_for_device(self.client.host)

    def get_current_role(self) -> str:
        """Get current device role with O(1) performance."""
        return self.device_registry.get_device_role(self.client.host)

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
        """Trigger discovery of slave devices - DEPRECATED."""
        # This method is kept for backward compatibility but does nothing
        # as the device registry handles device discovery automatically
        pass

    # Legacy properties and methods (keeping for backward compatibility)
    @property
    def is_wiim_master(self) -> bool:
        """Return whether this device is a WiiM multiroom master."""
        return self.device_registry.get_device_role(self.client.host) == "master"

    @property
    def is_wiim_slave(self) -> bool:
        """Return whether this device is a WiiM multiroom slave."""
        return self.device_registry.get_device_role(self.client.host) == "slave"

    @property
    def wiim_group_members(self) -> set[str]:
        """Return set of slave IPs if this device is a master."""
        if self.device_registry.get_device_role(self.client.host) == "master":
            return self.device_registry.get_slave_ips(self.client.host)
        return set()

    @property
    def is_ha_group_leader(self) -> bool:
        """Return whether this device is a Home Assistant group leader."""
        return self._is_ha_group_leader

    @property
    def ha_group_members(self) -> set[str]:
        """Return Home Assistant group members."""
        return self._ha_group_members

    @property
    def groups(self) -> dict:
        """Return groups."""
        return self._groups

    @property
    def friendly_name(self) -> str:
        """Return friendly name for this device."""
        if self.data and isinstance(self.data, dict):
            status = self.data.get("status", {})
            return status.get("DeviceName") or status.get("device_name") or self.client.host
        return self.client.host

    async def create_wiim_group(self) -> None:
        """Create a new WiiM multiroom group."""
        try:
            await self.client.create_group()
            await self.async_request_refresh()
        except WiiMError as err:
            _LOGGER.error("[WiiM] Failed to create group: %s", err)
            raise

    async def delete_wiim_group(self) -> None:
        """Delete WiiM multiroom group."""
        try:
            await self.client.delete_group()
            await self.async_request_refresh()
        except WiiMError as err:
            _LOGGER.error("[WiiM] Failed to delete group: %s", err)
            raise

    async def join_wiim_group(self, master_ip: str) -> None:
        """Join a WiiM multiroom group."""
        try:
            await self.client.join_group(master_ip)
            await self.async_request_refresh()
        except WiiMError as err:
            _LOGGER.error("[WiiM] Failed to join group: %s", err)
            raise

    async def leave_wiim_group(self) -> None:
        """Leave WiiM multiroom group."""
        try:
            await self.client.leave_group()
            await self.async_request_refresh()
        except WiiMError as err:
            _LOGGER.error("[WiiM] Failed to leave group: %s", err)
            raise

    async def _propagate_group_state_changes(self, role: str, multiroom: dict[str, Any]) -> None:
        """Propagate group state changes to affected devices."""
        affected_ips = set()
        affected_ips.add(self.client.host)

        # Add all devices in current or former groups
        if role == "master":
            slave_list = multiroom.get("slave_list", [])
            for slave in slave_list:
                if isinstance(slave, dict) and slave.get("ip"):
                    affected_ips.add(slave["ip"])
        elif role == "slave":
            master_ip = self.data.get("status", {}).get("master_ip") if self.data else None
            if master_ip:
                affected_ips.add(master_ip)

        _LOGGER.info(
            "[WiiM] %s: Group state change affects %d devices: %s",
            self.client.host,
            len(affected_ips),
            list(affected_ips),
        )

        # Trigger refresh for all affected coordinators
        for ip in affected_ips:
            coordinator = self.device_registry.get_coordinator(ip)
            if coordinator and coordinator != self:
                _LOGGER.debug("[WiiM] %s: Cleared cached group state for %s", self.client.host, ip)
                try:
                    _LOGGER.debug("[WiiM] %s: Triggered refresh for group member %s", self.client.host, ip)
                    await coordinator.async_request_refresh()
                except Exception as err:
                    _LOGGER.debug("[WiiM] %s: Failed to refresh %s: %s", self.client.host, ip, err)
