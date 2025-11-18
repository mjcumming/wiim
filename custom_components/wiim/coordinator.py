"""WiiM coordinator - minimal integration layer using pywiim."""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pywiim import Player, PollingStrategy, TrackChangeDetector, WiiMClient, fetch_parallel
from pywiim.exceptions import WiiMError

# Optional imports for UPnP (may not be available in all pywiim versions)
try:
    from pywiim import UpnpClient

    UPNP_AVAILABLE = True
except ImportError:
    UPNP_AVAILABLE = False
    UpnpClient = None  # type: ignore[assignment, misc]

_LOGGER = logging.getLogger(__name__)


class WiiMCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """WiiM coordinator - minimal glue between pywiim and Home Assistant."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: WiiMClient,
        entry=None,
        capabilities: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"WiiM {client.host}",
            update_interval=timedelta(seconds=5),  # Default, will adapt
        )
        self.hass = hass
        self.entry = entry
        self._capabilities = capabilities or {}
        self._polling_strategy = PollingStrategy(self._capabilities) if self._capabilities else PollingStrategy({})
        self._track_detector = TrackChangeDetector()

        # Create Player (primary interface - recommended by guide)
        self._client = client
        self.client = client
        self.player = Player(self._client)

        # UPnP client for events and queue management (optional, set up later)
        self.upnp_client: UpnpClient | None = None
        self._upnp_setup_attempted = False

        # Track last check times for conditional fetching
        self._last_device_info_check = 0.0
        self._last_multiroom_check = 0.0
        self._last_metadata_check = 0.0
        self._last_eq_info_check = 0.0
        self._last_audio_output_check = 0.0

        # Store last valid metadata for audio quality sensors (persists during track changes)
        self._last_valid_metadata: dict[str, Any] = {}

        # Store EQ presets list (from get_eq_presets())
        self._eq_presets: list[str] | None = None

        metadata_supported = None
        if self._capabilities:
            metadata_supported = self._capabilities.get("supports_metadata")
            if metadata_supported is None:
                metadata_supported = self._capabilities.get("metadata")
        self._metadata_supported: bool | None = metadata_supported

    async def _async_update_data(self) -> dict[str, Any]:
        """Update coordinator data - pywiim Player handles state management."""
        try:
            # Refresh player state (updates cache and StateSynchronizer)
            await self.player.refresh()

            # Get current state for adaptive polling (from Player properties)
            player_any: Any = self.player
            role = self.player.role
            play_state = self.player.play_state or ""
            is_playing = play_state.lower() in ("play", "playing", "load")

            # Get current time for conditional fetching
            now = time.time()

            # Use pywiim's PollingStrategy for conditional fetching
            should_fetch_device_info = self._polling_strategy.should_fetch_device_info(
                self._last_device_info_check,
                now,
            )
            # Force device_info fetch on first load or if input_list is missing (needed for source selection)
            is_first_load = self.data is None
            if not should_fetch_device_info:
                player_has_input_list = (
                    self.player.device_info
                    and hasattr(self.player.device_info, "input_list")
                    and self.player.device_info.input_list
                )
                if is_first_load or not player_has_input_list:
                    should_fetch_device_info = True
                    # Only log if this is unusual (not first load but missing input_list)
                    if not is_first_load and not player_has_input_list:
                        _LOGGER.debug(
                            "Forcing device_info fetch for %s (missing input_list)",
                            self.player.host,
                        )
            should_fetch_multiroom = self._polling_strategy.should_fetch_multiroom(
                self._last_multiroom_check,
                now,
            )
            # Check if track changed using track detector
            track_changed = self._track_detector.track_changed(
                self.player.media_title,
                self.player.media_artist,
                self.player.source,
                self.player.media_image_url,  # Passed as 'artwork' parameter
            )
            # Determine if metadata is supported (check capabilities or device model)
            metadata_supported = None
            if self._capabilities:
                metadata_supported = self._capabilities.get("supports_metadata")
                if metadata_supported is None:
                    metadata_supported = self._capabilities.get("metadata")
            self._metadata_supported = metadata_supported
            should_fetch_metadata = self._polling_strategy.should_fetch_metadata(
                track_changed,
                metadata_supported,
            )
            # Check if EQ and audio output should be fetched (if supported)
            eq_supported = None
            if self._capabilities:
                eq_supported = self._capabilities.get("supports_eq")
                if eq_supported is None:
                    eq_supported = self._capabilities.get("eq_supported")
            should_fetch_eq = (
                self._polling_strategy.should_fetch_eq_info(self._last_eq_info_check, eq_supported, now)
                if hasattr(self._polling_strategy, "should_fetch_eq_info")
                else False
            )
            # Force EQ fetch on first load if EQ is supported (needed for EQ button)
            if not should_fetch_eq and eq_supported and is_first_load:
                should_fetch_eq = True
                _LOGGER.debug(
                    "Forcing EQ info fetch for %s on first load (EQ supported)",
                    self.player.host,
                )
            audio_output_supported = None
            if self._capabilities:
                audio_output_supported = self._capabilities.get("supports_audio_output")
                if audio_output_supported is None:
                    audio_output_supported = self._capabilities.get("audio_output_supported")
            should_fetch_audio_output = (
                self._polling_strategy.should_fetch_audio_output(
                    self._last_audio_output_check, audio_output_supported, now
                )
                if hasattr(self._polling_strategy, "should_fetch_audio_output")
                else False
            )

            # Parallelize independent API calls to reduce blocking time
            # Preserve previous multiroom_info if not fetching this cycle
            multiroom_info = self.data.get("multiroom", {}) if self.data and not should_fetch_multiroom else {}
            eq_info = None
            audio_output = None

            # Create tasks for parallel execution (additional data via player helper methods)
            tasks = []
            if should_fetch_device_info:
                # Refresh device_info via Player (updates player.device_info)
                tasks.append(("device_info", self.player.get_device_info()))
                self._last_device_info_check = now
            if should_fetch_multiroom:
                tasks.append(("multiroom", player_any.get_multiroom_status()))  # pylint: disable=no-member
                self._last_multiroom_check = now
            if should_fetch_eq:
                # Fetch both EQ status and EQ presets list (per HA_INTEGRATION_GUIDE.md)
                tasks.append(("eq", self.player.get_eq()))
                tasks.append(("eq_presets", self.player.get_eq_presets()))
                self._last_eq_info_check = now
            if should_fetch_audio_output:
                tasks.append(("audio_output", player_any.get_audio_output_status()))  # pylint: disable=no-member
                self._last_audio_output_check = now

            # Execute independent calls in parallel using pywiim's fetch_parallel helper
            if tasks:
                results = await fetch_parallel(*[task[1] for task in tasks], return_exceptions=True)
                for (task_name, _), result in zip(tasks, results, strict=True):
                    if task_name == "device_info":
                        # Player.get_device_info() updates player.device_info property
                        # No need to store separately - entities access via player.device_info
                        if isinstance(result, Exception):
                            pass  # Use cached player.device_info if available
                    elif task_name == "multiroom":
                        if isinstance(result, WiiMError):
                            if self.data:
                                multiroom_info = self.data.get("multiroom", {})
                        elif isinstance(result, Exception):
                            if self.data:
                                multiroom_info = self.data.get("multiroom", {})
                        else:
                            multiroom_info = result or {}
                    elif task_name == "eq":
                        if isinstance(result, Exception):
                            if self.data:
                                eq_info = self.data.get("eq")
                        else:
                            eq_info = result or {}
                    elif task_name == "eq_presets":
                        # Store EQ presets list (list[str] of preset names)
                        if isinstance(result, Exception):
                            # Preserve existing EQ presets on error
                            if self.data and self.data.get("eq_presets"):
                                self._eq_presets = self.data.get("eq_presets")
                        elif result is not None:
                            self._eq_presets = result if isinstance(result, list) else []
                    elif task_name == "audio_output":
                        if isinstance(result, Exception):
                            if self.data:
                                audio_output = self.data.get("audio_output")
                        else:
                            audio_output = result or {}

            # Use Player.role (computed from pywiim Player.group) for immediacy after join/unjoin.
            role = self.player.role

            # Fetch metadata if needed (depends on track_changed, so must be after refresh)
            # Note: pywiim's Player.refresh() should handle updating media_image_url
            # We fetch metadata separately for additional info (audio quality, etc.)
            metadata: dict[str, Any] = {}
            if should_fetch_metadata:
                try:
                    metadata_response = await player_any.get_meta_info()  # pylint: disable=no-member
                except WiiMError:
                    if self.data:
                        metadata = self.data.get("metadata", {})
                else:
                    raw_metadata: dict[str, Any] | None = None
                    if isinstance(metadata_response, dict):
                        raw_metadata = metadata_response.get("metaData") or metadata_response
                    if isinstance(raw_metadata, dict) and raw_metadata:
                        # Process metadata to extract audio quality fields
                        metadata = self._process_metadata(raw_metadata)
                        # Store processed metadata for audio quality sensors
                        self._last_valid_metadata = metadata.copy()
                        self._metadata_supported = True
                    elif self.data:
                        metadata = self.data.get("metadata", {})
                    self._last_metadata_check = now
            else:
                # Preserve existing metadata if not fetching (track hasn't changed)
                if self.data:
                    metadata = self.data.get("metadata", {})
            if not metadata and self._last_valid_metadata:
                metadata = self._last_valid_metadata.copy()

            # Update polling interval using pywiim's PollingStrategy
            optimal_interval = self._polling_strategy.get_optimal_interval(role, is_playing)
            current_interval = self.update_interval.total_seconds() if self.update_interval else 5.0
            if current_interval != optimal_interval:
                self.update_interval = timedelta(seconds=optimal_interval)

            # Preserve existing EQ and audio_output if not fetched (needed for UI buttons)
            if eq_info is None and self.data:
                eq_info = self.data.get("eq")
            if audio_output is None and self.data:
                audio_output = self.data.get("audio_output")

            # Extract eq_preset from eq_info if available (more reliable than Player object)
            eq_preset = None
            if isinstance(eq_info, dict):
                eq_preset = eq_info.get("eq_preset") or eq_info.get("eq")
            # Fallback to Player object if not in eq_info
            if eq_preset is None:
                eq_preset = getattr(self.player, "eq_preset", None)

            # Assemble data for Home Assistant (use Player properties)
            data: dict[str, Any] = {
                # Player object for entity access
                "player": self.player,
                # Player state properties (already converted/formatted)
                "volume_level": self.player.volume_level,
                "is_muted": self.player.is_muted,
                "play_state": self.player.play_state,
                "media_title": self.player.media_title,
                "media_artist": self.player.media_artist,
                "media_album": self.player.media_album,
                "media_image_url": self.player.media_image_url,  # pywiim handles this via Player.refresh()
                "media_position": self.player.media_position,
                "media_duration": self.player.media_duration,
                "source": self.player.source,
                # Additional Player properties (from pywiim 0.24+)
                "shuffle": getattr(self.player, "shuffle", None),
                "repeat": getattr(self.player, "repeat", None),
                "eq_preset": eq_preset,  # Use extracted value from eq_info if available
                "wifi_rssi": getattr(self.player, "wifi_rssi", None),
                "role": role,
                # Additional data from conditional fetching
                "multiroom": multiroom_info,
                "metadata": metadata,
            }

            # Add EQ and audio_output if available (always add EQ if we have it, even if empty, to persist data)
            if eq_info is not None:
                data["eq"] = eq_info
            elif self.data and self.data.get("eq") is not None:
                # Preserve existing EQ info even if not fetched this cycle (needed for EQ button)
                data["eq"] = self.data.get("eq")
            if audio_output is not None:
                data["audio_output"] = audio_output

            # Add EQ presets list (from get_eq_presets()) - per HA_INTEGRATION_GUIDE.md
            if hasattr(self, "_eq_presets") and self._eq_presets is not None:
                data["eq_presets"] = self._eq_presets
            elif self.data and self.data.get("eq_presets") is not None:
                # Preserve existing EQ presets even if not fetched this cycle
                data["eq_presets"] = self.data.get("eq_presets")

            # Add available_sources from Player (smart detection) - per HA_INTEGRATION_GUIDE.md
            available_sources = getattr(self.player, "available_sources", None)
            if available_sources is not None:
                # Only log source data if it changed (for troubleshooting)
                if not hasattr(self, "_last_sources") or self._last_sources != available_sources:
                    self._last_sources = available_sources
                    _LOGGER.debug(
                        "Source list changed for %s: %s",
                        self.player.host,
                        available_sources,
                    )
                data["available_sources"] = available_sources
            elif self.data and self.data.get("available_sources") is not None:
                # Preserve existing available_sources even if not available this cycle
                data["available_sources"] = self.data.get("available_sources")

            # Preserve existing data
            if self.data:
                for key in ["presets", "bt_pair_status", "bt_history"]:
                    if key not in data and key in self.data:
                        data[key] = self.data[key]

            # Speaker object reads from coordinator.data directly - no update needed

            return data

        except WiiMError as err:
            _LOGGER.warning("Update failed for %s: %s", self.player.host, err)
            # Return cached data if available (Player caches state)
            if self.data:
                return self.data
            raise UpdateFailed(f"Failed to communicate with {self.player.host}: {err}") from err

    async def async_setup_upnp(self) -> None:
        """Set up UPnP client and Player for queue management and events."""
        if self._upnp_setup_attempted:
            return

        self._upnp_setup_attempted = True

        if not UPNP_AVAILABLE:
            _LOGGER.debug("UPnP support not available in pywiim version (queue management disabled)")
            self.upnp_client = None
            return

        try:
            # Create UPnP client
            description_url = f"http://{self.player.host}:49152/description.xml"
            self.upnp_client = await UpnpClient.create(  # type: ignore[misc]
                self.player.host,
                description_url,
            )

            # Recreate Player with UPnP client for queue management and events
            self.player = Player(
                self._client,
                upnp_client=self.upnp_client,
            )

            _LOGGER.info(
                "UPnP client initialized and Player updated for %s (queue management and events enabled)",
                self.player.host,
            )
        except Exception as err:
            _LOGGER.debug(
                "Failed to set up UPnP client for %s (queue management will be unavailable): %s",
                self.player.host,
                err,
            )
            # UPnP is optional - don't fail if it's not available
            self.upnp_client = None

    def _process_metadata(self, raw_metadata: dict[str, Any]) -> dict[str, Any]:
        """Process raw metadata response to extract audio quality fields.

        The getMetaInfo API returns metadata in various formats depending on the source.
        This method extracts sample_rate, bit_depth, and bit_rate fields.
        """
        processed = raw_metadata.copy() if isinstance(raw_metadata, dict) else {}

        # Extract audio quality fields - they may be in different locations
        # Try common field names and formats
        sample_rate = None
        bit_depth = None
        bit_rate = None

        # Check direct fields first
        if "sample_rate" in processed:
            sample_rate = processed["sample_rate"]
        elif "samplerate" in processed:
            sample_rate = processed["samplerate"]
        elif "sampleRate" in processed:
            sample_rate = processed["sampleRate"]

        if "bit_depth" in processed:
            bit_depth = processed["bit_depth"]
        elif "bitdepth" in processed:
            bit_depth = processed["bitdepth"]
        elif "bitDepth" in processed:
            bit_depth = processed["bitDepth"]

        if "bit_rate" in processed:
            bit_rate = processed["bit_rate"]
        elif "bitrate" in processed:
            bit_rate = processed["bitrate"]
        elif "bitRate" in processed:
            bit_rate = processed["bitRate"]

        # Check nested structures (some APIs nest these fields)
        if not sample_rate and "audio" in processed:
            audio = processed["audio"]
            if isinstance(audio, dict):
                sample_rate = audio.get("sample_rate") or audio.get("samplerate") or audio.get("sampleRate")
                bit_depth = audio.get("bit_depth") or audio.get("bitdepth") or audio.get("bitDepth")
                bit_rate = audio.get("bit_rate") or audio.get("bitrate") or audio.get("bitRate")

        # Convert to integers if they're strings
        if sample_rate is not None:
            try:
                sample_rate = int(sample_rate)
            except (ValueError, TypeError):
                sample_rate = None

        if bit_depth is not None:
            try:
                bit_depth = int(bit_depth)
            except (ValueError, TypeError):
                bit_depth = None

        if bit_rate is not None:
            try:
                bit_rate = int(bit_rate)
            except (ValueError, TypeError):
                bit_rate = None

        # Store extracted fields in processed metadata
        if sample_rate is not None:
            processed["sample_rate"] = sample_rate
        if bit_depth is not None:
            processed["bit_depth"] = bit_depth
        if bit_rate is not None:
            processed["bit_rate"] = bit_rate

        return processed

    async def async_force_multiroom_refresh(self) -> None:
        """Force an immediate refresh of player state and multiroom status.

        This is used after join/unjoin operations to ensure the group state
        is updated immediately. Player.refresh() updates player.group and player.role.
        """
        try:
            # Force refresh of player state (updates group/role) - per HA_INTEGRATION_GUIDE.md
            await self.player.refresh()

            # Trigger coordinator update to propagate changes
            await self.async_request_refresh()

        except Exception as err:
            _LOGGER.warning("Failed to force multiroom refresh: %s", err)
