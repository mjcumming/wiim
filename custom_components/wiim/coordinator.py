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

# Toggle to True if you really need full payloads in the log.
# When False (default) large dicts are truncated to a list of top-level keys
# which is usually enough for troubleshooting without spamming the log.
VERBOSE_DEBUG = False


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
        self._presets_supported: bool | None = None

        # Device state tracking
        self._last_status: dict[str, Any] = {}
        self._consecutive_failures = 0
        self._device_info = None

        # Track device info update timing (every 30-60 seconds)
        self._last_device_info_update = 0.0  # type: ignore[assignment]
        self._device_info_interval = 30

        # Debug: Track update calls
        self._update_count = 0

        # One-time flag for dynamic EQ preset discovery
        self._eq_list_extended: bool = False

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
            if VERBOSE_DEBUG:
                _LOGGER.debug("Player status result for %s: %s", self.client.host, result)
            else:
                _LOGGER.debug("Player status result for %s (keys=%s)", self.client.host, list(result.keys()))
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

        # 0. One-time attempt to fetch the full preset list (EQGetList)
        if not self._eq_list_extended:
            await self._extend_eq_preset_map_once()

        try:
            # Core data - always required
            player_status = await self._get_player_status()
            _LOGGER.debug("Player status result for %s: %s", self.client.host, player_status)

            _LOGGER.debug("Step 2: Getting device info for %s", self.client.host)
            device_info = await self._get_device_info_defensive()
            if VERBOSE_DEBUG:
                _LOGGER.debug("Device info result for %s: %s", self.client.host, device_info)
            else:
                _LOGGER.debug("Device info result for %s (keys=%s)", self.client.host, list(device_info.keys()))

            # --------------------------------------------------------
            # Normalise extra device info from getStatusEx so sensors
            # don\'t have to duplicate parsing logic.  Missing keys are
            # simply left out so downstream code can feature-probe.
            # --------------------------------------------------------
            try:
                from .const import (
                    DSP_VERSION_KEY,
                    FIRMWARE_DATE_KEY,
                    FIRMWARE_KEY,
                    HARDWARE_KEY,
                    LATEST_VERSION_KEY,
                    MCU_VERSION_KEY,
                    PRESET_SLOTS_KEY,
                    PROJECT_KEY,
                    UPDATE_AVAILABLE_KEY,
                    WMRM_VERSION_KEY,
                )

                normalised: dict[str, Any] = {}

                if firmware := device_info.get("firmware"):
                    normalised[FIRMWARE_KEY] = firmware

                # Build / release date
                if build_date := device_info.get("Release") or device_info.get("release"):
                    normalised[FIRMWARE_DATE_KEY] = build_date

                # Hardware & project split
                if hw := device_info.get("hardware"):
                    normalised[HARDWARE_KEY] = hw
                if proj := device_info.get("project"):
                    normalised[PROJECT_KEY] = proj

                # MCU / DSP versions
                if device_info.get("mcu_ver") is not None:
                    normalised[MCU_VERSION_KEY] = str(device_info.get("mcu_ver"))
                if device_info.get("dsp_ver") is not None:
                    normalised[DSP_VERSION_KEY] = str(device_info.get("dsp_ver"))

                # Preset slot count
                if device_info.get("preset_key") is not None:
                    try:
                        normalised[PRESET_SLOTS_KEY] = int(device_info.get("preset_key"))
                    except (TypeError, ValueError):
                        pass

                # WiiM multiroom protocol version
                if wmrm_ver := device_info.get("wmrm_version"):
                    normalised[WMRM_VERSION_KEY] = wmrm_ver

                # Update availability
                update_flag = str(device_info.get("VersionUpdate", "0"))
                normalised[UPDATE_AVAILABLE_KEY] = update_flag == "1"
                if latest := device_info.get("NewVer"):
                    normalised[LATEST_VERSION_KEY] = latest

                # Merge into device_info so both sensors and diagnostics share
                device_info.update(normalised)

            except Exception as norm_err:  # pragma: no cover – non-critical
                _LOGGER.debug("Normalising device_info failed for %s: %s", self.client.host, norm_err)

            # Additional data with defensive programming
            _LOGGER.debug("Step 3: Getting multiroom info for %s", self.client.host)
            multiroom_info = await self._get_multiroom_info_defensive()
            _LOGGER.debug("Multiroom info result for %s%s", self.client.host, f": {multiroom_info}" if VERBOSE_DEBUG else f" (keys={list(multiroom_info.keys())})")

            _LOGGER.debug("Step 4: Getting track metadata for %s", self.client.host)
            track_metadata = await self._get_track_metadata_defensive(player_status)
            _LOGGER.debug("Track metadata result for %s%s", self.client.host, f": {track_metadata}" if VERBOSE_DEBUG else f" (keys={list(track_metadata.keys())})")

            # --------------------------------------------------------
            # Preset list (optional)
            # --------------------------------------------------------
            presets_list: list[dict] = []
            if self._presets_supported is not False:
                try:
                    presets_list = await self.client.get_presets()
                    if presets_list and self._presets_supported is None:
                        self._presets_supported = True
                except WiiMError:
                    if self._presets_supported is None:
                        self._presets_supported = False
                except Exception as pre_err:
                    _LOGGER.debug("get_presets failed for %s: %s", self.client.host, pre_err)

            # --------------------------------------------------------
            # Artwork propagation
            # --------------------------------------------------------
            # Speaker entities look for artwork URL in coordinator.data["status"]
            # (see Speaker.get_media_image_url).  After the recent refactor
            # entity_picture/cover_url moved into the *metadata* payload which
            # broke album-art display.  To restore previous behaviour we now
            # copy any discovered artwork fields into the status dict while
            # keeping the richer metadata payload intact.

            if track_metadata:
                art_url = track_metadata.get("entity_picture") or track_metadata.get("cover_url")
                if art_url:
                    if player_status.get("entity_picture") != art_url:
                        _LOGGER.debug("Propagating artwork URL to status: %s", art_url)
                    player_status["entity_picture"] = art_url
                    player_status.setdefault("cover_url", art_url)

            _LOGGER.debug("Step 5: Getting EQ info for %s", self.client.host)
            eq_info = await self._get_eq_info_defensive()
            _LOGGER.debug("EQ info result for %s%s", self.client.host, f": {eq_info}" if VERBOSE_DEBUG else f" (keys={list(eq_info.keys())})")

            # Detect role using the fetched data
            _LOGGER.debug("Step 6: Detecting role for %s", self.client.host)
            role = await self._detect_role_from_status_and_slaves(player_status, multiroom_info, device_info)
            _LOGGER.debug("Detected role for %s: %s", self.client.host, role)

            # Resolve multiroom source and media info
            _LOGGER.debug("Step 7: Resolving multiroom source and media for %s", self.client.host)
            await self._resolve_multiroom_source_and_media(player_status, track_metadata, role)

            # Prepare polling data for diagnostic sensors
            polling_data = {
                "interval": self.update_interval.total_seconds() if self.update_interval else 0,
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
                "presets": presets_list,
                "role": role,
                "polling": polling_data,
            }

            # Propagate EQ preset info to status for better sound mode detection
            if eq_info.get("eq_preset"):
                data["status"]["eq_preset"] = eq_info["eq_preset"]
                _LOGGER.debug("Propagated EQ preset to status: %s", eq_info["eq_preset"])

            # Inject UUID if missing
            if "uuid" not in device_info and self.entry.unique_id:
                data["device_info"]["uuid"] = self.entry.unique_id
                _LOGGER.debug("Injected UUID from config entry as API did not provide one")

            # Log only top-level keys to keep debug output readable
            _LOGGER.debug("Step 8: Final coordinator data for %s (keys=%s)", self.client.host, list(data.keys()))

            # Update speaker object with comprehensive data
            _LOGGER.debug("Step 9: Updating speaker object for %s", self.client.host)
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
        WiiM devices actually support getMetaInfo and provide cover art successfully.
        """
        _LOGGER.debug("Getting track metadata for %s", self.client.host)

        if self._metadata_supported is False:
            # Already know this device doesn't support getMetaInfo
            _LOGGER.debug("Device %s doesn't support getMetaInfo - using basic metadata", self.client.host)
            return self._extract_basic_metadata(status)

        try:
            _LOGGER.debug("Attempting getMetaInfo for %s", self.client.host)
            metadata_response = await self.client.get_meta_info()
            _LOGGER.debug("getMetaInfo response for %s: %s", self.client.host, metadata_response)

            if metadata_response and metadata_response.get("metaData"):
                metadata = metadata_response["metaData"]
                if self._metadata_supported is None:
                    self._metadata_supported = True
                    _LOGGER.info("getMetaInfo works for %s - full metadata available", self.client.host)

                # Enhance metadata with cover art extraction
                enhanced_metadata = self._enhance_metadata_with_artwork(metadata, status)
                _LOGGER.debug("Enhanced metadata for %s: %s", self.client.host, enhanced_metadata)
                return enhanced_metadata
        except WiiMError as err:
            if self._metadata_supported is None:
                self._metadata_supported = False
                _LOGGER.info("getMetaInfo not supported for %s: %s - using basic metadata", self.client.host, err)

        # Fallback: Extract basic metadata from player status
        _LOGGER.debug("Using basic metadata fallback for %s", self.client.host)
        return self._extract_basic_metadata(status)

    def _enhance_metadata_with_artwork(self, metadata: dict, status: dict) -> dict:
        """Enhance metadata with cover art information from multiple sources.

        WiiM devices support cover art via getMetaInfo and albumArtURI fields.
        """
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
            "image",
            "coverart",
            "cover_art",
            "album_art",
            "artworkUrl",
            "imageUrl",
        ]

        _LOGGER.debug("Looking for artwork in metadata for %s", self.client.host)
        _LOGGER.debug("Metadata fields available: %s", list(metadata.keys()))

        # Check metadata first, then status
        artwork_url = None
        found_field = None

        # Check metadata first
        for field in artwork_fields:
            artwork_url = metadata.get(field)
            if artwork_url and artwork_url != "un_known":  # Filter out invalid URLs
                found_field = f"metadata.{field}"
                break

        # Then check status if not found in metadata
        if not artwork_url:
            for field in artwork_fields:
                artwork_url = status.get(field)
                if artwork_url and artwork_url != "un_known":
                    found_field = f"status.{field}"
                    break

        # Track last artwork URL to reduce repetitive logging
        if not hasattr(self, "_last_artwork_url"):
            self._last_artwork_url = None

        if artwork_url and artwork_url != "un_known":
            enhanced["entity_picture"] = artwork_url
            enhanced["cover_url"] = artwork_url

            # Only log when artwork URL actually changes
            if self._last_artwork_url != artwork_url:
                _LOGGER.info("🎨 Artwork changed for %s (%s): %s", self.client.host, found_field, artwork_url)
                self._last_artwork_url = artwork_url
            else:
                _LOGGER.debug("🎨 Artwork unchanged for %s: %s", self.client.host, artwork_url)
        else:
            if self._last_artwork_url is not None:
                _LOGGER.info("🎨 Artwork removed for %s", self.client.host)
                self._last_artwork_url = None
            else:
                _LOGGER.debug("❌ No valid artwork URL found for %s", self.client.host)

        return enhanced

    def _extract_basic_metadata(self, status: dict) -> dict:
        """Extract basic metadata from player status when getMetaInfo unavailable.

        HA will handle cover art fetching through its own mechanisms.
        """
        _LOGGER.debug("Extracting basic metadata from status for %s", self.client.host)

        metadata = {}
        if status.get("title"):
            metadata["title"] = status["title"]
        if status.get("artist"):
            metadata["artist"] = status["artist"]
        if status.get("album"):
            metadata["album"] = status["album"]

        _LOGGER.debug(
            "Basic metadata extracted for %s: title='%s', artist='%s', album='%s'",
            self.client.host,
            metadata.get("title"),
            metadata.get("artist"),
            metadata.get("album"),
        )

        # Note: Cover art will be handled by Home Assistant's media browser and other mechanisms
        return metadata

    async def _get_eq_info_defensive(self) -> dict:
        """Get EQ info only if device supports it.

        Enhanced to poll more frequently and extract EQ preset information
        for proper sound mode functionality.
        """
        if self._eq_supported is False:
            # Already know this device doesn't support EQ
            _LOGGER.debug("[WiiM] %s: EQ not supported, skipping EQ info collection", self.client.host)
            return {}

        try:
            _LOGGER.debug("[WiiM] %s: Collecting EQ information", self.client.host)

            eq_enabled = await self.client.get_eq_status()
            eq_info = {"eq_enabled": eq_enabled}
            _LOGGER.debug("[WiiM] %s: EQ enabled status: %s", self.client.host, eq_enabled)

            # Always try to get EQ data for preset information
            eq_data = await self.client.get_eq()
            if eq_data:
                # NEW: Detect 'unknown command' responses and treat as unsupported
                if "raw" in eq_data and str(eq_data["raw"]).lower().startswith("unknown command"):
                    _LOGGER.info(
                        "[WiiM] %s: Device responded 'unknown command' to getEQ - disabling EQ polling",
                        self.client.host,
                    )
                    self._eq_supported = False
                    return eq_info

                eq_info.update(eq_data)
                _LOGGER.debug("[WiiM] %s: Raw EQ data: %s", self.client.host, eq_data)

                # Extract EQ preset specifically for sound mode functionality
                # Try multiple field names that different devices might use
                eq_preset = None
                for field_name in ["preset", "EQ", "eq_preset", "eq_mode", "sound_mode"]:
                    if field_name in eq_data and eq_data[field_name] is not None:
                        eq_preset = eq_data[field_name]
                        _LOGGER.debug(
                            "[WiiM] %s: Found EQ preset in field '%s': %s", self.client.host, field_name, eq_preset
                        )
                        break

                if eq_preset is not None:
                    eq_info["eq_preset"] = eq_preset
                    _LOGGER.info("[WiiM] %s: Current EQ preset detected: %s", self.client.host, eq_preset)
                else:
                    _LOGGER.debug("[WiiM] %s: No EQ preset found in EQ data", self.client.host)

            if self._eq_supported is None:
                self._eq_supported = True
                _LOGGER.debug("[WiiM] %s: EQ endpoints work", self.client.host)

            _LOGGER.debug("[WiiM] %s: Final EQ info: %s", self.client.host, eq_info)
            return eq_info

        except WiiMError as err:
            if self._eq_supported is None:
                self._eq_supported = False
                _LOGGER.info("[WiiM] %s: EQ not supported by device: %s", self.client.host, err)
            else:
                _LOGGER.debug("[WiiM] %s: EQ request failed: %s", self.client.host, err)
            return {}

    def _should_update_device_info(self) -> bool:
        """Check if we should update device info (every 30-60 seconds)."""
        now = time.time()
        if now - self._last_device_info_update >= self._device_info_interval:
            self._last_device_info_update = now  # type: ignore[assignment]
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

        Group information comes from device_info (getStatusEx).
        We need to consolidate group fields from the proper source.
        """
        _LOGGER.debug("=== ROLE DETECTION START for %s ===", self.client.host)

        # Get current role for comparison to reduce logging
        current_role = self.get_current_role()

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
        _LOGGER.debug("  - current_role: '%s'", current_role)

        # DETECTION LOGIC:
        # 1. Device is MASTER if it has slaves (slave_count > 0)
        # 2. Device is SLAVE if group field > 0 AND has master info
        # 3. Device is SOLO otherwise

        _LOGGER.debug("Applying role detection logic for %s:", self.client.host)

        # Check for MASTER role first
        if slave_count > 0:
            if current_role != "master":  # Only log when role actually changes
                _LOGGER.info(
                    "ROLE DETECTION: %s (%s) is MASTER because slave_count=%s > 0",
                    self.client.host,
                    device_name,
                    slave_count,
                )
                _LOGGER.debug("Master %s has %d slaves: %s", self.client.host, slave_count, slaves_list)
            else:
                _LOGGER.debug("Role confirmed as MASTER for %s (slave_count=%s)", self.client.host, slave_count)
            role = "master"

            # SYNC CLIENT STATE: Set client internal state for group operations
            self.client._group_master = self.client.host  # Master points to itself
            self.client._group_slaves = [
                slave["ip"] for slave in slaves_list if isinstance(slave, dict) and slave.get("ip") is not None
            ]
            _LOGGER.debug(
                "Synchronized client state: master=%s, slaves=%s", self.client._group_master, self.client._group_slaves
            )

        # Check for SLAVE role
        elif group_field != "0":
            if master_uuid or master_ip:
                if current_role != "slave":  # Only log when role actually changes
                    _LOGGER.info(
                        "ROLE DETECTION: %s (%s) is SLAVE because group='%s' != '0' and has master info (uuid='%s', ip='%s')",
                        self.client.host,
                        device_name,
                        group_field,
                        master_uuid,
                        master_ip,
                    )
                else:
                    _LOGGER.debug("Role confirmed as SLAVE for %s", self.client.host)
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

        # Special case: Some firmwares flag followers with mode=99 but keep group='0'.
        # Treat those as SLAVE so that volume commands are redirected to the master
        elif status.get("mode") == "99":
            # Some firmwares keep mode=99 after a group has been disbanded.  Treat the
            # speaker as a follower *only* when it is actively relaying audio.

            play_state = (status.get("play_status") or status.get("status", "")).lower()

            if play_state == "play":
                if current_role != "slave":
                    _LOGGER.info(
                        "ROLE DETECTION: %s (%s) acting as FOLLOWER (mode=99) – treating as SLAVE for control redirection",
                        self.client.host,
                        device_name,
                    )
                role = "slave"

                # We don't know master IP yet; clear client state so subsequent discovery can fill it
                self.client._group_master = None
                self.client._group_slaves = []
            else:
                # Idle follower → revert to SOLO to avoid mis-classification
                if current_role != "solo":
                    _LOGGER.debug(
                        "ROLE DETECTION: %s (%s) reports mode=99 but is not playing – treating as SOLO",
                        self.client.host,
                        device_name,
                    )
                role = "solo"
                self.client._group_master = None
                self.client._group_slaves = []

        # Default to SOLO
        else:
            if current_role != "solo":  # Only log when role actually changes
                _LOGGER.info(
                    "ROLE DETECTION: %s (%s) is SOLO (group='%s', slave_count=%s, no master info)",
                    self.client.host,
                    device_name,
                    group_field,
                    slave_count,
                )
            else:
                _LOGGER.debug("Role confirmed as SOLO for %s", self.client.host)
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
            from .data import get_speaker_from_config_entry

            # In v2.0.0 simplified architecture, get speaker directly from config entry
            speaker = get_speaker_from_config_entry(self.hass, self.entry)

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

    async def _resolve_multiroom_source_and_media(self, status: dict, metadata: dict, role: str) -> None:
        """Resolve source and media info for multiroom devices.

        Masters: Resolve actual source from multiroom mode
        Slaves: Mirror master's media information
        """
        _LOGGER.debug("=== MULTIROOM SOURCE RESOLUTION START for %s (role: %s) ===", self.client.host, role)

        # Check if this device is in multiroom mode
        if not status.get("_multiroom_mode"):
            _LOGGER.debug("Device %s not in multiroom mode, no source resolution needed", self.client.host)
            return

        if role == "master":
            await self._resolve_master_source(status)
        elif role == "slave":
            await self._mirror_master_media(status, metadata)
        else:
            _LOGGER.debug("Solo device %s in multiroom mode - keeping multiroom source", self.client.host)

        _LOGGER.debug("=== MULTIROOM SOURCE RESOLUTION END for %s ===", self.client.host)

    async def _resolve_master_source(self, status: dict) -> None:
        """Resolve actual source for master device in multiroom.

        Masters in multiroom mode (mode=99) need to show their actual source,
        not "follower". We'll try to determine this from other status fields.
        """
        _LOGGER.debug("Resolving actual source for master %s", self.client.host)

        # Try to get actual source from additional API calls or status fields
        # For now, we'll try some common approaches:

        # Option 1: Check if there's a different mode field or source indicator
        actual_source = None

        # Look for other source indicators in the status
        if status.get("title") and status.get("title") != "Unknown":
            # If we have actual track info, guess source from pattern or default to network
            if "spotify" in str(status.get("title", "")).lower():
                actual_source = "spotify"
            elif status.get("duration", 0) > 0:
                actual_source = "wifi"  # Streaming content
            else:
                actual_source = "network"
        else:
            actual_source = "network"  # Default for masters with no clear source

        status["source"] = actual_source
        _LOGGER.debug("Resolved master %s source: multiroom -> %s", self.client.host, actual_source)

    async def _mirror_master_media(self, status: dict, metadata: dict) -> None:
        """Mirror master's media information for slave device.

        Slaves should show what the master is playing, not their own local state.
        """
        _LOGGER.debug("Mirroring master media info for slave %s", self.client.host)

        # Get the master device's information using simplified architecture
        from .data import find_speaker_by_ip, get_all_speakers

        # Find master by looking at our group state
        master_speaker = None

        # First try to find master using device status master_ip field
        device_status = self.data.get("status", {}) if self.data else {}
        master_ip = device_status.get("master_ip")

        if master_ip:
            # Look for speaker with this IP address
            master_speaker = find_speaker_by_ip(self.hass, master_ip)
            if master_speaker and master_speaker.role == "master":
                _LOGGER.debug("Found master %s by IP %s for slave %s", master_speaker.name, master_ip, self.client.host)
            else:
                master_speaker = None  # IP found but not a master

        # Fallback: search through all masters to find one that has us as a slave
        if not master_speaker:
            all_speakers = get_all_speakers(self.hass)
            for speaker in all_speakers:
                if speaker.role == "master" and self.client.host != speaker.ip_address:
                    # Check if this master has our device as a slave
                    try:
                        slave_ips = [s.ip_address for s in speaker.group_members if hasattr(s, "ip_address")]
                        if self.client.host in slave_ips:
                            master_speaker = speaker
                            _LOGGER.debug(
                                "Found master %s by group membership for slave %s", speaker.name, self.client.host
                            )
                            break
                    except Exception as group_err:
                        _LOGGER.debug("Error checking group members for %s: %s", speaker.name, group_err)
                        continue

        if master_speaker:
            _LOGGER.debug("Successfully found master %s for slave %s", master_speaker.name, self.client.host)

            # Mirror master's media information
            if master_speaker.coordinator.data:
                master_status = master_speaker.coordinator.data.get("status", {})
                master_metadata = master_speaker.coordinator.data.get("metadata", {})

                # Store what we're about to mirror for comparison
                master_source = master_status.get("source")
                master_title = master_status.get("title")
                master_play_status = master_status.get("play_status")

                # Check against last mirrored state to avoid repetitive logging
                if not hasattr(self, "_last_mirrored_state"):
                    self._last_mirrored_state: dict[str, dict[str, str]] = {}

                last_state = self._last_mirrored_state.get(self.client.host, {})
                state_key = f"{master_source}|{master_title}|{master_play_status}"

                should_log = last_state.get("state_key") != state_key

                # Mirror key media fields from master
                media_fields = ["title", "artist", "album", "source", "play_status", "position", "duration"]
                for field in media_fields:
                    if field in master_status:
                        status[field] = master_status[field]

                # Mirror metadata (including cover art)
                for key, value in master_metadata.items():
                    metadata[key] = value

                # Only log media mirroring when state actually changes (first time or when content changes)
                if should_log:
                    _LOGGER.debug(
                        "Slave %s now mirroring master %s media info (source: %s, track: %s)",
                        self.client.host,
                        master_speaker.name,
                        master_source,
                        master_title,
                    )
                    # Update last mirrored state
                    self._last_mirrored_state[self.client.host] = {"state_key": state_key}
                else:
                    _LOGGER.debug(
                        "Slave %s continuing to mirror master %s (no state changes)",
                        self.client.host,
                        master_speaker.name,
                    )
            else:
                _LOGGER.warning("Master %s has no coordinator data to mirror", master_speaker.name)
        else:
            # Rate limit this warning to reduce log spam
            if not hasattr(self, "_last_master_warning_time"):
                self._last_master_warning_time = 0

            import time

            current_time = time.time()
            if current_time - self._last_master_warning_time > 60:
                # If the device itself does not report a master_ip we have *no* way to locate
                # the leader – this is normal for many LinkPlay firmwares that only flag the
                # follower state via ``mode=99``.  In that case just emit a debug message to
                # avoid confusing end-users with a warning that suggests something is wrong.

                if master_ip:
                    _LOGGER.warning(
                        "Could not find master for slave %s (suppressing further warnings for 60s)",
                        self.client.host,
                    )
                else:
                    _LOGGER.debug(
                        "Slave %s is in follower mode (mode=99) but did not report master_ip – unable to locate group leader",
                        self.client.host,
                    )

                self._last_master_warning_time = current_time
            else:
                _LOGGER.debug("Could not find master for slave %s (warning suppressed)", self.client.host)

            # Fallback: just change source from "multiroom" to "follower" for clarity
            status["source"] = "follower"

    # ------------------------------------------------------------------
    # Dynamic EQ preset discovery --------------------------------------
    # ------------------------------------------------------------------

    async def _extend_eq_preset_map_once(self) -> None:
        """Fetch *additional* EQ presets from the device (EQGetList).

        Some WiiM firmwares expose extra presets (e.g. "Latin", "Small Speakers").
        We merge them into EQ_PRESET_MAP exactly once at start-up so they turn
        up in the sound-mode dropdown.  If the endpoint is missing we simply
        mark the attempt as done and move on silently.
        """

        # Guard – only run once per coordinator instance
        if self._eq_list_extended:
            return

        try:
            presets = await self.client.get_eq_presets()
            if not isinstance(presets, list):
                self._eq_list_extended = True
                return

            import re

            from .const import EQ_PRESET_MAP

            def _slug(label: str) -> str:
                slug = label.strip().lower().replace(" ", "_").replace("-", "_")
                # keep only ascii letters/numbers/underscore
                return re.sub(r"[^0-9a-z_]+", "", slug)

            added: list[str] = []
            for label in presets:
                if not isinstance(label, str):
                    continue
                key = _slug(label)
                if key and key not in EQ_PRESET_MAP:
                    EQ_PRESET_MAP[key] = label
                    added.append(label)

            if added:
                _LOGGER.info("[WiiM] %s: Added %d additional EQ presets from EQGetList: %s", self.client.host, len(added), added)
        except WiiMError as err:
            _LOGGER.debug("[WiiM] %s: EQGetList not supported (%s)", self.client.host, err)
        except Exception as err:  # pragma: no cover – safety
            _LOGGER.debug("[WiiM] %s: Unexpected error during EQ list fetch: %s", self.client.host, err)
        finally:
            # Always mark as attempted so we do not retry every poll
            self._eq_list_extended = True
