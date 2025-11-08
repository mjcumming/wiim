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

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.media_player import MediaPlayerState, MediaType
from homeassistant.components.media_player.browse_media import async_process_play_media_url
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

        speaker_name = self.speaker.name  # type: ignore[attr-defined]
        _LOGGER.info("Setting volume to %.2f (%.0f%%) for %s", volume, volume * 100, speaker_name)

        # 1. Optimistic update for immediate UI feedback
        self._optimistic_volume = volume  # type: ignore[attr-defined]
        self._pending_volume = volume  # type: ignore[attr-defined]
        self.async_write_ha_state()  # type: ignore[attr-defined]

        try:
            has_debouncer = hasattr(self, "_volume_debouncer") and self._volume_debouncer is not None  # type: ignore[attr-defined]
            if has_debouncer:
                # Use the debouncer – command will be sent after cooldown
                # _pending_volume already set above; do NOT clear it here!
                _LOGGER.debug("Volume command queued with debouncer for %s", speaker_name)
                await self._volume_debouncer.async_call()  # type: ignore[attr-defined]
            else:
                # Debouncer not available (shouldn't happen) – send immediately
                _LOGGER.debug("Sending volume command immediately (no debouncer) for %s", speaker_name)
                await controller.set_volume(volume)
                # Command sent → clear the pending flag
                self._pending_volume = None  # type: ignore[attr-defined]

            _LOGGER.info("Volume set command completed successfully for %s at %.0f%%", speaker_name, volume * 100)

            # 3. Let adaptive polling handle sync (no immediate refresh needed)

        except Exception as err:
            # Clear optimistic state on error
            _LOGGER.error(
                "Failed to set volume to %.2f (%.0f%%) for %s: %s (type: %s)",
                volume,
                volume * 100,
                speaker_name,
                err,
                type(err).__name__,
                exc_info=True,
            )
            self._optimistic_volume = None  # type: ignore[attr-defined]
            self._pending_volume = None  # type: ignore[attr-defined]
            self.async_write_ha_state()  # type: ignore[attr-defined]
            raise

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]
        speaker_name = self.speaker.name  # type: ignore[attr-defined]

        _LOGGER.info("Setting mute to %s for %s", mute, speaker_name)

        # 1. Optimistic update for immediate UI feedback
        self._optimistic_mute = mute  # type: ignore[attr-defined]
        self.async_write_ha_state()  # type: ignore[attr-defined]

        try:
            # 2. Send command to device
            _LOGGER.debug("Sending mute command to device for %s", speaker_name)
            await controller.set_mute(mute)
            _LOGGER.info("Mute command completed successfully for %s (mute=%s)", speaker_name, mute)

            # 3. Let adaptive polling handle sync (no immediate refresh needed)

        except Exception as err:
            # Clear optimistic state on error so real state shows
            _LOGGER.error(
                "Failed to set mute to %s for %s: %s (type: %s)",
                mute,
                speaker_name,
                err,
                type(err).__name__,
                exc_info=True,
            )
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

        speaker_name = self.speaker.name  # type: ignore[attr-defined]
        _LOGGER.info(
            "Volume up: %.0f%% -> %.0f%% (step=%.0f%%) for %s",
            current * 100,
            new_volume * 100,
            step * 100,
            speaker_name,
        )

        # Optimistic UI update
        self._optimistic_volume = new_volume  # type: ignore[attr-defined]
        self._pending_volume = new_volume  # type: ignore[attr_defined]
        self.async_write_ha_state()  # type: ignore[attr-defined]

        try:
            has_debouncer = hasattr(self, "_volume_debouncer") and self._volume_debouncer is not None  # type: ignore[attr-defined]
            if has_debouncer:
                _LOGGER.debug("Volume up command queued with debouncer for %s", speaker_name)
                await self._volume_debouncer.async_call()  # type: ignore[attr_defined]
            else:
                _LOGGER.debug("Sending volume up command immediately for %s", speaker_name)
                await controller.set_volume(new_volume)
            _LOGGER.info("Volume up command completed for %s", speaker_name)
        except Exception as err:
            # Revert optimistic state on error
            _LOGGER.error(
                "Volume up failed for %s: %s (type: %s)",
                speaker_name,
                err,
                type(err).__name__,
                exc_info=True,
            )
            self._optimistic_volume = None  # type: ignore[attr_defined]
            self.async_write_ha_state()  # type: ignore[attr_defined]

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

        speaker_name = self.speaker.name  # type: ignore[attr-defined]
        _LOGGER.info(
            "Volume down: %.0f%% -> %.0f%% (step=%.0f%%) for %s",
            current * 100,
            new_volume * 100,
            step * 100,
            speaker_name,
        )

        self._optimistic_volume = new_volume  # type: ignore[attr_defined]
        self._pending_volume = new_volume  # type: ignore[attr_defined]
        self.async_write_ha_state()  # type: ignore[attr_defined]

        try:
            has_debouncer = hasattr(self, "_volume_debouncer") and self._volume_debouncer is not None  # type: ignore[attr-defined]
            if has_debouncer:
                _LOGGER.debug("Volume down command queued with debouncer for %s", speaker_name)
                await self._volume_debouncer.async_call()  # type: ignore[attr_defined]
            else:
                _LOGGER.debug("Sending volume down command immediately for %s", speaker_name)
                await controller.set_volume(new_volume)
            _LOGGER.info("Volume down command completed for %s", speaker_name)
        except Exception as err:
            _LOGGER.error(
                "Volume down failed for %s: %s (type: %s)",
                speaker_name,
                err,
                type(err).__name__,
                exc_info=True,
            )
            self._optimistic_volume = None  # type: ignore[attr_defined]
            self.async_write_ha_state()  # type: ignore[attr_defined]


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
        """Send play command. Uses resume() if paused to continue from current position."""
        import time

        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]
        speaker = self.speaker  # type: ignore[attr-defined]

        # Check current state - don't restart if already playing
        current_state = self.state  # type: ignore[attr-defined]
        if current_state == MediaPlayerState.PLAYING:
            _LOGGER.debug("Device %s is already playing, skipping play command", speaker.name)
            # Trigger a refresh to get latest metadata/position if playing from external app
            await speaker.coordinator.async_request_refresh()
            return

        # 1. Optimistic update for immediate UI feedback
        self._optimistic_state = MediaPlayerState.PLAYING  # type: ignore[attr-defined]
        self._optimistic_state_timestamp = time.time()  # type: ignore[attr-defined]
        self.async_write_ha_state()  # type: ignore[attr-defined]

        try:
            # 2. Send command to device
            # Use resume() if paused to continue from current position, otherwise use play()
            if current_state == MediaPlayerState.PAUSED:
                _LOGGER.debug("Device %s is paused, using resume to continue playback", speaker.name)
                await controller.resume()
            else:
                await controller.play()

            # 3. Trigger immediate refresh to get updated state/metadata
            await speaker.coordinator.async_request_refresh()

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

    async def async_media_play_pause(self) -> None:
        """Toggle play/pause media player. Uses resume() when resuming from pause."""
        import time

        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]
        speaker = self.speaker  # type: ignore[attr-defined]

        current_state = self.state  # type: ignore[attr-defined]

        if current_state == MediaPlayerState.PLAYING:
            # Currently playing - pause it
            await self.async_media_pause()
        elif current_state == MediaPlayerState.PAUSED:
            # Currently paused - resume from current position
            _LOGGER.debug("Device %s is paused, resuming playback", speaker.name)
            # 1. Optimistic update for immediate UI feedback
            self._optimistic_state = MediaPlayerState.PLAYING  # type: ignore[attr-defined]
            self._optimistic_state_timestamp = time.time()  # type: ignore[attr-defined]
            self.async_write_ha_state()  # type: ignore[attr-defined]

            try:
                # 2. Send resume command to device
                await controller.resume()

                # 3. Trigger immediate refresh to get updated state/metadata
                await speaker.coordinator.async_request_refresh()

            except Exception:
                # Clear optimistic state on error so real state shows
                self._optimistic_state = None  # type: ignore[attr-defined]
                self._optimistic_state_timestamp = None  # type: ignore[attr-defined]
                self.async_write_ha_state()  # type: ignore[attr-defined]
                raise
        else:
            # IDLE or other state - start playing
            await self.async_media_play()

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

    async def async_play_media(
        self, media_type: str, media_id: str, announce: bool | None = None, **kwargs: Any
    ) -> None:
        """Play a piece of media with TTS announcement support."""
        _LOGGER.debug("Play media called: type=%s, id=%s, announce=%s", media_type, media_id, announce)
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]
        hass = self.hass  # type: ignore[attr-defined]

        try:
            # Handle TTS announcements
            if announce:
                await self._async_handle_tts_announcement(media_id, **kwargs)
                return

            # Handle media-source:// URLs by resolving them first
            if media_id.startswith("media-source://"):
                is_tts_content = self._is_tts_media_source(media_id)
                content_type = "TTS" if is_tts_content else "media"
                _LOGGER.debug("Resolving %s source: %s", content_type, media_id)

                try:
                    from homeassistant.components import media_source

                    # Resolve the media source to get the actual playable URL
                    play_item = await media_source.async_resolve_media(hass, media_id, self.entity_id)  # type: ignore[attr-defined]
                    resolved_url = play_item.url

                    # Ensure resolved_url is a string (play_item.url might be a URL object)
                    resolved_url = str(resolved_url) if resolved_url is not None else ""

                    _LOGGER.debug("%s source resolved: %s -> %s", content_type, media_id, resolved_url)

                    # Validate that it's audio content
                    if not self._is_audio_media_source(play_item):
                        error_msg = f"Unsupported media type for WiiM: {getattr(play_item, 'mime_type', 'unknown')}"
                        if is_tts_content:
                            error_msg += " (TTS content should always be audio)"
                        raise HomeAssistantError(error_msg)

                    # Process the resolved URL to convert relative URLs to absolute URLs
                    # This is required for devices (like Audio Pro) that need absolute URLs
                    processed_url = async_process_play_media_url(hass, resolved_url)
                    _LOGGER.debug("%s source URL processed: %s -> %s", content_type, resolved_url, processed_url)

                    # Play the processed URL
                    media_id = processed_url
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
                # Process URL to convert relative URLs to absolute URLs
                # This is required for devices (like Audio Pro) that need absolute URLs
                processed_url = async_process_play_media_url(hass, media_id)
                if processed_url != media_id:
                    _LOGGER.debug("URL processed: %s -> %s", media_id, processed_url)
                    media_id = processed_url

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

                # Always send the processed URL to the device
                await controller.play_url(media_id)

                # Let adaptive polling handle sync (no immediate refresh needed)

            else:
                _LOGGER.warning("Unsupported media type: %s", media_type)
        except Exception as err:
            _LOGGER.error("Failed to play media %s: %s", media_id, err)
            raise

    async def _async_handle_tts_announcement(self, media_id: str, **kwargs: Any) -> None:
        """Handle TTS announcements with role-aware behavior for group coordination."""
        speaker: Speaker = self.speaker  # type: ignore[attr-defined]
        _LOGGER.debug("Handling TTS announcement for %s (role=%s)", speaker.name, speaker.role)

        # Check user preference for TTS behavior
        tts_behavior = kwargs.get("extra", {}).get("tts_behavior", "auto")

        if tts_behavior == "force_local":
            # User wants TTS on this specific speaker regardless of role
            _LOGGER.debug("Force local TTS requested for %s", speaker.name)
            await self._async_play_local_tts(media_id, **kwargs)

        elif tts_behavior == "force_group":
            # User wants group-wide TTS (delegate to master if slave)
            if speaker.role == "slave":
                await self._async_delegate_tts_to_master(media_id, **kwargs)
            else:
                await self._async_play_local_tts(media_id, **kwargs)

        else:  # "auto" - default behavior
            # Use role-based logic
            if speaker.role == "slave":
                await self._async_delegate_tts_to_master(media_id, **kwargs)
            else:
                await self._async_play_local_tts(media_id, **kwargs)

    async def _async_delegate_tts_to_master(self, media_id: str, **kwargs: Any) -> None:
        """Delegate TTS to the group master for group-wide announcement."""
        speaker: Speaker = self.speaker  # type: ignore[attr-defined]

        if not speaker.coordinator_speaker:
            _LOGGER.warning("Slave %s has no coordinator - cannot play TTS", speaker.name)
            raise HomeAssistantError(f"Slave speaker '{speaker.name}' cannot play TTS independently")

        _LOGGER.debug("Slave %s delegating TTS to master %s", speaker.name, speaker.coordinator_speaker.name)

        # Delegate to master speaker
        await speaker.coordinator_speaker._async_handle_tts_announcement(media_id, **kwargs)

    async def _async_play_local_tts(self, media_id: str, **kwargs: Any) -> None:
        """Play TTS locally on this speaker."""
        speaker: Speaker = self.speaker  # type: ignore[attr-defined]
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]
        hass = self.hass  # type: ignore[attr-defined]

        _LOGGER.debug("Playing local TTS on %s", speaker.name)

        # Save current state for restoration
        original_state = await self._save_current_state()

        try:
            # Set TTS volume
            await self._set_tts_volume(**kwargs)

            # Pause current playback if playing
            if self.state == MediaPlayerState.PLAYING:  # type: ignore[attr-defined]
                await controller.pause()

            # Process URL to convert relative URLs to absolute URLs
            # This is required for devices (like Audio Pro) that need absolute URLs
            processed_url = async_process_play_media_url(hass, media_id)
            if processed_url != media_id:
                _LOGGER.debug("TTS URL processed: %s -> %s", media_id, processed_url)
                media_id = processed_url

            # Play TTS audio
            await controller.play_url(media_id)

            # Wait for TTS completion
            await self._wait_for_tts_completion()

            # Resume original playback
            if original_state["state"] == MediaPlayerState.PLAYING:
                await controller.play()

        except Exception as err:
            _LOGGER.error("TTS announcement failed for %s: %s", speaker.name, err)
            raise
        finally:
            # Always restore state
            await self._restore_state(original_state)

    async def _save_current_state(self) -> dict[str, Any]:
        """Save current playback state for restoration after TTS."""
        return {
            "volume": self.volume_level,  # type: ignore[attr-defined]
            "mute": self.is_volume_muted,  # type: ignore[attr-defined]
            "state": self.state,  # type: ignore[attr-defined]
            "position": self.media_position,  # type: ignore[attr-defined]
            "source": self.source,  # type: ignore[attr-defined]
        }

    async def _restore_state(self, saved_state: dict[str, Any]) -> None:
        """Restore saved playback state after TTS."""
        speaker: Speaker = self.speaker  # type: ignore[attr-defined]
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        try:
            # Restore volume
            if saved_state["volume"] is not None:
                await controller.set_volume(saved_state["volume"])

            # Restore mute state
            if saved_state["mute"] is not None:
                await controller.set_mute(saved_state["mute"])

            # Note: Don't restore playback state - let user control that
            # The resume logic is handled in _async_play_local_tts

        except Exception as err:
            _LOGGER.warning("Failed to restore state for %s: %s", speaker.name, err)

    async def _set_tts_volume(self, **kwargs: Any) -> None:
        """Set appropriate volume for TTS announcements."""
        speaker: Speaker = self.speaker  # type: ignore[attr-defined]
        controller: MediaPlayerController = self.controller  # type: ignore[attr-defined]

        # Check for custom TTS volume in kwargs
        extra = kwargs.get("extra", {})
        tts_volume = extra.get("tts_volume")

        if tts_volume is not None:
            # Use specified TTS volume (0-100)
            volume_level = min(max(float(tts_volume) / 100.0, 0.0), 1.0)
            await controller.set_volume(volume_level)
            _LOGGER.debug("Set TTS volume to %.1f%% for %s", tts_volume, speaker.name)
        else:
            # Use default TTS volume: 70% of current volume, but not below 30%
            current_volume = self.volume_level  # type: ignore[attr-defined]
            if current_volume is not None:
                tts_volume_level = max(current_volume * 0.7, 0.3)
                await controller.set_volume(tts_volume_level)
                _LOGGER.debug("Set TTS volume to %.1f%% (70%% of current) for %s", tts_volume_level * 100, speaker.name)
            else:
                # Default TTS volume if current volume unknown
                await controller.set_volume(0.5)
                _LOGGER.debug("Set default TTS volume (50%%) for %s", speaker.name)

    async def _wait_for_tts_completion(self, timeout: float = 30.0) -> None:
        """Wait for TTS audio to complete playing."""
        import time

        speaker: Speaker = self.speaker  # type: ignore[attr-defined]
        start_time = time.time()

        _LOGGER.debug("Waiting for TTS completion on %s", speaker.name)

        while time.time() - start_time < timeout:
            # Check if still playing TTS content
            if self.state != MediaPlayerState.PLAYING:  # type: ignore[attr-defined]
                _LOGGER.debug("TTS completed - no longer playing")
                break

            # Check if position has advanced (indicates active playback)
            current_position = self.media_position  # type: ignore[attr-defined]
            if current_position is not None:
                # If position hasn't changed in 2 seconds, assume TTS is done
                await asyncio.sleep(2.0)
                new_position = self.media_position  # type: ignore[attr-defined]
                if new_position == current_position:
                    _LOGGER.debug("TTS completed - position unchanged")
                    break

            await asyncio.sleep(0.5)

        _LOGGER.debug("TTS completion detected or timeout reached for %s", speaker.name)

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
