"""WiiM Media Controller - Core Module.

This module provides the main controller class and core functionality including:
- Volume control with master/slave coordination
- Playback control with group awareness
- Source selection with EQ and mode management
- Core controller initialization and state management

Extracted from media_controller.py as part of Phase 2 refactor to create focused,
maintainable modules following natural code boundaries.

Following the successful API refactor pattern with logical cohesion over arbitrary size limits.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.media_player import MediaPlayerState
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_VOLUME_STEP,
    DEFAULT_VOLUME_STEP,
    EQ_PRESET_MAP,
)

if TYPE_CHECKING:
    from .data import Speaker

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "MediaControllerCoreMixin",
]


class MediaControllerCoreMixin:
    """Core controller functionality for volume, playback, and source management."""

    def __init__(self, speaker: Speaker) -> None:
        """Initialize the media player controller core."""
        self.speaker = speaker
        self.hass = speaker.hass
        self._logger = logging.getLogger(f"{__name__}.{speaker.name}")

        # Get volume step from integration config or use default

        config_volume_step = speaker.coordinator.config_entry.options.get(CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP)

        # If the user provided a percentage (e.g. 5 → 5 %), convert to 0-1 range.
        # If the value already looks like a fraction (≤ 1.0) keep it as-is.
        if config_volume_step is None:
            self._volume_step = DEFAULT_VOLUME_STEP
        elif isinstance(config_volume_step, int | float) and config_volume_step > 1:
            self._volume_step = float(config_volume_step) / 100.0
        else:
            # Already in 0-1 range
            self._volume_step = float(config_volume_step)

        # Internal trackers to avoid noisy duplicate logs on every property poll
        self._last_sound_mode: str | None = None
        self._last_shuffle_state: bool | None = None
        self._last_repeat_mode: str | None = None

    # ===== VOLUME CONTROL =====

    async def set_volume(self, volume: float) -> None:
        """Set volume with master/slave logic.

        Args:
            volume: Volume level 0.0-1.0

        Raises:
            HomeAssistantError: If volume setting fails
        """
        try:
            # Send volume directly to *this* device regardless of role.
            # Group-level aggregation is handled by the group-volume entity.
            await self.speaker.coordinator.client.set_volume(volume)

        except Exception as err:
            self._logger.error("Failed to set volume to %.2f: %s", volume, err)
            raise HomeAssistantError(
                f"Failed to set volume to {int(volume * 100)}% on {self.speaker.name}: {err}"
            ) from err

    async def set_mute(self, mute: bool) -> None:
        """Set mute with master/slave logic.

        Args:
            mute: True to mute, False to unmute

        Raises:
            HomeAssistantError: If mute setting fails
        """
        try:
            # Send mute directly to *this* device regardless of role.
            # Group-level mute operations are handled by the group coordinator entity.
            await self.speaker.coordinator.client.set_mute(mute)

        except Exception as err:
            self._logger.error("Failed to set mute to %s: %s", mute, err)
            raise HomeAssistantError(f"Failed to set mute: {err}") from err

    async def volume_up(self, step: float | None = None) -> None:
        """Volume up with configurable step.

        Args:
            step: Volume step (0.0-1.0), uses configured default if None
        """
        current_volume = self.get_volume_level()
        if current_volume is None:
            self._logger.warning("Cannot increase volume - current volume unknown")
            return

        step = step or self._volume_step
        # Fallback to 5% if volume step is 0.00 (configuration issue)
        if step == 0.0:
            step = 0.05
            self._logger.warning("Volume step was 0.00, using fallback of 5%%")

        new_volume = min(1.0, current_volume + step)

        await self.set_volume(new_volume)

    async def volume_down(self, step: float | None = None) -> None:
        """Volume down with configurable step.

        Args:
            step: Volume step (0.0-1.0), uses configured default if None
        """
        current_volume = self.get_volume_level()
        if current_volume is None:
            self._logger.warning("Cannot decrease volume - current volume unknown")
            return

        step = step or self._volume_step
        # Fallback to 5% if volume step is 0.00 (configuration issue)
        if step == 0.0:
            step = 0.05
            self._logger.warning("Volume step was 0.00, using fallback of 5%%")

        new_volume = max(0.0, current_volume - step)

        await self.set_volume(new_volume)

    def get_volume_level(self) -> float | None:
        """Get effective volume (master/slave aware).

        Returns:
            Volume level 0.0-1.0, or None if unknown
        """
        return self.speaker.get_volume_level()

    def is_volume_muted(self) -> bool | None:
        """Get effective mute state (master/slave aware).

        Returns:
            True if muted, False if not muted, None if unknown
        """
        return self.speaker.is_volume_muted()

    # ===== PLAYBACK CONTROL =====

    async def play(self) -> None:
        """Start playback (master/slave aware)."""
        try:
            self._logger.debug(
                "Starting playback for %s (role=%s)",
                self.speaker.name,
                self.speaker.role,
            )

            # Implement master/slave logic - slaves should control master
            if self.speaker.role == "slave" and self.speaker.coordinator_speaker:
                target_speaker = self.speaker.coordinator_speaker
                self._logger.debug(
                    "Slave redirecting to master %s at %s",
                    target_speaker.name,
                    target_speaker.ip_address,
                )
                await target_speaker.coordinator.client.play()
            else:
                self._logger.debug(
                    "Sending play to %s at %s",
                    self.speaker.name,
                    self.speaker.ip_address,
                )
                await self.speaker.coordinator.client.play()

        except Exception as err:
            self._logger.error("Failed to start playback: %s", err)
            raise HomeAssistantError(f"Failed to play: {err}") from err

    async def pause(self) -> None:
        """Pause playback (master/slave aware)."""
        try:
            self._logger.debug(
                "Pausing playback for %s (role=%s)",
                self.speaker.name,
                self.speaker.role,
            )

            # Implement master/slave logic - slaves should control master
            if self.speaker.role == "slave" and self.speaker.coordinator_speaker:
                target_speaker = self.speaker.coordinator_speaker
                self._logger.debug(
                    "Slave redirecting pause to master %s at %s",
                    target_speaker.name,
                    target_speaker.ip_address,
                )
                await target_speaker.coordinator.client.pause()
            else:
                self._logger.debug(
                    "Sending pause to %s at %s",
                    self.speaker.name,
                    self.speaker.ip_address,
                )
                await self.speaker.coordinator.client.pause()

        except Exception as err:
            self._logger.error("Failed to pause playback: %s", err)
            raise HomeAssistantError(f"Failed to pause: {err}") from err

    async def stop(self) -> None:
        """Stop playback."""
        try:
            # Check if current source is Bluetooth - use pause instead of stop
            current_source = self.speaker.get_current_source()
            if current_source and current_source.lower() in ["bluetooth", "bt"]:
                self._logger.debug(
                    "Bluetooth source detected - using pause instead of stop for %s",
                    self.speaker.name,
                )
                # Use pause for Bluetooth sources since stop is not supported
                await self.pause()
                return

            # Implement master/slave logic - slaves should control master
            if self.speaker.role == "slave" and self.speaker.coordinator_speaker:
                await self.speaker.coordinator_speaker.coordinator.client.stop()
            else:
                await self.speaker.coordinator.client.stop()

        except Exception as err:
            self._logger.error("Failed to stop playback: %s", err)
            raise HomeAssistantError(f"Failed to stop: {err}") from err

    async def next_track(self) -> None:
        """Next track (master/slave aware)."""
        try:
            # Implement master/slave logic - slaves should control master
            if self.speaker.role == "slave" and self.speaker.coordinator_speaker:
                await self.speaker.coordinator_speaker.coordinator.client.next_track()
            else:
                await self.speaker.coordinator.client.next_track()

        except Exception as err:
            self._logger.error("Failed to skip to next track: %s", err)
            raise HomeAssistantError(f"Failed to skip to next track: {err}") from err

    async def previous_track(self) -> None:
        """Previous track (master/slave aware)."""
        try:
            # Implement master/slave logic - slaves should control master
            if self.speaker.role == "slave" and self.speaker.coordinator_speaker:
                await self.speaker.coordinator_speaker.coordinator.client.previous_track()
            else:
                await self.speaker.coordinator.client.previous_track()

        except Exception as err:
            self._logger.error("Failed to skip to previous track: %s", err)
            raise HomeAssistantError(f"Failed to skip to previous track: {err}") from err

    async def seek(self, position: float) -> None:
        """Seek to position.

        Args:
            position: Position in seconds
        """
        try:
            self._logger.debug("Seeking to position %.1f for %s", position, self.speaker.name)

            await self.speaker.coordinator.client.seek(int(position))

        except Exception as err:
            self._logger.error("Failed to seek to position %.1f: %s", position, err)
            raise HomeAssistantError(f"Failed to seek: {err}") from err

    def get_playback_state(self) -> MediaPlayerState:
        """Get current playback state."""
        return self.speaker.get_playback_state()

    # ===== SOURCE & AUDIO CONTROL =====

    async def select_source(self, source: str) -> None:
        """Select source, handle slave group leaving.

        Args:
            source: Source name to select
        """
        try:
            self._logger.debug("Selecting source '%s' for %s", source, self.speaker.name)

            # Map friendly source names to WiiM source IDs
            from .const import SOURCE_MAP

            # Try to find the internal source ID for the friendly name
            # Normalize both source and friendly_name for comparison (strip whitespace, lowercase)
            source_normalized = source.strip().lower()
            wiim_source = None
            for internal_id, friendly_name in SOURCE_MAP.items():
                friendly_normalized = friendly_name.strip().lower()
                if source == friendly_name or source_normalized == friendly_normalized:
                    wiim_source = internal_id
                    self._logger.debug(
                        "Found source mapping: '%s' -> '%s' (internal_id: '%s')",
                        source,
                        friendly_name,
                        internal_id,
                    )
                    break

            # If no mapping found, try to convert friendly name format to internal ID format
            # Convert spaces to underscores and lowercase (e.g., "Line In" -> "line_in")
            if wiim_source is None:
                # First check if it's already an internal ID (has underscore or is lowercase single word)
                if "_" in source or (source.islower() and " " not in source):
                    wiim_source = source.lower()
                    self._logger.debug("Source '%s' appears to be internal ID, using as-is: '%s'", source, wiim_source)
                else:
                    # Convert friendly name format to internal ID format
                    # "Line In" -> "line_in", "Line In 2" -> "line_in_2"
                    wiim_source = source.lower().replace(" ", "_")
                    self._logger.debug(
                        "No mapping found for '%s', converted to internal format: '%s'", source, wiim_source
                    )

            self._logger.info("Mapped source '%s' to WiiM source '%s' for %s", source, wiim_source, self.speaker.name)

            # Implement slave group leaving logic - slaves should leave group when changing source
            if self.speaker.role == "slave" and self.speaker.coordinator_speaker:
                self._logger.debug("Slave speaker leaving group before changing source")
                try:
                    await self.speaker.async_leave_group()
                except Exception as leave_err:
                    self._logger.warning("Failed to leave group before source change: %s", leave_err)
                    # Continue with source change anyway

            await self.speaker.coordinator.client.set_source(wiim_source)

        except Exception as err:
            self._logger.error("Failed to select source '%s': %s", source, err)
            raise HomeAssistantError(f"Failed to select source '{source}' on {self.speaker.name}: {err}") from err

    async def set_eq_preset(self, preset: str) -> None:
        """Set EQ preset.

        Args:
            preset: EQ preset name (either internal key or display name)
        """
        try:
            # Handle both internal keys and display names
            preset_key = None

            # First, try direct key lookup (e.g., "bassreducer")
            if preset in EQ_PRESET_MAP:
                preset_key = preset
            else:
                # Try reverse lookup for display names (e.g., "Bass Reducer")
                for key, display_name in EQ_PRESET_MAP.items():
                    if preset == display_name or preset.lower() == display_name.lower():
                        preset_key = key
                        break

            if preset_key is None:
                available_keys = list(EQ_PRESET_MAP.keys())
                available_names = list(EQ_PRESET_MAP.values())
                raise ValueError(
                    f"Unknown EQ preset '{preset}' on {self.speaker.name}. "
                    f"Available keys: {available_keys}. "
                    f"Available names: {available_names}"
                )

            # The API client expects the internal key, not the display name
            await self.speaker.coordinator.client.set_eq_preset(preset_key)

        except Exception as err:
            self._logger.error("Failed to set EQ preset '%s': %s", preset, err)
            raise HomeAssistantError(f"Failed to set EQ preset '{preset}' on {self.speaker.name}: {err}") from err

    async def select_output_mode(self, output_mode: str) -> None:
        """Select hardware output mode.

        Args:
            output_mode: Output mode to select (Line Out, Optical Out, Coax Out, Bluetooth Out)
        """
        try:
            self._logger.info(
                "WiiM Media Controller: Selecting output mode '%s' for %s",
                output_mode,
                self.speaker.name,
            )

            # Map friendly output mode names to API values
            from .const import AUDIO_OUTPUT_MODES

            # Find the API value for the output mode
            api_value = None
            for api_val, friendly_name in AUDIO_OUTPUT_MODES.items():
                if output_mode == friendly_name or output_mode.lower() == friendly_name.lower():
                    api_value = api_val
                    break

            if api_value is None:
                raise ValueError(
                    f"Invalid output mode: {output_mode}. Valid modes: {list(AUDIO_OUTPUT_MODES.values())}"
                )

            self._logger.info(
                "WiiM Media Controller: Mapped output mode '%s' to API value '%s'",
                output_mode,
                api_value,
            )

            await self.speaker.coordinator.client.set_audio_output_hardware_mode(int(api_value))
            self._logger.info(
                "WiiM Media Controller: Successfully sent API command setAudioOutputHardwareMode:%s",
                api_value,
            )

        except Exception as err:
            self._logger.error("Failed to select output mode '%s': %s", output_mode, err)
            raise HomeAssistantError(
                f"Failed to select output mode '{output_mode}' on {self.speaker.name}: {err}"
            ) from err

    async def set_shuffle(self, shuffle: bool) -> None:
        """Set shuffle mode using WiiM's loopmode command.

        Args:
            shuffle: True to enable shuffle, False to disable
        """
        try:
            # Check current source - Airplay sources may not support shuffle control
            current_source = self.get_current_source()
            if current_source and "airplay" in current_source.lower():
                self._logger.warning(
                    "Shuffle control may not work with Airplay source '%s' - "
                    "playback is controlled by the source device (iPhone/Mac)",
                    current_source,
                )

            # Get current repeat state to preserve it
            current_repeat = self.get_repeat_mode()

            # Map to loopmode values: 0=normal, 1=repeat_one, 2=repeat_all, 4=shuffle, 5=shuffle+repeat_one, 6=shuffle+repeat_all
            if shuffle:
                if current_repeat == "one":
                    loop_mode = 5  # shuffle + repeat_one
                elif current_repeat == "all":
                    loop_mode = 6  # shuffle + repeat_all
                else:
                    loop_mode = 4  # shuffle only
            else:
                if current_repeat == "one":
                    loop_mode = 1  # repeat_one
                elif current_repeat == "all":
                    loop_mode = 2  # repeat_all
                else:
                    loop_mode = 0  # normal

            await self.speaker.coordinator.client.set_loop_mode(loop_mode)
            self._logger.debug("Shuffle command sent: loopmode=%s", loop_mode)

        except Exception as err:
            self._logger.error("Failed to set shuffle to %s: %s", shuffle, err)
            raise HomeAssistantError(f"Failed to set shuffle: {err}") from err

    async def set_repeat(self, repeat: str) -> None:
        """Set repeat mode using WiiM's loopmode command.

        Args:
            repeat: Repeat mode - "off", "one", "all"
        """
        try:
            # Check current source - Airplay sources may not support repeat control
            current_source = self.get_current_source()
            if current_source and "airplay" in current_source.lower():
                self._logger.warning(
                    "Repeat control may not work with Airplay source '%s' - "
                    "playback is controlled by the source device (iPhone/Mac)",
                    current_source,
                )

            # Get current shuffle state to preserve it
            current_shuffle = self.get_shuffle_state()

            # Map to loopmode values: 0=normal, 1=repeat_one, 2=repeat_all, 4=shuffle, 5=shuffle+repeat_one, 6=shuffle+repeat_all
            if current_shuffle:
                if repeat == "one":
                    loop_mode = 5  # shuffle + repeat_one
                elif repeat == "all":
                    loop_mode = 6  # shuffle + repeat_all
                else:
                    loop_mode = 4  # shuffle only
            else:
                if repeat == "one":
                    loop_mode = 1  # repeat_one
                elif repeat == "all":
                    loop_mode = 2  # repeat_all
                else:
                    loop_mode = 0  # normal

            await self.speaker.coordinator.client.set_loop_mode(loop_mode)
            self._logger.debug("Repeat command sent: loopmode=%s", loop_mode)

        except Exception as err:
            self._logger.error("Failed to set repeat to '%s': %s", repeat, err)
            raise HomeAssistantError(f"Failed to set repeat: {err}") from err

    def get_source_list(self) -> list[str]:
        """Get sources (master/slave aware).

        Uses API-provided input_list from getStatusEx if available,
        otherwise falls back to hardcoded SELECTABLE_SOURCES list.
        """
        try:
            from .const import SELECTABLE_SOURCES, SOURCE_MAP

            # Try to use API-provided input list first (from getStatusEx)
            if hasattr(self.speaker, "input_list") and self.speaker.input_list:
                api_sources = self.speaker.input_list
                self._logger.debug(
                    "Using API-provided input_list for %s: %s",
                    self.speaker.name,
                    api_sources,
                )

                # Map API source names to friendly display names
                mapped_sources = []
                for api_source in api_sources:
                    # Convert API name to friendly name using SOURCE_MAP
                    friendly_name = SOURCE_MAP.get(
                        api_source.lower(),
                        api_source.title(),  # Fallback: capitalize first letter
                    )
                    # Only include if it's a selectable source (not status-only)
                    if friendly_name not in ["Idle", "Multiroom", "Follower", "Following", "Network"]:
                        mapped_sources.append(friendly_name)

                # Remove duplicates while preserving order
                seen = set()
                unique_sources = []
                for source in mapped_sources:
                    if source not in seen:
                        seen.add(source)
                        unique_sources.append(source)

                return unique_sources

            # Fallback to hardcoded list
            sources = SELECTABLE_SOURCES.copy()

            # Filter device-specific sources
            # Phono input is only available on WiiM Ultra
            model_lower = (self.speaker.model or "").lower()
            if "ultra" not in model_lower:
                sources = [s for s in sources if s != "Phono"]

            return sources
        except Exception as err:
            self._logger.error("Failed to get source list: %s", err)
            return ["WiFi", "Bluetooth", "Line In", "Optical"]  # Basic fallback

    def get_current_source(self) -> str | None:
        """Get current source (master/slave aware)."""
        try:
            # Get the internal source from speaker
            internal_source = self.speaker.get_current_source()
            if not internal_source:
                return None

            # Handle dynamic slave sources like "Following [Master Name]"
            if internal_source.startswith("Following "):
                return internal_source  # Return as-is for slave sources

            # Map other internal sources to friendly names
            from .const import SOURCE_MAP

            return SOURCE_MAP.get(internal_source.lower(), internal_source)

        except Exception as err:
            self._logger.error("Failed to get current source: %s", err)
            return None

    def get_shuffle_state(self) -> bool | None:
        """Get shuffle state."""
        try:
            shuffle_state = self.speaker.get_shuffle_state()

            if shuffle_state != self._last_shuffle_state:
                self._logger.debug(
                    "Shuffle state changed: %s → %s for %s",
                    self._last_shuffle_state,
                    shuffle_state,
                    self.speaker.name,
                )
                self._last_shuffle_state = shuffle_state

            return shuffle_state
        except Exception as err:
            self._logger.error("Error getting shuffle state: %s", err)
            return None

    def get_repeat_mode(self) -> str | None:
        """Get repeat mode."""
        try:
            repeat_mode = self.speaker.get_repeat_mode()

            # Log only on change
            if repeat_mode != self._last_repeat_mode:
                self._logger.debug(
                    "Repeat mode changed: '%s' → '%s' for %s",
                    self._last_repeat_mode,
                    repeat_mode,
                    self.speaker.name,
                )
                self._last_repeat_mode = repeat_mode

            return repeat_mode
        except Exception as err:
            self._logger.error("Error getting repeat mode: %s", err)
            return None

    def get_sound_mode_list(self) -> list[str]:
        """Get available EQ presets (capitalized display names)."""
        return list(EQ_PRESET_MAP.values())  # Return display names: ["Flat", "Acoustic", "Bass"]

    def get_sound_mode(self) -> str | None:
        """Get current EQ preset."""
        try:
            sound_mode = self.speaker.get_sound_mode()

            if sound_mode != self._last_sound_mode:
                self._logger.debug("Detected sound mode: '%s' for %s", sound_mode, self.speaker.name)
                self._last_sound_mode = sound_mode

            return sound_mode
        except Exception as err:
            self._logger.error("Error getting sound mode: %s", err)
            return None
