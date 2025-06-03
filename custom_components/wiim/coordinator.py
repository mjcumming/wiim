"""WiiM coordinator for fixed 5-second polling and device updates."""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WiiMClient, WiiMError
from .const import DEFAULT_POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)


class WiiMCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """WiiM coordinator with fixed 5-second polling.

    This coordinator implements simple, reliable polling with fixed intervals:
    - Fixed 5-second polling interval (HA compliant minimum)
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
        poll_interval: int = 5,  # Fixed 5-second polling
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"WiiM {client.host}",
            update_interval=timedelta(seconds=5),  # Fixed 5-second interval
        )
        self.client = client
        self.hass = hass
        self.entry = entry

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

        # Debug: Track update calls
        self._update_count = 0

        _LOGGER.info(
            "[WiiM] Coordinator initialized for %s with fixed 5-second polling",
            client.host,
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

    async def _get_player_status(self) -> dict:
        """Get player status - the only universal endpoint that always works."""
        try:
            _LOGGER.debug("[WiiM] %s: About to call client.get_player_status()", self.client.host)
            result = await self.client.get_player_status() or {}
            _LOGGER.debug("[WiiM] %s: get_player_status() returned: %s", self.client.host, result)
            return result
        except WiiMError as err:
            _LOGGER.warning("[WiiM] %s: getPlayerStatus failed: %s", self.client.host, err)
            raise
        except Exception as err:
            _LOGGER.error("[WiiM] %s: Unexpected error in get_player_status: %s", self.client.host, err)
            raise

    async def _get_device_info_defensive(self) -> dict[str, Any]:
        """Fetch device information, handling potential errors or missing support."""
        try:
            # This method in WiiMClient should return a dict including 'uuid', 'name', 'model', 'firmware', 'mac' etc.
            # It might internally call getStatusEx or other relevant endpoints.
            device_info = await self.client.get_device_info()
            if not device_info.get("uuid"):
                # Fallback or error if UUID is critical and missing post-setup
                _LOGGER.warning("Device UUID missing from get_device_info for %s", self.client.host)
                # Optionally, try to get MAC as a fallback if it's used as part of the unique ID logic
                # For consistency, the unique ID established in ConfigFlow should be the primary one.
                # If the device_info from API doesn't have UUID, but we stored one in config_entry,
                # we might want to inject it here or ensure client always provides it.
                # For now, we assume client.get_device_info() is the source of truth for current state.
            return device_info
        except WiiMError as err:
            _LOGGER.debug(
                "Failed to get device info for %s: %s, device info will be unavailable", self.client.host, err
            )
        return {}

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the WiiM device."""
        try:
            # Prioritize fetching essential data
            player_status = await self._get_player_status()  # Assumed to return a rich status dict
            device_info = await self._get_device_info_defensive()  # Ensure this includes 'uuid'

            # Combine data, ensuring device_info (with uuid) is present
            data: dict[str, Any] = {
                "status": player_status,
                "device_info": device_info,  # Contains uuid, name, model, fw, mac
                "multiroom": {},
                "metadata": {},
                "eq": {},
            }

            # Ensure the UUID from device_info is consistently available
            # The Speaker object will use this.
            if "uuid" not in device_info and self.entry.data.get("uuid"):
                # If API didn't return UUID but we have it from config entry, inject for consistency
                # This scenario should ideally be avoided by robust API client.
                data["device_info"]["uuid"] = self.entry.data.get("uuid")
                _LOGGER.debug("Injected UUID from config entry as API did not provide one")

            # Reset consecutive failures on success
            self._consecutive_failures = 0

            return data

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
                backoff_interval = 15  # Fixed 15-second backoff
                self.update_interval = timedelta(seconds=backoff_interval)
            else:
                # Reset to normal 5-second interval
                self.update_interval = timedelta(seconds=5)

            raise UpdateFailed(f"Error updating WiiM device: {err}") from err

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

    async def _detect_role_from_status_and_slaves(self, status: dict, multiroom: dict) -> str:
        """Detect device role using proper slaves API call."""
        group_field = status.get("group", "0")
        slave_count = multiroom.get("slave_count", 0)

        _LOGGER.warning(
            "[WiiM] %s: Role detection details - group_field='%s', slave_count=%s",
            self.client.host,
            group_field,
            slave_count,
        )

        # Device is MASTER if it has slaves
        if slave_count > 0:
            _LOGGER.warning("[WiiM] %s: Detected as MASTER because slave_count=%s > 0", self.client.host, slave_count)
            return "master"

        # Device is SLAVE if group field > 0 (but no slaves, so it's following another master)
        if group_field != "0":
            _LOGGER.warning("[WiiM] %s: Detected as SLAVE because group='%s' != '0'", self.client.host, group_field)
            return "slave"

        # Default to solo
        _LOGGER.warning("[WiiM] %s: Detected as SOLO (default)", self.client.host)
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
