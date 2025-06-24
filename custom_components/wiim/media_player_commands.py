"""WiiM Media Player Command Methods.

This module handles all media player command functionality including:
- Volume control with optimistic state and debouncing
- Playback control (play/pause/stop/seek/next/previous)
- Source and mode selection (input, EQ, shuffle, repeat)
- Group management (join/leave multiroom groups)
- Media playback (URLs, presets, media types)

Extracted from media_player.py as part of Phase 2 refactor to create focused,
maintainable modules following natural code boundaries.

Following the successful API refactor pattern with logical cohesion over arbitrary size limits.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.media_player import MediaPlayerState, MediaType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.debounce import Debouncer

if TYPE_CHECKING:
    from .data import Speaker
    from .media_controller import MediaPlayerController

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "VolumeCommandsMixin",
    "PlaybackCommandsMixin",
    "SourceCommandsMixin",
    "GroupCommandsMixin",
    "MediaCommandsMixin",
]


class VolumeCommandsMixin:
    """Mixin for volume control commands with optimistic state and debouncing."""

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        # Required attributes from implementing class
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        # 1. Optimistic update for immediate UI feedback
        self._optimistic_volume = volume  # type: ignore[attr-defined]
        self._pending_volume = volume  # type: ignore[attr-defined]
        self.async_write_ha_state()  # type: ignore[attr-defined]

        # ------------------------------------------------------------------
        # For single, infrequent volume changes (typical button click tests or
        # manual user interaction) we can call the API immediately to keep the
        # behaviour simple and deterministic.  When the debouncer has already
        # been created (e.g. because the user is dragging the slider) we fall
        # back to the debounced approach to avoid command-flooding.
        # ------------------------------------------------------------------

        if self._volume_debouncer is None:  # type: ignore[attr-defined]
            # FIRST call → execute immediately, create debouncer for subsequent
            # rapid updates.
            await controller.set_volume(volume)
            await self._async_execute_command_with_immediate_refresh("set_volume")  # type: ignore[attr-defined]

            # Create debouncer for any follow-up rapid changes.
            self._volume_debouncer = Debouncer(  # type: ignore[attr-defined]
                self.hass,  # type: ignore[attr-defined]
                _LOGGER,
                cooldown=0.4,
                immediate=False,
                function=self._send_volume_debounced,
            )

            # Command executed – clear pending marker.
            self._pending_volume = None  # type: ignore[attr-defined]
            return

        # Debouncer already exists → we're in a slider drag scenario, use it.
        await self._volume_debouncer.async_call()  # type: ignore[attr-defined]

    async def _send_volume_debounced(self) -> None:
        """Send the last requested volume to the device (debounced)."""
        if self._pending_volume is None:  # type: ignore[attr-defined]
            return

        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]
        speaker: Speaker = self.speaker  # type: ignore[attr-defined]

        try:
            await controller.set_volume(self._pending_volume)  # type: ignore[attr-defined]

            # Immediate refresh to confirm actual device state
            await self._async_execute_command_with_immediate_refresh("set_volume_debounced")  # type: ignore[attr-defined]

        except HomeAssistantError as err:
            # Record command failure for immediate user feedback
            if hasattr(speaker.coordinator, "record_command_failure"):
                speaker.coordinator.record_command_failure("set_volume", err)

            # Clear optimistic state so UI snaps back gracefully
            self._optimistic_volume = None  # type: ignore[attr-defined]
            self.async_write_ha_state()  # type: ignore[attr-defined]

            # Do NOT re-raise – prevents noisy stack traces & keeps entity alive

        except Exception:
            # Unexpected error – bubble up after clearing optimistic state
            self._optimistic_volume = None  # type: ignore[attr-defined]
            self.async_write_ha_state()  # type: ignore[attr-defined]
            raise

        finally:
            # Reset pending value so next change is fresh
            self._pending_volume = None  # type: ignore[attr-defined]

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        # 1. Optimistic update for immediate UI feedback
        self._optimistic_mute = mute  # type: ignore[attr-defined]
        self.async_write_ha_state()  # type: ignore[attr-defined]

        try:
            # 2. Send command to device
            await controller.set_mute(mute)

            # 3. Immediate refresh for confirmation (don't wait 5 seconds)
            await self._async_execute_command_with_immediate_refresh("set_mute")  # type: ignore[attr-defined]

        except Exception:
            # Clear optimistic state on error so real state shows
            self._optimistic_mute = None  # type: ignore[attr-defined]
            self.async_write_ha_state()  # type: ignore[attr-defined]
            raise

    async def async_volume_up(self) -> None:
        """Increase volume using the configured step size."""
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]
        speaker: Speaker = self.speaker  # type: ignore[attr-defined]

        # Determine step from controller config (fallback to 5 %)
        step = getattr(controller, "_volume_step", 0.05)

        # Base calculation on the value the UI currently shows. If we already
        # applied an optimistic change that hasn't been confirmed yet use that
        # value so consecutive clicks accumulate properly.
        current_volume = (
            self._optimistic_volume  # type: ignore[attr-defined]
            if self._optimistic_volume is not None  # type: ignore[attr-defined]
            else controller.get_volume_level() or 0.0
        )
        new_volume = min(1.0, current_volume + step)

        # 1. Optimistic UI update
        self._optimistic_volume = new_volume  # type: ignore[attr-defined]
        self._pending_volume = new_volume  # type: ignore[attr-defined]
        self.async_write_ha_state()  # type: ignore[attr-defined]

        try:
            # 2. Send absolute volume so we don't double-apply the step
            await controller.set_volume(new_volume)

            # 3. Immediate refresh for confirmation
            await self._async_execute_command_with_immediate_refresh("volume_up")  # type: ignore[attr-defined]

            # Mark command complete
            self._pending_volume = None  # type: ignore[attr-defined]

        except HomeAssistantError as err:
            # Record command failure for immediate user feedback
            if hasattr(speaker.coordinator, "record_command_failure"):
                speaker.coordinator.record_command_failure("volume_up", err)
            self._optimistic_volume = None  # type: ignore[attr-defined]
            self.async_write_ha_state()  # type: ignore[attr-defined]
            # swallow to avoid traceback
        except Exception:
            # Clear optimistic state on error
            self._optimistic_volume = None  # type: ignore[attr-defined]
            self.async_write_ha_state()  # type: ignore[attr-defined]
            raise

    async def async_volume_down(self) -> None:
        """Decrease volume using the configured step size."""
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]
        speaker: Speaker = self.speaker  # type: ignore[attr-defined]

        # Determine step from controller config (fallback to 5 %)
        step = getattr(controller, "_volume_step", 0.05)

        # Base calculation on the value the UI currently shows. If we already
        # applied an optimistic change that hasn't been confirmed yet use that
        # value so consecutive clicks accumulate properly.
        current_volume = (
            self._optimistic_volume  # type: ignore[attr-defined]
            if self._optimistic_volume is not None  # type: ignore[attr-defined]
            else controller.get_volume_level() or 0.0
        )
        new_volume = max(0.0, current_volume - step)

        # 1. Optimistic UI update
        self._optimistic_volume = new_volume  # type: ignore[attr-defined]
        self._pending_volume = new_volume  # type: ignore[attr-defined]
        self.async_write_ha_state()  # type: ignore[attr-defined]

        try:
            # 2. Send absolute volume so we don't double-apply the step
            await controller.set_volume(new_volume)

            # 3. Immediate refresh for confirmation
            await self._async_execute_command_with_immediate_refresh("volume_down")  # type: ignore[attr-defined]

            # Mark command complete
            self._pending_volume = None  # type: ignore[attr-defined]

        except HomeAssistantError as err:
            # Record command failure for immediate user feedback
            if hasattr(speaker.coordinator, "record_command_failure"):
                speaker.coordinator.record_command_failure("volume_down", err)
            self._optimistic_volume = None  # type: ignore[attr-defined]
            self.async_write_ha_state()  # type: ignore[attr-defined]
            # swallow to avoid traceback
        except Exception:
            # Clear optimistic state on error
            self._optimistic_volume = None  # type: ignore[attr-defined]
            self.async_write_ha_state()  # type: ignore[attr-defined]
            raise


class PlaybackCommandsMixin:
    """Mixin for playback control commands with optimistic state."""

    async def async_media_play(self) -> None:
        """Send play command."""
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        # 1. Optimistic update for immediate UI feedback
        self._optimistic_state = MediaPlayerState.PLAYING  # type: ignore[attr-defined]
        self.async_write_ha_state()  # type: ignore[attr-defined]

        try:
            # 2. Send command to device
            await controller.play()

            # 3. Immediate refresh for confirmation (don't wait 5 seconds)
            await self._async_execute_command_with_immediate_refresh("play")  # type: ignore[attr-defined]

        except Exception:
            # Clear optimistic state on error so real state shows
            self._optimistic_state = None  # type: ignore[attr-defined]
            self.async_write_ha_state()  # type: ignore[attr-defined]
            raise

    async def async_media_pause(self) -> None:
        """Send pause command."""
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        # 1. Optimistic update for immediate UI feedback
        self._optimistic_state = MediaPlayerState.PAUSED  # type: ignore[attr-defined]
        self.async_write_ha_state()  # type: ignore[attr-defined]

        try:
            # 2. Send command to device
            await controller.pause()

            # 3. Immediate refresh for confirmation (don't wait 5 seconds)
            await self._async_execute_command_with_immediate_refresh("pause")  # type: ignore[attr-defined]

        except Exception:
            # Clear optimistic state on error so real state shows
            self._optimistic_state = None  # type: ignore[attr-defined]
            self.async_write_ha_state()  # type: ignore[attr-defined]
            raise

    async def async_media_stop(self) -> None:
        """Send stop command."""
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        # 1. Optimistic update for immediate UI feedback
        self._optimistic_state = MediaPlayerState.IDLE  # type: ignore[attr-defined]
        self.async_write_ha_state()  # type: ignore[attr-defined]

        try:
            # 2. Send command to device
            await controller.stop()

            # 3. Immediate refresh for confirmation (don't wait 5 seconds)
            await self._async_execute_command_with_immediate_refresh("stop")  # type: ignore[attr-defined]

        except Exception:
            # Clear optimistic state on error so real state shows
            self._optimistic_state = None  # type: ignore[attr-defined]
            self.async_write_ha_state()  # type: ignore[attr-defined]
            raise

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        try:
            # No predictable optimistic state for track changes
            await controller.next_track()

            # Immediate refresh for fast track info update
            await self._async_execute_command_with_immediate_refresh("next_track")  # type: ignore[attr-defined]

        except Exception:
            raise

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        try:
            # No predictable optimistic state for track changes
            await controller.previous_track()

            # Immediate refresh for fast track info update
            await self._async_execute_command_with_immediate_refresh("previous_track")  # type: ignore[attr-defined]

        except Exception:
            raise

    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        try:
            # No predictable optimistic state for seeking
            await controller.seek(position)

            # Immediate refresh for fast position update
            await self._async_execute_command_with_immediate_refresh("seek")  # type: ignore[attr-defined]

        except Exception:
            raise


class SourceCommandsMixin:
    """Mixin for source and mode selection commands with optimistic state."""

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        # 1. Optimistic update for immediate UI feedback
        self._optimistic_source = source  # type: ignore[attr-defined]
        self.async_write_ha_state()  # type: ignore[attr-defined]

        try:
            # 2. Send command to device
            await controller.select_source(source)

            # 3. Immediate refresh for confirmation (don't wait 5 seconds)
            await self._async_execute_command_with_immediate_refresh("select_source")  # type: ignore[attr-defined]

        except Exception:
            # Clear optimistic state on error so real state shows
            self._optimistic_source = None  # type: ignore[attr-defined]
            self.async_write_ha_state()  # type: ignore[attr-defined]
            raise

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        try:
            # EQ changes don't have direct UI state, just refresh quickly
            await controller.set_eq_preset(sound_mode)

            # Immediate refresh for fast EQ update
            await self._async_execute_command_with_immediate_refresh("select_sound_mode")  # type: ignore[attr-defined]

        except Exception:
            raise

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffle mode."""
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        # 1. Optimistic update for immediate UI feedback
        self._optimistic_shuffle = shuffle  # type: ignore[attr-defined]
        self.async_write_ha_state()  # type: ignore[attr-defined]

        try:
            # 2. Send command to device
            await controller.set_shuffle(shuffle)

            # 3. Immediate refresh for confirmation (don't wait 5 seconds)
            await self._async_execute_command_with_immediate_refresh("set_shuffle")  # type: ignore[attr-defined]

        except Exception:
            # Clear optimistic state on error so real state shows
            self._optimistic_shuffle = None  # type: ignore[attr-defined]
            self.async_write_ha_state()  # type: ignore[attr-defined]
            raise

    async def async_set_repeat(self, repeat: str) -> None:
        """Set repeat mode."""
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        # 1. Optimistic update for immediate UI feedback
        self._optimistic_repeat = repeat  # type: ignore[attr-defined]
        self.async_write_ha_state()  # type: ignore[attr-defined]

        try:
            # 2. Send command to device
            await controller.set_repeat(repeat)

            # 3. Immediate refresh for confirmation (don't wait 5 seconds)
            await self._async_execute_command_with_immediate_refresh("set_repeat")  # type: ignore[attr-defined]

        except Exception:
            # Clear optimistic state on error so real state shows
            self._optimistic_repeat = None  # type: ignore[attr-defined]
            self.async_write_ha_state()  # type: ignore[attr-defined]
            raise


