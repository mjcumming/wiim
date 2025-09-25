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

    def volume_up(self) -> None:
        """Increase volume (sync wrapper)."""
        self.hass.async_create_task(self.async_volume_up())  # type: ignore[attr-defined]

    def volume_down(self) -> None:
        """Decrease volume (sync wrapper)."""
        self.hass.async_create_task(self.async_volume_down())  # type: ignore[attr-defined]

    def mute_volume(self, mute: bool) -> None:
        """Mute the volume (sync wrapper)."""
        self.hass.async_create_task(self.async_mute_volume(mute))  # type: ignore[attr-defined]

    def set_volume_level(self, volume: float) -> None:
        """Set volume level (sync wrapper)."""
        self.hass.async_create_task(self.async_set_volume_level(volume))  # type: ignore[attr-defined]

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        # Required attributes from implementing class
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        _LOGGER.debug("Setting volume to %.2f for %s", volume, self.speaker.name)  # type: ignore[attr-defined]

        # 1. Optimistic update for immediate UI feedback
        self._optimistic_volume = volume  # type: ignore[attr-defined]
        self._pending_volume = volume  # type: ignore[attr-defined]
        self.async_write_ha_state()  # type: ignore[attr-defined]

        try:
            if hasattr(self, "_volume_debouncer") and self._volume_debouncer is not None:  # type: ignore[attr-defined]
                # Use the debouncer – command will be sent after cooldown
                # _pending_volume already set above; do NOT clear it here!
                await self._volume_debouncer.async_call()  # type: ignore[attr-defined]
            else:
                # Debouncer not available (shouldn’t happen) – send immediately
                await controller.set_volume(volume)
                # Command sent → clear the pending flag
                self._pending_volume = None  # type: ignore[attr-defined]

            _LOGGER.debug("Volume set command completed successfully")

            # 3. Let adaptive polling handle sync (no immediate refresh needed)

        except Exception:
            # Clear optimistic state on error
            self._optimistic_volume = None  # type: ignore[attr-defined]
            self._pending_volume = None  # type: ignore[attr-defined]
            self.async_write_ha_state()  # type: ignore[attr-defined]
            raise

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        # 1. Optimistic update for immediate UI feedback
        self._optimistic_mute = mute  # type: ignore[attr-defined]
        self.async_write_ha_state()  # type: ignore[attr-defined]

        try:
            # 2. Send command to device
            await controller.set_mute(mute)

            # 3. Let adaptive polling handle sync (no immediate refresh needed)

        except Exception:
            # Clear optimistic state on error so real state shows
            self._optimistic_mute = None  # type: ignore[attr-defined]
            self.async_write_ha_state()  # type: ignore[attr-defined]
            raise

    async def async_volume_up(self) -> None:
        """Increase volume using debounced step updates."""
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        # Determine step (use controller config, 5 % fallback)
        step = getattr(controller, "_volume_step", 0.05) or 0.05

        current = (
            self._optimistic_volume  # type: ignore[attr-defined]
            if self._optimistic_volume is not None  # type: ignore[attr-defined]
            else controller.get_volume_level() or 0.0
        )
        new_volume = min(1.0, current + step)

        # Optimistic UI update
        self._optimistic_volume = new_volume  # type: ignore[attr-defined]
        self._pending_volume = new_volume  # type: ignore[attr_defined]
        self.async_write_ha_state()  # type: ignore[attr_defined]

        try:
            if hasattr(self, "_volume_debouncer") and self._volume_debouncer is not None:  # type: ignore[attr-defined]
                await self._volume_debouncer.async_call()  # type: ignore[attr_defined]
            else:
                await controller.set_volume(new_volume)
        except Exception as err:
            # Revert optimistic state on error
            self._optimistic_volume = None  # type: ignore[attr_defined]
            self.async_write_ha_state()  # type: ignore[attr_defined]
            _LOGGER.warning("Volume up failed: %s", err)

    async def async_volume_down(self) -> None:
        """Decrease volume using debounced step updates."""
        controller: MediaPlayerController = self.controller  # type: ignore[attr_defined]

        step = getattr(controller, "_volume_step", 0.05) or 0.05

        current = (
            self._optimistic_volume  # type: ignore[attr_defined]
            if self._optimistic_volume is not None  # type: ignore[attr_defined]
            else controller.get_volume_level() or 0.0
        )
        new_volume = max(0.0, current - step)

        self._optimistic_volume = new_volume  # type: ignore[attr_defined]
        self._pending_volume = new_volume  # type: ignore[attr_defined]
        self.async_write_ha_state()  # type: ignore[attr_defined]

        try:
            if hasattr(self, "_volume_debouncer") and self._volume_debouncer is not None:  # type: ignore[attr_defined]
                await self._volume_debouncer.async_call()  # type: ignore[attr_defined]
            else:
                await controller.set_volume(new_volume)
        except Exception as err:
            self._optimistic_volume = None  # type: ignore[attr_defined]
            self.async_write_ha_state()  # type: ignore[attr_defined]
            _LOGGER.warning("Volume down failed: %s", err)


