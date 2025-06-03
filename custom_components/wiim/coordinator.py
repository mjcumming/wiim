"""WiiM coordinator for defensive two-state polling and device updates."""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WiiMClient, WiiMError
from .const import CONF_IDLE_UPDATE_RATE, CONF_PLAYING_UPDATE_RATE, DEFAULT_POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)


class WiiMCoordinator(DataUpdateCoordinator):
    """WiiM coordinator with defensive two-state polling.

    This coordinator implements simple, reliable polling that adapts to device state:
    - Fast polling (1s) when playing for smooth position updates
    - Slower polling (5s) when idle for efficiency
    - Defensive programming with graceful API fallbacks
    - Never fails hard - always has fallbacks for unreliable endpoints

    Key principles:
    - getPlayerStatus is the only universal endpoint (works on all devices)
    - getStatusEx is WiiM-specific (not available on pure LinkPlay)
    - getMetaInfo may not work on many LinkPlay devices
    - EQ endpoints are highly inconsistent across manufacturers
    """

    def __init__(
        self,
        hass: HomeAssistant,
        client: WiiMClient,
        entry=None,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"WiiM {client.host}",
            update_interval=timedelta(seconds=poll_interval),
        )
        self.client = client
        self.hass = hass
        self.entry = entry

        # Defensive polling configuration
        self._playing_interval = 1  # 1 second when playing
        self._idle_interval = 5  # 5 seconds when idle

        # Load user preferences if available
        if entry and entry.options:
            self._playing_interval = entry.options.get(CONF_PLAYING_UPDATE_RATE, 1)
            self._idle_interval = entry.options.get(CONF_IDLE_UPDATE_RATE, 5)

        # API capability flags (None = untested, True/False = tested)
        self._statusex_supported: bool | None = None
        self._metadata_supported: bool | None = None
        self._eq_supported: bool | None = None

        # Device state tracking
        self._last_status = {}
        self._consecutive_failures = 0
        self._device_info = None

        # Track device info update timing (every 30-60 seconds)
        self._last_device_info_update = 0
        self._device_info_interval = 30

        _LOGGER.info(
            "[WiiM] Defensive coordinator initialized for %s (playing=%ds, idle=%ds)",
            client.host,
            self._playing_interval,
            self._idle_interval,
        )

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
        """Defensive two-state polling with graceful API fallbacks."""
        try:
            # ALWAYS RELIABLE: Core playbook status (universal endpoint)
            status = await self._get_player_status()

            # Two-state polling: fast when playing, slower when idle
            is_playing = status.get("play_status") == "play"
            if is_playing:
                self.update_interval = timedelta(seconds=self._playing_interval)
            else:
                self.update_interval = timedelta(seconds=self._idle_interval)

            # DEFENSIVE: Device info with WiiM enhancement fallback
            if self._should_update_device_info():
                device_info = await self._get_device_info_defensive()
                if device_info:
                    status.update(device_info)
                    self._device_info = device_info

            # DEFENSIVE: Multiroom info with graceful failure
            multiroom = await self._get_multiroom_info_defensive()

            # DEFENSIVE: Track metadata with fallback
            if self._track_changed(status):
                metadata = await self._get_track_metadata_defensive(status)
                if metadata:
                    status.update(metadata)

            # DEFENSIVE: EQ info (only if device supports it)
            if self._eq_supported is not False:
                eq_info = await self._get_eq_info_defensive()
                if eq_info:
                    status.update(eq_info)

            # Detect role and build result
            role = self._detect_role_from_status(status, multiroom)

            # Update Speaker object if available
            await self._update_speaker_object(status, multiroom, role)

            # Reset consecutive failures on success
            self._consecutive_failures = 0

            result = {
                "status": status,
                "multiroom": multiroom,
                "role": role,
                "polling": {
                    "interval": self.update_interval.total_seconds(),
                    "is_playing": is_playing,
                    "api_capabilities": {
                        "statusex_supported": self._statusex_supported,
                        "metadata_supported": self._metadata_supported,
                        "eq_supported": self._eq_supported,
                    },
                },
            }

            _LOGGER.debug(
                "[WiiM] %s: Update completed - role=%s, playing=%s, interval=%ds",
                self.client.host,
                role,
                is_playing,
                self.update_interval.total_seconds(),
            )
            return result

        except WiiMError as err:
            self._consecutive_failures += 1
            _LOGGER.warning(
                "[WiiM] %s: Update failed (attempt %d): %s",
                self.client.host,
                self._consecutive_failures,
                err,
            )

            # Simple backoff: increase interval on failures
            if self._consecutive_failures >= 3:
                backoff_interval = min(30, self._idle_interval * 2)
                self.update_interval = timedelta(seconds=backoff_interval)

            raise UpdateFailed(f"Error updating WiiM device: {err}") from err

    async def _get_player_status(self) -> dict:
        """Get player status - the only universal endpoint that always works."""
        try:
            return await self.client.get_player_status() or {}
        except WiiMError as err:
            _LOGGER.warning("[WiiM] %s: getPlayerStatus failed: %s", self.client.host, err)
            raise

    async def _get_device_info_defensive(self) -> dict:
        """Get device info with WiiM enhancement fallback."""
        # Try WiiM-enhanced getStatusEx first
        if self._statusex_supported is not False:
            try:
                result = await self.client.get_status()  # This calls getStatusEx internally
                if self._statusex_supported is None:
                    self._statusex_supported = True
                    _LOGGER.debug("[WiiM] %s: getStatusEx works - WiiM device", self.client.host)
                return result
            except WiiMError:
                if self._statusex_supported is None:
                    self._statusex_supported = False
                    _LOGGER.info("[WiiM] %s: getStatusEx not supported - pure LinkPlay device", self.client.host)

        # CRITICAL: getStatus doesn't work on WiiM devices!
        # For pure LinkPlay devices, we would fallback to basic getStatus
        # But since user confirmed getStatus doesn't work on WiiM devices,
        # we only try getStatusEx and gracefully handle failure

        _LOGGER.debug("[WiiM] %s: No device info available (getStatusEx failed)", self.client.host)
        return {}

    async def _get_multiroom_info_defensive(self) -> dict:
        """Get multiroom info with graceful failure handling."""
        try:
            return await self.client.get_multiroom_info() or {}
        except WiiMError as err:
            _LOGGER.debug("[WiiM] %s: get_multiroom_info failed: %s", self.client.host, err)
            return {}

    async def _get_track_metadata_defensive(self, status: dict) -> dict:
        """Get track metadata with graceful fallback when getMetaInfo fails."""
        if self._metadata_supported is False:
            # Already know this device doesn't support getMetaInfo
            return self._extract_basic_metadata(status)

        try:
            metadata = await self.client.get_meta_info()
            if metadata and metadata.get("metaData"):
                if self._metadata_supported is None:
                    self._metadata_supported = True
                    _LOGGER.debug("[WiiM] %s: getMetaInfo works - full metadata available", self.client.host)
                return metadata["metaData"]
        except WiiMError:
            if self._metadata_supported is None:
                self._metadata_supported = False
                _LOGGER.info("[WiiM] %s: getMetaInfo not supported - using basic metadata", self.client.host)

        # Fallback: Extract basic metadata from player status
        return self._extract_basic_metadata(status)

    def _extract_basic_metadata(self, status: dict) -> dict:
        """Extract basic metadata from player status when getMetaInfo unavailable."""
        metadata = {}
        if status.get("title"):
            metadata["title"] = status["title"]
        if status.get("artist"):
            metadata["artist"] = status["artist"]
        if status.get("album"):
            metadata["album"] = status["album"]
        # Note: No album artwork available in basic status
        return metadata

    async def _get_eq_info_defensive(self) -> dict:
        """Get EQ info only if device supports it."""
        if self._eq_supported is False:
            # Already know this device doesn't support EQ
            return {}

        try:
            eq_enabled = await self.client.get_eq_status()
            eq_info = {"eq_enabled": eq_enabled}

            if eq_enabled:
                eq_data = await self.client.get_eq()
                if eq_data:
                    eq_info.update(eq_data)

            if self._eq_supported is None:
                self._eq_supported = True
                _LOGGER.debug("[WiiM] %s: EQ endpoints work", self.client.host)

            return eq_info

        except WiiMError:
            if self._eq_supported is None:
                self._eq_supported = False
                _LOGGER.info("[WiiM] %s: EQ not supported by device", self.client.host)
            return {}

    def _should_update_device_info(self) -> bool:
        """Check if we should update device info (every 30-60 seconds)."""
        now = time.time()
        if now - self._last_device_info_update >= self._device_info_interval:
            self._last_device_info_update = now
            return True
        return False

    def _track_changed(self, status: dict) -> bool:
        """Check if track changed (indicates need for metadata update)."""
        current_title = status.get("title")
        if not current_title:
            return False

        last_title = self._last_status.get("title")
        changed = current_title != last_title

        if changed:
            _LOGGER.debug("[WiiM] %s: Track changed: %s -> %s", self.client.host, last_title, current_title)

        self._last_status = status.copy()
        return changed

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

    async def _update_speaker_object(self, status: dict, multiroom: dict, role: str) -> None:
        """Update Speaker object if it exists."""
        try:
            from .data import get_wiim_data

            wiim_data = get_wiim_data(self.hass)

            # Find speaker for this coordinator
            speaker = None
            for spk in wiim_data.speakers.values():
                if spk.coordinator is self:
                    speaker = spk
                    break

            if speaker:
                # Build data structure for speaker update
                update_data = {
                    "status": status,
                    "multiroom": multiroom,
                    "role": role,
                }
                speaker.update_from_coordinator_data(update_data)

        except Exception as speaker_err:
            # Don't fail coordinator update if Speaker update fails
            _LOGGER.debug(
                "[WiiM] %s: Speaker update failed: %s",
                self.client.host,
                speaker_err,
            )

    # User interaction methods
    def record_user_command(self, command_type: str) -> None:
        """Record user command and force immediate update."""
        _LOGGER.debug("[WiiM] %s: User command '%s' - requesting immediate refresh", self.client.host, command_type)
        # Force immediate refresh by setting short interval
        self.update_interval = timedelta(seconds=1)

    async def async_request_refresh(self) -> None:
        """Request immediate refresh of coordinator data."""
        await self.async_request_refresh()

    # Group management methods (simplified from legacy)
    def get_current_role(self) -> str:
        """Get current device role."""
        if self.data and isinstance(self.data, dict):
            return self.data.get("role", "solo")
        return "solo"

    def get_cached_group_members(self) -> list[str]:
        """Get cached group member IPs."""
        if self.data and isinstance(self.data, dict):
            multiroom = self.data.get("multiroom", {})
            return [entry.get("ip") for entry in multiroom.get("slave_list", []) if entry.get("ip")]
        return []

    def get_cached_group_leader(self) -> str | None:
        """Get cached group leader IP."""
        if self.data and isinstance(self.data, dict):
            status = self.data.get("status", {})
            return status.get("master_ip")
        return None

    # Legacy compatibility properties
    @property
    def is_wiim_master(self) -> bool:
        """Check if device is a WiiM group master."""
        return self.get_current_role() == "master"

    @property
    def is_wiim_slave(self) -> bool:
        """Check if device is a WiiM group slave."""
        return self.get_current_role() == "slave"

    @property
    def wiim_group_members(self) -> set[str]:
        """Get WiiM group member IPs."""
        return set(self.get_cached_group_members())

    @property
    def friendly_name(self) -> str:
        """Return friendly name for the device."""
        return self.device_name