class GroupCommandsMixin:
    """Mixin for group management commands."""

    async def async_join(self, group_members: list[str]) -> None:
        """Join speakers into a group."""
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        try:
            await controller.join_group(group_members)

            # Immediate refresh for fast group state update
            await self._async_execute_command_with_immediate_refresh("join_group")  # type: ignore[attr-defined]

        except Exception:
            raise

    async def async_unjoin(self) -> None:
        """Remove this speaker from any group."""
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        try:
            await controller.leave_group()

            # Immediate refresh for fast group state update
            await self._async_execute_command_with_immediate_refresh("leave_group")  # type: ignore[attr-defined]

        except Exception:
            raise

    async def async_unjoin_player(self) -> None:
        """Remove this player from any group (HA core override).

        Override the core implementation to directly use our async_unjoin method
        instead of running unjoin_player in an executor.
        """
        speaker: Speaker = self.speaker  # type: ignore[attr-defined]
        _LOGGER.debug("async_unjoin_player called for %s", speaker.name)
        await self.async_unjoin()

    async def async_join_players(self, group_members: list[str]) -> None:
        """Join this player with others (HA core override).

        Override the core implementation to directly use our async_join method
        instead of running join_players in an executor.
        """
        speaker: Speaker = self.speaker  # type: ignore[attr-defined]
        _LOGGER.debug("async_join_players called for %s with members: %s", speaker.name, group_members)
        await self.async_join(group_members)


