"""WiiM coordinator for fixed 5-second polling and device updates."""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WiiMClient, WiiMError
from .const import FIXED_POLL_INTERVAL

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
    ) -> None:
        """Initialize the coordinator with fixed 5-second polling."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"WiiM {client.host}",
            update_interval=timedelta(seconds=FIXED_POLL_INTERVAL),  # Fixed interval
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
            "Coordinator initialized for %s with fixed %d-second polling",
            client.host,
            FIXED_POLL_INTERVAL,
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
                # Some devices don't provide UUID in their API responses - this is normal
                # The integration uses the unique_id from config entry (set during discovery)
                _LOGGER.debug(
                    "Device API does not provide UUID for %s (using config entry unique_id instead)", self.client.host
                )
                # Note: The unique ID established in ConfigFlow is the primary one and is sufficient
                # This missing API UUID does not affect integration functionality
            return device_info
        except WiiMError as err:
            _LOGGER.debug(
                "Failed to get device info for %s: %s, device info will be unavailable", self.client.host, err
            )
        return {}

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the WiiM device."""
        _LOGGER.debug("=== COORDINATOR UPDATE START for %s ===", self.client.host)

        try:
            # Core data - always required
            player_status = await self._get_player_status()
            _LOGGER.debug("Player status result for %s: %s", self.client.host, player_status)

            _LOGGER.debug("Step 2: Getting device info for %s", self.client.host)
            device_info = await self._get_device_info_defensive()
            _LOGGER.debug("Device info result for %s: %s", self.client.host, device_info)

            # Additional data with defensive programming
            _LOGGER.debug("Step 3: Getting multiroom info for %s", self.client.host)
            multiroom_info = await self._get_multiroom_info_defensive()
            _LOGGER.debug("Multiroom info result for %s: %s", self.client.host, multiroom_info)

            _LOGGER.debug("Step 4: Getting track metadata for %s", self.client.host)
            track_metadata = await self._get_track_metadata_defensive(player_status)
            _LOGGER.debug("Track metadata result for %s: %s", self.client.host, track_metadata)

            _LOGGER.debug("Step 5: Getting EQ info for %s", self.client.host)
            eq_info = await self._get_eq_info_defensive()
            _LOGGER.debug("EQ info result for %s: %s", self.client.host, eq_info)

            # Detect role using the fetched data
            _LOGGER.debug("Step 6: Detecting role for %s", self.client.host)
            role = await self._detect_role_from_status_and_slaves(player_status, multiroom_info, device_info)
            _LOGGER.debug("Detected role for %s: %s", self.client.host, role)

            # Prepare polling data for diagnostic sensors
            polling_data = {
                "interval": self.update_interval.total_seconds(),
                "is_playing": (player_status.get("play_status") or player_status.get("status", "")).lower() == "play",
                "api_capabilities": {
                    "statusex_supported": self._statusex_supported,
                    "metadata_supported": self._metadata_supported,
                    "eq_supported": self._eq_supported,
                },
            }

            # Comprehensive data dictionary
            data: dict[str, Any] = {
                "status": player_status,
                "device_info": device_info,
                "multiroom": multiroom_info,
                "metadata": track_metadata,
                "eq": eq_info,
                "role": role,
                "polling": polling_data,
            }

            # Inject UUID if missing
            if "uuid" not in device_info and self.entry.unique_id:
                data["device_info"]["uuid"] = self.entry.unique_id
                _LOGGER.debug("Injected UUID from config entry as API did not provide one")

            _LOGGER.debug("Step 7: Final coordinator data for %s: %s", self.client.host, data)

            # Update speaker object with comprehensive data
            _LOGGER.debug("Step 8: Updating speaker object for %s", self.client.host)
            await self._update_speaker_object(data)

            self._consecutive_failures = 0
            _LOGGER.debug("=== COORDINATOR UPDATE SUCCESS for %s ===", self.client.host)
            return data

        except WiiMError as err:
            self._consecutive_failures += 1
            _LOGGER.error("=== COORDINATOR UPDATE FAILED for %s ===", self.client.host)
            _LOGGER.error("Update failed for %s (attempt %d): %s", self.client.host, self._consecutive_failures, err)
            # Simplified backoff
            if self._consecutive_failures >= 3:
                self.update_interval = timedelta(seconds=15)
            raise UpdateFailed(f"Error updating WiiM device: {err}") from err

    async def _get_multiroom_info_defensive(self) -> dict:
        """Get multiroom info with graceful failure handling."""
        try:
            return await self.client.get_multiroom_info() or {}
        except WiiMError as err:
            _LOGGER.debug("[WiiM] %s: get_multiroom_info failed: %s", self.client.host, err)
            return {}

    async def _get_track_metadata_defensive(self, status: dict) -> dict:
        """Get track metadata with graceful fallback when getMetaInfo fails.

        Enhanced to better extract cover art and media information.
        """
        if self._metadata_supported is False:
            # Already know this device doesn't support getMetaInfo
            return self._extract_basic_metadata(status)

        try:
            metadata_response = await self.client.get_meta_info()
            if metadata_response and metadata_response.get("metaData"):
                metadata = metadata_response["metaData"]
                if self._metadata_supported is None:
                    self._metadata_supported = True
                    _LOGGER.debug("[WiiM] %s: getMetaInfo works - full metadata available", self.client.host)

                # Enhance metadata with cover art extraction
                enhanced_metadata = self._enhance_metadata_with_artwork(metadata, status)
                _LOGGER.debug("[WiiM] %s: Enhanced metadata: %s", self.client.host, enhanced_metadata)
                return enhanced_metadata
        except WiiMError:
            if self._metadata_supported is None:
                self._metadata_supported = False
                _LOGGER.info("[WiiM] %s: getMetaInfo not supported - using basic metadata", self.client.host)

        # Fallback: Extract basic metadata from player status
        return self._extract_basic_metadata(status)

    def _enhance_metadata_with_artwork(self, metadata: dict, status: dict) -> dict:
        """Enhance metadata with cover art information from multiple sources."""
        # Start with the metadata from getMetaInfo
        enhanced = metadata.copy()

        # Extract cover art from multiple possible fields
        artwork_fields = [
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

        _LOGGER.debug("[WiiM] %s: Looking for artwork in metadata fields: %s", self.client.host, list(metadata.keys()))
        _LOGGER.debug("[WiiM] %s: Looking for artwork in status fields: %s", self.client.host, list(status.keys()))

        # Check metadata first, then status
        artwork_url = None
        found_in_source = None
        found_in_field = None

        # Check metadata first
        for field in artwork_fields:
            artwork_url = metadata.get(field)
            if artwork_url:
                found_in_source = "metadata"
                found_in_field = field
                _LOGGER.debug(
                    "[WiiM] %s: Found artwork in metadata field '%s': %s", self.client.host, field, artwork_url
                )
                break

        # Then check status if not found in metadata
        if not artwork_url:
            for field in artwork_fields:
                artwork_url = status.get(field)
                if artwork_url:
                    found_in_source = "status"
                    found_in_field = field
                    _LOGGER.debug(
                        "[WiiM] %s: Found artwork in status field '%s': %s", self.client.host, field, artwork_url
                    )
                    break

        if artwork_url:
            enhanced["entity_picture"] = artwork_url
            enhanced["cover_url"] = artwork_url
            _LOGGER.info(
                "[WiiM] %s: Enhanced metadata with artwork from %s.%s: %s",
                self.client.host,
                found_in_source,
                found_in_field,
                artwork_url,
            )
        else:
            _LOGGER.debug("[WiiM] %s: No artwork URL found in any known fields", self.client.host)
            # Log available fields that might contain artwork for debugging
            potential_artwork_fields = {}
            for source_name, source_data in [("metadata", metadata), ("status", status)]:
                for key, value in source_data.items():
                    if any(art_term in key.lower() for art_term in ["cover", "art", "pic", "thumb", "image"]):
                        potential_artwork_fields[f"{source_name}.{key}"] = value

            if potential_artwork_fields:
                _LOGGER.debug(
                    "[WiiM] %s: Found potential artwork fields: %s", self.client.host, potential_artwork_fields
                )

        return enhanced

    def _extract_basic_metadata(self, status: dict) -> dict:
        """Extract basic metadata from player status when getMetaInfo unavailable.

        Enhanced to extract cover art from status fields.
        """
        _LOGGER.debug("[WiiM] %s: Extracting basic metadata from status (getMetaInfo unavailable)", self.client.host)

        metadata = {}
        if status.get("title"):
            metadata["title"] = status["title"]
        if status.get("artist"):
            metadata["artist"] = status["artist"]
        if status.get("album"):
            metadata["album"] = status["album"]

        _LOGGER.debug(
            "[WiiM] %s: Basic metadata extracted: title='%s', artist='%s', album='%s'",
            self.client.host,
            metadata.get("title"),
            metadata.get("artist"),
            metadata.get("album"),
        )

        # Extract cover art from status if available
        artwork_fields = [
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

        artwork_found = False
        for field in artwork_fields:
            if status.get(field):
                metadata["entity_picture"] = status[field]
                metadata["cover_url"] = status[field]
                _LOGGER.info(
                    "[WiiM] %s: Found artwork in basic metadata from status field '%s': %s",
                    self.client.host,
                    field,
                    status[field],
                )
                artwork_found = True
                break

        if not artwork_found:
            _LOGGER.debug("[WiiM] %s: No artwork found in basic metadata extraction", self.client.host)
            # Debug: show what fields are available that might contain artwork
            potential_artwork_fields = {
                k: v
                for k, v in status.items()
                if any(art_term in k.lower() for art_term in ["cover", "art", "pic", "thumb", "image"])
            }
            if potential_artwork_fields:
                _LOGGER.debug(
                    "[WiiM] %s: Available potential artwork fields in status: %s",
                    self.client.host,
                    potential_artwork_fields,
                )

        return metadata

    async def _get_eq_info_defensive(self) -> dict:
        """Get EQ info only if device supports it.

        Enhanced to poll more frequently and extract EQ preset information
        for proper sound mode functionality.
        """
        if self._eq_supported is False:
            # Already know this device doesn't support EQ
            return {}

        try:
            eq_enabled = await self.client.get_eq_status()
            eq_info = {"eq_enabled": eq_enabled}

            # Always try to get EQ data for preset information
            eq_data = await self.client.get_eq()
            if eq_data:
                eq_info.update(eq_data)
                # Extract EQ preset specifically for sound mode functionality
                if "preset" in eq_data:
                    eq_info["eq_preset"] = eq_data["preset"]
                elif "EQ" in eq_data:
                    eq_info["eq_preset"] = eq_data["EQ"]

                _LOGGER.debug("[WiiM] %s: EQ data retrieved: %s", self.client.host, eq_data)

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

    async def _detect_role_from_status_and_slaves(self, status: dict, multiroom: dict, device_info: dict) -> str:
        """Detect device role using proper slaves API call.

        CRITICAL FIX: Group information comes from device_info (getStatusEx), not status (getPlayerStatus).
        We need to consolidate group fields from the proper source.
        """
        _LOGGER.debug("=== ROLE DETECTION START for %s ===", self.client.host)

        # Extract fields for analysis - PRIORITY: device_info over status
        # Group fields come from getStatusEx (device_info), not getPlayerStatus (status)
        group_field = device_info.get("group", status.get("group", "0"))
        master_uuid = device_info.get("master_uuid", status.get("master_uuid"))
        master_ip = device_info.get("master_ip", status.get("master_ip"))
        device_uuid = device_info.get("uuid", status.get("uuid"))
        device_name = (
            device_info.get("DeviceName")
            or device_info.get("device_name")
            or status.get("DeviceName")
            or status.get("device_name", "Unknown")
        )

        slave_count = multiroom.get("slave_count", 0)
        slaves_list = multiroom.get("slaves", [])

        _LOGGER.debug("Role detection inputs for %s:", self.client.host)
        _LOGGER.debug("  - device_name: '%s'", device_name)
        _LOGGER.debug("  - device_uuid: '%s'", device_uuid)
        _LOGGER.debug("  - group_field: '%s' (from device_info/status priority)", group_field)
        _LOGGER.debug("  - slave_count: %s (from multiroom)", slave_count)
        _LOGGER.debug("  - slaves_list: %s (from multiroom)", slaves_list)
        _LOGGER.debug("  - master_uuid: '%s' (from device_info/status priority)", master_uuid)
        _LOGGER.debug("  - master_ip: '%s' (from device_info/status priority)", master_ip)

        # DETECTION LOGIC:
        # 1. Device is MASTER if it has slaves (slave_count > 0)
        # 2. Device is SLAVE if group field > 0 AND has master info
        # 3. Device is SOLO otherwise

        _LOGGER.debug("Applying role detection logic for %s:", self.client.host)

        # Check for MASTER role first
        if slave_count > 0:
            _LOGGER.info(
                "ROLE DETECTION: %s (%s) is MASTER because slave_count=%s > 0",
                self.client.host,
                device_name,
                slave_count,
            )
            _LOGGER.debug("Master %s has %d slaves: %s", self.client.host, slave_count, slaves_list)
            role = "master"

            # SYNC CLIENT STATE: Set client internal state for group operations
            self.client._group_master = self.client.host  # Master points to itself
            self.client._group_slaves = [
                slave.get("ip") for slave in slaves_list if isinstance(slave, dict) and slave.get("ip")
            ]
            _LOGGER.debug(
                "Synchronized client state: master=%s, slaves=%s", self.client._group_master, self.client._group_slaves
            )

        # Check for SLAVE role
        elif group_field != "0":
            if master_uuid or master_ip:
                _LOGGER.info(
                    "ROLE DETECTION: %s (%s) is SLAVE because group='%s' != '0' and has master info (uuid='%s', ip='%s')",
                    self.client.host,
                    device_name,
                    group_field,
                    master_uuid,
                    master_ip,
                )
                role = "slave"

                # SYNC CLIENT STATE: Set client to know it's a slave
                self.client._group_master = master_ip  # Slave points to master IP
                self.client._group_slaves = []  # Slaves don't manage slave lists
                _LOGGER.debug("Synchronized client state: master=%s (slave mode)", self.client._group_master)

            else:
                _LOGGER.warning(
                    "ROLE DETECTION: %s (%s) has group='%s' != '0' but NO master info - treating as SOLO (possible detection issue)",
                    self.client.host,
                    device_name,
                    group_field,
                )
                role = "solo"

                # SYNC CLIENT STATE: Clear client state for solo mode
                self.client._group_master = None
                self.client._group_slaves = []

        # Default to SOLO
        else:
            _LOGGER.info(
                "ROLE DETECTION: %s (%s) is SOLO (group='%s', slave_count=%s, no master info)",
                self.client.host,
                device_name,
                group_field,
                slave_count,
            )
            role = "solo"

            # SYNC CLIENT STATE: Clear client state for solo mode
            self.client._group_master = None
            self.client._group_slaves = []

        _LOGGER.debug("FINAL ROLE for %s (%s): %s", self.client.host, device_name, role.upper())
        _LOGGER.debug("Client is_master property now returns: %s", self.client.is_master)
        _LOGGER.debug("=== ROLE DETECTION END for %s ===", self.client.host)

        return role

    async def _update_speaker_object(self, status: dict) -> None:
        """Update Speaker object if it exists."""
        try:
            from .data import get_wiim_data

            wiim_data = get_wiim_data(self.hass)
            speaker = wiim_data.speakers.get(self.entry.unique_id)

            if speaker:
                # Build data structure for speaker update
                speaker.update_from_coordinator_data(status)

        except Exception as speaker_err:
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