class PlaybackCommandsMixin:
    """Mixin for playback control commands with optimistic state."""

    def media_play(self) -> None:
        """Send play command (sync wrapper)."""
        self.hass.async_create_task(self.async_media_play())  # type: ignore[attr-defined]

    def media_pause(self) -> None:
        """Send pause command (sync wrapper)."""
        self.hass.async_create_task(self.async_media_pause())  # type: ignore[attr-defined]

    def media_stop(self) -> None:
        """Send stop command (sync wrapper)."""
        self.hass.async_create_task(self.async_media_stop())  # type: ignore[attr-defined]

    def media_next_track(self) -> None:
        """Send next track command (sync wrapper)."""
        self.hass.async_create_task(self.async_media_next_track())  # type: ignore[attr-defined]

    def media_previous_track(self) -> None:
        """Send previous track command (sync wrapper)."""
        self.hass.async_create_task(self.async_media_previous_track())  # type: ignore[attr-defined]

    def media_seek(self, position: float) -> None:
        """Send seek command (sync wrapper)."""
        self.hass.async_create_task(self.async_media_seek(position))  # type: ignore[attr-defined]

    async def async_media_play(self) -> None:
        """Send play command."""
        import time

        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        # 1. Optimistic update for immediate UI feedback
        self._optimistic_state = MediaPlayerState.PLAYING  # type: ignore[attr-defined]
        self._optimistic_state_timestamp = time.time()  # type: ignore[attr-defined]
        self.async_write_ha_state()  # type: ignore[attr-defined]

        try:
            # 2. Send command to device
            await controller.play()

            # 3. Let adaptive polling handle sync (no immediate refresh needed)

        except Exception:
            # Clear optimistic state on error so real state shows
            self._optimistic_state = None  # type: ignore[attr-defined]
            self._optimistic_state_timestamp = None  # type: ignore[attr-defined]
            self.async_write_ha_state()  # type: ignore[attr-defined]
            raise

    async def async_media_pause(self) -> None:
        """Send pause command."""
        import time

        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        # 1. Optimistic update for immediate UI feedback
        self._optimistic_state = MediaPlayerState.PAUSED  # type: ignore[attr-defined]
        self._optimistic_state_timestamp = time.time()  # type: ignore[attr-defined]
        self.async_write_ha_state()  # type: ignore[attr-defined]

        try:
            # 2. Send command to device
            await controller.pause()

            # 3. Let adaptive polling handle sync (no immediate refresh needed)

        except Exception:
            # Clear optimistic state on error so real state shows
            self._optimistic_state = None  # type: ignore[attr-defined]
            self._optimistic_state_timestamp = None  # type: ignore[attr-defined]
            self.async_write_ha_state()  # type: ignore[attr-defined]
            raise

    async def async_media_stop(self) -> None:
        """Send stop command."""
        import time

        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        # 1. Optimistic update for immediate UI feedback
        self._optimistic_state = MediaPlayerState.IDLE  # type: ignore[attr-defined]
        self._optimistic_state_timestamp = time.time()  # type: ignore[attr-defined]
        self.async_write_ha_state()  # type: ignore[attr-defined]

        try:
            # 2. Send command to device
            await controller.stop()

            # 3. Let adaptive polling handle sync (no immediate refresh needed)

        except Exception:
            # Clear optimistic state on error so real state shows
            self._optimistic_state = None  # type: ignore[attr-defined]
            self._optimistic_state_timestamp = None  # type: ignore[attr-defined]
            self.async_write_ha_state()  # type: ignore[attr-defined]
            raise

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        try:
            # No predictable optimistic state for track changes
            await controller.next_track()

            # Let adaptive polling handle sync (no immediate refresh needed)

        except Exception:
            raise

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        try:
            # No predictable optimistic state for track changes
            await controller.previous_track()

            # Let adaptive polling handle sync (no immediate refresh needed)

        except Exception:
            raise

    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        try:
            # No predictable optimistic state for seeking
            await controller.seek(position)

            # Let adaptive polling handle sync (no immediate refresh needed)

        except Exception:
            raise