class MediaCommandsMixin:
    """Mixin for media playback commands (URLs, presets, media types)."""

    async def async_play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        """Play a piece of media."""
        _LOGGER.debug("Play media called: type=%s, id=%s", media_type, media_id)
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        try:
            # Preset numbers → play_preset (MCUKeyShortClick)
            if media_type == "preset":
                try:
                    preset_num = int(media_id)
                except ValueError as err:
                    _LOGGER.error("Invalid preset id '%s': %s", media_id, err)
                    raise

                await self.async_play_preset(preset_num)

                # Immediate refresh already handled inside async_play_preset()

            # For URLs or generic audio MIME types, use play_url
            elif media_type in [MediaType.URL, MediaType.MUSIC, "url"] or (
                isinstance(media_type, str) and media_type.startswith("audio/")
            ):
                # If the URL matches a Quick Station entry, use its friendly name
                station_title = await self._async_lookup_quick_station_title(media_id)  # type: ignore[attr-defined]
                if station_title:
                    self._optimistic_media_title = station_title  # type: ignore[attr-defined]
                    self._optimistic_state = MediaPlayerState.PLAYING  # type: ignore[attr-defined]
                    # Show a sensible source immediately (WiFi)
                    self._optimistic_source = "WiFi"  # type: ignore[attr-defined]
                    self.async_write_ha_state()  # type: ignore[attr-defined]
                else:
                    self._optimistic_media_title = None  # type: ignore[attr-defined]
                    self._optimistic_state = MediaPlayerState.PLAYING  # type: ignore[attr-defined]
                    self._optimistic_source = None  # type: ignore[attr-defined]
                    self.async_write_ha_state()  # type: ignore[attr-defined]

                # Always send the URL to the device
                await controller.play_url(media_id)

                # Immediate refresh for fast media update
                await self._async_execute_command_with_immediate_refresh("play_media")  # type: ignore[attr-defined]

            else:
                _LOGGER.warning("Unsupported media type: %s", media_type)
        except Exception as err:
            _LOGGER.error("Failed to play media %s: %s", media_id, err)
            raise

    async def async_play_preset(self, preset: int) -> None:
        """Play a WiiM preset (1-6)."""
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        try:
            await controller.play_preset(preset)

            # Immediate refresh for fast preset update
            await self._async_execute_command_with_immediate_refresh("play_preset")  # type: ignore[attr-defined]

        except Exception:
            raise

    async def async_play_url(self, url: str) -> None:
        """Play a URL."""
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        try:
            await controller.play_url(url)

            # Immediate refresh for fast URL play update
            await self._async_execute_command_with_immediate_refresh("play_url")  # type: ignore[attr-defined]

        except Exception:
            raise
