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
        self.client = client  # Access via self.player.client instead
        self.hass = hass
        self.entry = entry
        self._capabilities = capabilities or {}
        self._polling_strategy = PollingStrategy(self._capabilities) if self._capabilities else PollingStrategy({})
        self._track_detector = TrackChangeDetector()

        # Create Player (primary interface - recommended by guide)
        self.player = Player(client)

        # UPnP client for events and queue management (optional, set up later)
        self.upnp_client: UpnpClient | None = None
        self._upnp_setup_attempted = False

        # Track last check times for conditional fetching
        self._last_device_info_check = 0.0
        self._last_multiroom_check = 0.0
        self._last_metadata_check = 0.0
        self._last_eq_info_check = 0.0
        self._last_audio_output_check = 0.0

    async def _async_update_data(self) -> dict[str, Any]:
        """Update coordinator data - pywiim Player handles state management."""
        try:
            # Refresh player state (updates cache and StateSynchronizer)
            await self.player.refresh()

            # Get current state for adaptive polling (from Player properties)
            role = self.player.role if self.player.group else "solo"
            play_state = self.player.play_state or ""
            is_playing = play_state.lower() in ("play", "playing", "load")

            # Get current time for conditional fetching
            current_time = time.time()

            # Use pywiim's PollingStrategy for conditional fetching
            should_fetch_device_info = self._polling_strategy.should_fetch_device_info(self._last_device_info_check)
            # Force device_info fetch if input_list is missing (needed for source selection)
            if not should_fetch_device_info:
                player_has_input_list = (
                    self.player.device_info
                    and hasattr(self.player.device_info, "input_list")
                    and self.player.device_info.input_list
                )
                if not player_has_input_list:
                    should_fetch_device_info = True
            should_fetch_multiroom = self._polling_strategy.should_fetch_multiroom(
                self._last_multiroom_check, is_playing
            )
            # Check if track changed using track detector
            track_changed = self._track_detector.track_changed(
                self.player.media_title,
                self.player.media_artist,
                self.player.source,
                self.player.media_image_url,  # Passed as 'artwork' parameter
            )
            # Determine if metadata is supported (check capabilities or device model)
            metadata_supported = self._capabilities.get("metadata", None) if self._capabilities else None
            should_fetch_metadata = self._polling_strategy.should_fetch_metadata(
                track_changed,
                metadata_supported,
            )
            # Check if EQ and audio output should be fetched (if supported)
            eq_supported = self._capabilities.get("supports_eq", None) if self._capabilities else None
            should_fetch_eq = (
                self._polling_strategy.should_fetch_eq_info(self._last_eq_info_check, eq_supported, current_time)
                if hasattr(self._polling_strategy, "should_fetch_eq_info")
                else False
            )
            audio_output_supported = (
                self._capabilities.get("supports_audio_output", None) if self._capabilities else None
            )
            should_fetch_audio_output = (
                self._polling_strategy.should_fetch_audio_output(
                    self._last_audio_output_check, audio_output_supported, current_time
                )
                if hasattr(self._polling_strategy, "should_fetch_audio_output")
                else False
            )

            # Parallelize independent API calls to reduce blocking time
            multiroom_info = {}
            eq_info = None
            audio_output = None

            # Create tasks for parallel execution (additional data via player.client)
            tasks = []
            if should_fetch_device_info:
                # Refresh device_info via Player (updates player.device_info)
                tasks.append(("device_info", self.player.get_device_info()))
                self._last_device_info_check = current_time
            if should_fetch_multiroom:
                tasks.append(("multiroom", self.player.client.get_multiroom_status()))
            if should_fetch_eq:
                tasks.append(("eq", self.player.client.get_eq()))
            if should_fetch_audio_output:
                tasks.append(("audio_output", self.player.client.get_audio_output_status()))

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
                            self._last_multiroom_check = current_time
                    elif task_name == "eq":
                        if isinstance(result, Exception):
                            if self.data:
                                eq_info = self.data.get("eq")
                        else:
                            eq_info = result or {}
                            self._last_eq_info_check = current_time
                    elif task_name == "audio_output":
                        if isinstance(result, Exception):
                            if self.data:
                                audio_output = self.data.get("audio_output")
                        else:
                            audio_output = result or {}
                            self._last_audio_output_check = current_time

            # Get role from Player (Player computes it from group)
            role = self.player.role if self.player.group else "solo"

            # Fetch metadata if needed (depends on track_changed, so must be after refresh)
            # Note: pywiim's Player.refresh() should handle updating media_image_url
            # We fetch metadata separately for additional info (audio quality, etc.)
            metadata = {}
            if should_fetch_metadata and track_changed:
                try:
                    metadata_response = await self.player.client.get_meta_info()
                    if metadata_response and metadata_response.get("metaData"):
                        metadata = metadata_response["metaData"]
                    self._last_metadata_check = current_time
                except WiiMError:
                    pass
            else:
                # Preserve existing metadata if not fetching (track hasn't changed)
                if self.data:
                    metadata = self.data.get("metadata", {})

            # Update polling interval using pywiim's PollingStrategy
            optimal_interval = self._polling_strategy.get_optimal_interval(role, is_playing)
            if self.update_interval.total_seconds() != optimal_interval:
                self.update_interval = timedelta(seconds=optimal_interval)

            # Preserve existing EQ and audio_output if not fetched
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

            # Add EQ and audio_output if available
            if eq_info is not None:
                data["eq"] = eq_info
            if audio_output is not None:
                data["audio_output"] = audio_output

            # Preserve existing data
            if self.data:
                for key in ["presets", "bt_pair_status", "bt_history"]:
                    if key not in data and key in self.data:
                        data[key] = self.data[key]

            # Speaker object reads from coordinator.data directly - no update needed

            return data

        except WiiMError as err:
            _LOGGER.warning("Update failed for %s: %s", self.player.client.host, err)
            # Return cached data if available (Player caches state)
            if self.data:
                return self.data
            raise UpdateFailed(f"Failed to communicate with {self.player.client.host}: {err}") from err

    async def async_setup_upnp(self) -> None:
        """Set up UPnP client and Player for queue management and events."""
        if self._upnp_setup_attempted:
            return

        self._upnp_setup_attempted = True

        if not UPNP_AVAILABLE:
            _LOGGER.debug("UPnP support not available in pywiim version (queue management disabled)")
            self.upnp_client = None
            self.player = None
            return

        try:
            # Create UPnP client
            description_url = f"http://{self.player.client.host}:49152/description.xml"
            self.upnp_client = await UpnpClient.create(  # type: ignore[misc]
                self.player.client.host,
                description_url,
            )

            # Recreate Player with UPnP client for queue management and events
            self.player = Player(
                self.player.client,
                upnp_client=self.upnp_client,
            )

            _LOGGER.info(
                "UPnP client initialized and Player updated for %s (queue management and events enabled)",
                self.player.client.host,
            )
        except Exception as err:
            _LOGGER.debug(
                "Failed to set up UPnP client for %s (queue management will be unavailable): %s",
                self.player.client.host,
                err,
            )
            # UPnP is optional - don't fail if it's not available
            self.upnp_client = None

    async def async_force_multiroom_refresh(self) -> None:
        """Force an immediate refresh of player state and multiroom status.

        This is used after join/unjoin operations to ensure the group state
        is updated immediately.
        """
        try:
            # Force refresh of player state first (updates group/role)
            await self.player.refresh()

            # Force multiroom status fetch by resetting the check time
            self._last_multiroom_check = 0.0

            # Fetch multiroom status immediately
            try:
                multiroom_info = await self.player.client.get_multiroom_status()
                self._last_multiroom_check = time.time()

                # Update coordinator data with new multiroom info
                if self.data:
                    # Get current role from player (which should now be updated)
                    role = self.player.role if self.player.group else "solo"

                    # Create updated data dict
                    updated_data = self.data.copy()
                    updated_data["multiroom"] = multiroom_info or {}
                    updated_data["role"] = role

                    # Also update player reference in case it changed
                    updated_data["player"] = self.player

                    # Use async_set_updated_data to properly notify all listeners
                    self.async_set_updated_data(updated_data)
                else:
                    # If no data yet, trigger a full refresh
                    await self.async_request_refresh()
            except Exception as err:
                _LOGGER.warning("Failed to fetch multiroom status after group operation: %s", err)
                # Even if multiroom fetch fails, update role from player
                if self.data:
                    role = self.player.role if self.player.group else "solo"
                    updated_data = self.data.copy()
                    updated_data["role"] = role
                    updated_data["player"] = self.player
                    self.async_set_updated_data(updated_data)

        except Exception as err:
            _LOGGER.warning("Failed to force multiroom refresh: %s", err)