class SourceCommandsMixin:
    """Mixin for source and mode selection commands with optimistic state."""

    def select_source(self, source: str) -> None:
        """Select input source (sync wrapper)."""
        self.hass.async_create_task(self.async_select_source(source))  # type: ignore[attr-defined]

    def select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode (sync wrapper)."""
        self.hass.async_create_task(self.async_select_sound_mode(sound_mode))  # type: ignore[attr-defined]

    def set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffle mode (sync wrapper)."""
        self.hass.async_create_task(self.async_set_shuffle(shuffle))  # type: ignore[attr-defined]

    def set_repeat(self, repeat: str) -> None:
        """Set repeat mode (sync wrapper)."""
        self.hass.async_create_task(self.async_set_repeat(repeat))  # type: ignore[attr-defined]

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        # 1. Optimistic update for immediate UI feedback
        self._optimistic_source = source  # type: ignore[attr-defined]
        self.async_write_ha_state()  # type: ignore[attr-defined]

        try:
            # 2. Send command to device
            await controller.select_source(source)

            # 3. Let adaptive polling handle sync (no immediate refresh needed)

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

            # Let adaptive polling handle sync (no immediate refresh needed)

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

            # 3. Let adaptive polling handle sync (no immediate refresh needed)

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

            # 3. Let adaptive polling handle sync (no immediate refresh needed)

        except Exception:
            # Clear optimistic state on error so real state shows
            self._optimistic_repeat = None  # type: ignore[attr-defined]
            self.async_write_ha_state()  # type: ignore[attr-defined]
            raise


class GroupCommandsMixin:
    """Mixin for group management commands."""

    def join_players(self, group_members: list[str]) -> None:
        """Join speakers into a group (sync wrapper)."""
        self.hass.async_create_task(self.async_join(group_members))  # type: ignore[attr-defined]

    def unjoin_player(self) -> None:
        """Remove this speaker from any group (sync wrapper)."""
        self.hass.async_create_task(self.async_unjoin())  # type: ignore[attr-defined]

    async def async_join(self, group_members: list[str]) -> None:
        """Join speakers into a group with optimistic UI update."""
        import time

        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        # 1. Optimistic UI update for immediate feedback
        if group_members:
            # Joining as master with slaves
            self._optimistic_group_state = "master"  # type: ignore[attr-defined]
            # Building prediction group - merge existing members with new ones
            curr_members = controller.get_group_members()

            for member in group_members:
                if member not in curr_members:
                    curr_members.append(member)

            self._optimistic_group_members = curr_members  # type: ignore[attr-defined]

            if not self._optimistic_group_members or len(self._optimistic_group_members) == 0:
                _LOGGER.warning("async_join_players optimistic group doesnt have any members")
                # Default to old method
                self._optimistic_group_members = group_members  # type: ignore[attr-defined]
        else:
            # Joining as slave (no members means joining existing group)
            self._optimistic_group_state = "slave"  # type: ignore[attr-defined]
            self._optimistic_group_members = []  # type: ignore[attr-defined]

        self._optimistic_group_timestamp = time.time()  # type: ignore[attr-defined]

        self.async_write_ha_state()  # type: ignore[attr-defined]

        try:
            # 2. Send command to device
            await controller.join_group(group_members)

            # 3. Let adaptive polling handle sync (no immediate refresh needed)

        except Exception:
            # Clear optimistic state on error so real state shows
            self._optimistic_group_state = None  # type: ignore[attr-defined]
            self._optimistic_group_members = None  # type: ignore[attr-defined]
            self._optimistic_group_timestamp = None  # type: ignore[attr-defined]
            self.async_write_ha_state()  # type: ignore[attr-defined]
            raise

    async def async_unjoin(self) -> None:
        """Remove this speaker from any group with optimistic UI update."""
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        # 1. Optimistic UI update for immediate feedback
        self._optimistic_group_state = "solo"  # type: ignore[attr-defined]
        self._optimistic_group_members = []  # type: ignore[attr-defined]
        self._optimistic_group_timestamp = None  # type: ignore[attr-defined]
        self.async_write_ha_state()  # type: ignore[attr-defined]

        try:
            # 2. Send command to device
            await controller.leave_group()

            # 3. Let adaptive polling handle sync (no immediate refresh needed)

        except Exception:
            # Clear optimistic state on error so real state shows
            self._optimistic_group_state = None  # type: ignore[attr-defined]
            self._optimistic_group_members = None  # type: ignore[attr-defined]
            self._optimistic_group_timestamp = None  # type: ignore[attr-defined]
            self.async_write_ha_state()  # type: ignore[attr-defined]
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

    def _is_tts_media_source(self, media_id: str) -> bool:
        """Check if this is a TTS-generated media source.

        Args:
            media_id: Media ID to check

        Returns:
            True if this is TTS content
        """
        if not media_id:
            return False

        media_id_lower = media_id.lower()
        return (
            media_id.startswith("media-source://tts/")
            or "tts" in media_id_lower
            or any(
                engine in media_id_lower
                for engine in [
                    "google_cloud",
                    "google_translate",
                    "cloud",
                    "amazon_polly",
                    "espeak",
                    "festival",
                    "picotts",
                    "microsoft",
                    "azure",
                ]
            )
        )

    def _is_audio_media_source(self, play_item) -> bool:
        """Check if a resolved media source item is audio content compatible with WiiM.

        Args:
            play_item: ResolvedMedia item from media_source.async_resolve_media()

        Returns:
            True if item is audio content that WiiM can play
        """
        # Always allow TTS content - it's always audio
        if hasattr(play_item, "url") and self._is_tts_media_source(play_item.url):
            _LOGGER.debug("Detected TTS content, allowing playback")
            return True

        # Check MIME type if available
        if hasattr(play_item, "mime_type") and play_item.mime_type:
            mime_type = play_item.mime_type.lower()
            if mime_type.startswith("audio/"):
                return True

        # Check file extension in URL
        url = getattr(play_item, "url", "")
        if url:
            url_lower = url.lower()
            audio_extensions = {
                ".mp3",
                ".flac",
                ".wav",
                ".aac",
                ".ogg",
                ".m4a",
                ".wma",
                ".aiff",
                ".dsd",
                ".dsf",
                ".dff",
            }
            if any(url_lower.endswith(ext) for ext in audio_extensions):
                return True

        return False

    def play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        """Play a piece of media (sync wrapper)."""
        self.hass.async_create_task(self.async_play_media(media_type, media_id, **kwargs))  # type: ignore[attr-defined]

    async def async_play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        """Play a piece of media."""
        _LOGGER.debug("Play media called: type=%s, id=%s", media_type, media_id)
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]
        hass = self.hass  # type: ignore[attr-defined]

        try:
            # Handle media-source:// URLs by resolving them first
            if media_id.startswith("media-source://"):
                is_tts_content = self._is_tts_media_source(media_id)
                content_type = "TTS" if is_tts_content else "media"
                _LOGGER.debug("Resolving %s source: %s", content_type, media_id)

                try:
                    from homeassistant.components import media_source

                    # Resolve the media source to get the actual playable URL
                    play_item = await media_source.async_resolve_media(hass, media_id)
                    resolved_url = play_item.url

                    _LOGGER.debug("%s source resolved: %s -> %s", content_type, media_id, resolved_url)

                    # Validate that it's audio content
                    if not self._is_audio_media_source(play_item):
                        error_msg = f"Unsupported media type for WiiM: {getattr(play_item, 'mime_type', 'unknown')}"
                        if is_tts_content:
                            error_msg += " (TTS content should always be audio)"
                        raise HomeAssistantError(error_msg)

                    # Play the resolved URL
                    media_id = resolved_url
                    media_type = MediaType.URL

                    if is_tts_content:
                        _LOGGER.info("Playing TTS content on WiiM device")

                except Exception as err:
                    error_msg = f"Failed to resolve {content_type} source: {err}"
                    _LOGGER.error(error_msg)
                    raise HomeAssistantError(error_msg) from err

            # Continue with normal media handling logic
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

                # Let adaptive polling handle sync (no immediate refresh needed)

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

            # Let adaptive polling handle sync (no immediate refresh needed)

        except Exception:
            raise

    async def async_play_url(self, url: str) -> None:
        """Play a URL."""
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        try:
            await controller.play_url(url)

            # Let adaptive polling handle sync (no immediate refresh needed)

        except Exception:
            raise
