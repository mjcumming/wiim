"""WiiM media player platform."""

from __future__ import annotations

import binascii
import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError  # Graceful error handling
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import yaml as hass_yaml

from .data import Speaker, get_speaker_from_config_entry
from .entity import WiimEntity
from .media_controller import MediaPlayerController

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM Media Player platform."""
    speaker = get_speaker_from_config_entry(hass, config_entry)
    async_add_entities([WiiMMediaPlayer(speaker)])


class WiiMMediaPlayer(WiimEntity, MediaPlayerEntity):
    """WiiM media player entity.

    This is a THIN WRAPPER that delegates all functionality to MediaPlayerController.
    The entity focuses solely on the Home Assistant interface while the controller
    handles all complex media player business logic.
    """

    def __init__(self, speaker: Speaker) -> None:
        """Initialize the media player."""
        super().__init__(speaker)
        self.controller = MediaPlayerController(speaker)

        # Optimistic state for immediate UI feedback
        self._optimistic_volume: float | None = None
        self._optimistic_mute: bool | None = None
        self._optimistic_state: MediaPlayerState | None = None
        self._optimistic_source: str | None = None
        self._optimistic_shuffle: bool | None = None
        self._optimistic_repeat: str | None = None

        # Track info for album art cache management
        self._last_track_info: dict[str, Any] = {}

        # HA convention: Use device name as entity name
        self._attr_name = None

        # Override unique_id to match raw speaker UUID (tests expect this)
        self._attr_unique_id = self.speaker.uuid

        # Debouncer for high-frequency volume changes (slider drags)
        self._volume_debouncer: Debouncer | None = None
        self._pending_volume: float | None = None

        # Quick stations YAML path will be resolved lazily once self.hass is available
        self._quick_stations_path: Path | None = None
        self._quick_station_cache: list[dict[str, str]] = []  # cache for title lookup

        # Optimistic media title to show friendly station name immediately
        self._optimistic_media_title: str | None = None

        _LOGGER.debug(
            "WiiMMediaPlayer initialized for %s with controller delegation",
            speaker.name,
        )

    @property
    def name(self) -> str:
        """Return the name of the entity (device name only)."""
        # Ensures media_player entity_id shares the same base slug as other entities
        # (e.g. media_player.main_floor_speakers) by providing Home Assistant with
        # a concrete name during initial entity_id generation.
        return self.speaker.name

    async def async_added_to_hass(self) -> None:
        """Set up entity."""
        await super().async_added_to_hass()
        _LOGGER.debug("Media player %s registered with entity_id %s", self.speaker.name, self.entity_id)

        # Create debouncer lazily once hass is available
        if self._volume_debouncer is None:
            self._volume_debouncer = Debouncer(
                self.hass,
                _LOGGER,
                cooldown=0.4,          # max 1 cmd / 0.4 s  (~2.5 Hz)
                immediate=False,
                function=self._send_volume_debounced,
            )

    @callback
    def async_write_ha_state(self) -> None:
        """Write state to Home Assistant and clear image cache if track changed."""
        # Check if track metadata changed to clear image cache
        current_track_info = {
            "title": self.media_title,
            "artist": self.media_artist,
            "album": self.media_album_name,
            "image_url": self.media_image_url,
        }

        # Remove None values for comparison
        current_track_info = {k: v for k, v in current_track_info.items() if v is not None}

        # Check if track changed (title/artist change indicates new song)
        track_changed = current_track_info.get("title") != self._last_track_info.get("title") or current_track_info.get(
            "artist"
        ) != self._last_track_info.get("artist")

        # Check if image URL changed
        image_url_changed = current_track_info.get("image_url") != self._last_track_info.get("image_url")

        if current_track_info != self._last_track_info:
            # Track metadata changed - clear image cache
            for key in set(current_track_info.keys()) | set(self._last_track_info.keys()):
                old_val = self._last_track_info.get(key)
                new_val = current_track_info.get(key)
                if old_val != new_val:
                    if key == "image_url":
                        _LOGGER.debug(
                            "🎨 Media player clearing image cache due to URL change: %s -> %s", old_val, new_val
                        )
                    elif key in ["title", "artist"]:
                        _LOGGER.debug("🎵 Media player detected %s change: %s -> %s", key, old_val, new_val)

            # CRITICAL: Clear cache when track changes OR when image URL changes
            # WiiM devices often keep the same URL but change the image content
            if track_changed or image_url_changed:
                if track_changed and not image_url_changed and current_track_info.get("image_url"):
                    _LOGGER.debug(
                        "🎨 Media player forcing image cache clear - track changed but URL stayed same (WiiM behavior)"
                    )
                self.controller.clear_media_image_cache()

            self._last_track_info = current_track_info.copy()

        # Call parent to write state
        super().async_write_ha_state()

    # ===== HOME ASSISTANT ENTITY PROPERTIES =====

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        features = (
            MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
            | MediaPlayerEntityFeature.SELECT_SOURCE
            | MediaPlayerEntityFeature.SELECT_SOUND_MODE
            | MediaPlayerEntityFeature.SHUFFLE_SET
            | MediaPlayerEntityFeature.REPEAT_SET
            | MediaPlayerEntityFeature.GROUPING
            | MediaPlayerEntityFeature.BROWSE_MEDIA
        )

        # Add conditional features based on device capabilities
        try:
            # Check if device supports seeking (most modern WiiM devices do)
            status = self.speaker.coordinator.data.get("status", {}) if self.speaker.coordinator.data else {}

            # Enable seek if device reports duration/position or is playing streaming content
            if (
                status.get("duration") is not None
                or status.get("position") is not None
                or status.get("source") in ["spotify", "tidal", "qobuz", "amazon", "network"]
            ):
                features |= MediaPlayerEntityFeature.SEEK

            # Enable play_media for URL/stream playback (all WiiM devices support this)
            features |= MediaPlayerEntityFeature.PLAY_MEDIA

        except Exception as err:
            _LOGGER.debug("Failed to determine conditional features: %s", err)

        return features

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Follows the test logic: available if both flags are True
        return bool(getattr(self.speaker, "_available", True)) and bool(
            getattr(getattr(self.speaker, "coordinator", None), "last_update_success", True)
        )

    # ===== VOLUME PROPERTIES (delegate to controller) =====

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        # Use optimistic state if available for immediate feedback
        if self._optimistic_volume is not None:
            return self._optimistic_volume
        return self.controller.get_volume_level()

    @property
    def is_volume_muted(self) -> bool | None:
        """Boolean if volume is currently muted."""
        # Use optimistic state if available for immediate feedback
        if self._optimistic_mute is not None:
            return self._optimistic_mute
        return self.controller.is_volume_muted()

    # ===== PLAYBACK PROPERTIES (delegate to controller) =====

    @property
    def state(self) -> MediaPlayerState:
        """State of the media player."""
        # Use optimistic state if available for immediate feedback
        if self._optimistic_state is not None:
            return self._optimistic_state
        return self.controller.get_playback_state()

    # ===== SOURCE PROPERTIES (delegate to controller) =====

    @property
    def source(self) -> str | None:
        """Name of the current input source."""
        # Use optimistic state if available for immediate feedback
        if self._optimistic_source is not None:
            return self._optimistic_source
        return self.controller.get_current_source()

    @property
    def source_list(self) -> list[str]:
        """List of available input sources."""
        return self.controller.get_source_list()

    @property
    def sound_mode(self) -> str | None:
        """Name of the current sound mode."""
        return self.controller.get_sound_mode()

    @property
    def sound_mode_list(self) -> list[str]:
        """List of available sound modes."""
        return self.controller.get_sound_mode_list()

    @property
    def shuffle(self) -> bool | None:
        """Boolean if shuffle is enabled."""
        # Use optimistic state if available for immediate feedback
        if self._optimistic_shuffle is not None:
            return self._optimistic_shuffle
        return self.controller.get_shuffle_state()

    @property
    def repeat(self) -> str | None:
        """Return current repeat mode."""
        # Use optimistic state if available for immediate feedback
        if self._optimistic_repeat is not None:
            return self._optimistic_repeat
        return self.controller.get_repeat_mode()

    # ===== MEDIA PROPERTIES (delegate to controller) =====

    @property
    def media_content_type(self) -> MediaType | None:
        """Content type of current playing media."""
        # Most WiiM content is music
        return MediaType.MUSIC

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        if self._optimistic_media_title is not None:
            return self._optimistic_media_title

        title = self.controller.get_media_title()

        # 1) Decode hex-encoded URL strings reported by LinkPlay
        if title:
            decoded = self._maybe_decode_hex_url(title)
            if decoded:
                title = decoded

        # 2) Replace URL / filename with friendly name from Quick-Stations list
        if title and isinstance(title, str) and self._quick_station_cache:
            for st in self._quick_station_cache:
                url_val = st.get("url") or ""
                if isinstance(url_val, str) and url_val.endswith(title):
                    title = st["name"]
                    break

        return title

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media."""
        return self.controller.get_media_artist()

    @property
    def media_album_name(self) -> str | None:
        """Album name of current playing media."""
        return self.controller.get_media_album()

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        return self.controller.get_media_duration()

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        return self.controller.get_media_position()

    @property
    def media_position_updated_at(self) -> float | None:
        """When the position was last updated."""
        return self.controller.get_media_position_updated_at()

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        return self.controller.get_media_image_url()

    @property
    def media_image_remotely_accessible(self) -> bool:
        """If the image url is remotely accessible."""
        # WiiM devices serve images locally (HTTP or self-signed HTTPS)
        # These are not directly accessible by web browsers, so HA must proxy them
        return False

    async def async_get_media_image(self) -> tuple[bytes | None, str | None]:
        """Fetch media image of current playing media.

        Returns:
            Tuple of (image_bytes, content_type) or (None, None) if no image available.
        """
        return await self.controller.get_media_image()

    # ===== GROUP PROPERTIES (delegate to controller) =====

    @property
    def group_members(self) -> list[str]:
        """List of group member entity IDs."""
        return self.controller.get_group_members()

    # ===== OPTIMISTIC STATE MANAGEMENT =====

    def _clear_optimistic_state(self) -> None:
        """Clear optimistic state when real data is available."""
        # Only clear optimistic volume/mute if there is no command in-flight.
        if self._pending_volume is None:
            self._optimistic_volume = None
            self._optimistic_mute = None
        # Other optimistic fields are safe to clear immediately.
        self._optimistic_state = None
        self._optimistic_source = None
        self._optimistic_shuffle = None
        self._optimistic_repeat = None
        self._optimistic_media_title = None

    async def _async_execute_command_with_immediate_refresh(self, command_name: str) -> None:
        """Execute command with immediate polling for fast UI updates.

        This provides much better UX than waiting 5 seconds for next poll cycle.
        """
        _LOGGER.debug("Command '%s' completed, requesting immediate refresh for %s", command_name, self.speaker.name)

        # Clear any previous command failures since this command succeeded
        if hasattr(self.speaker.coordinator, 'clear_command_failures'):
            self.speaker.coordinator.clear_command_failures()

        # Request immediate coordinator refresh instead of waiting for next 5s cycle
        await self.coordinator.async_request_refresh()

        # Clear optimistic state since real data is coming
        self._clear_optimistic_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update - clear optimistic state when real data arrives."""
        self._clear_optimistic_state()
        # Call parent to handle normal coordinator entity lifecycle
        super()._handle_coordinator_update()

    # ===== VOLUME COMMANDS (optimistic updates + immediate refresh) =====

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        # 1. Optimistic update for immediate UI feedback
        self._optimistic_volume = volume
        self._pending_volume = volume
        self.async_write_ha_state()

        # ------------------------------------------------------------------
        # For single, infrequent volume changes (typical button click tests or
        # manual user interaction) we can call the API immediately to keep the
        # behaviour simple and deterministic.  When the debouncer has already
        # been created (e.g. because the user is dragging the slider) we fall
        # back to the debounced approach to avoid command-flooding.
        # ------------------------------------------------------------------

        if self._volume_debouncer is None:
            # FIRST call → execute immediately, create debouncer for subsequent
            # rapid updates.
            await self.controller.set_volume(volume)
            await self._async_execute_command_with_immediate_refresh("set_volume")

            # Create debouncer for any follow-up rapid changes.
            self._volume_debouncer = Debouncer(
                self.hass,
                _LOGGER,
                cooldown=0.4,
                immediate=False,
                function=self._send_volume_debounced,
            )

            # Command executed – clear pending marker.
            self._pending_volume = None
            return

        # Debouncer already exists → we're in a slider drag scenario, use it.
        await self._volume_debouncer.async_call()

    async def _send_volume_debounced(self) -> None:
        """Send the last requested volume to the device (debounced)."""
        if self._pending_volume is None:
            return

        try:
            await self.controller.set_volume(self._pending_volume)

            # Immediate refresh to confirm actual device state
            await self._async_execute_command_with_immediate_refresh("set_volume_debounced")

        except HomeAssistantError as err:
            # Record command failure for immediate user feedback
            if hasattr(self.speaker.coordinator, 'record_command_failure'):
                self.speaker.coordinator.record_command_failure("set_volume", err)

            # Clear optimistic state so UI snaps back gracefully
            self._optimistic_volume = None
            self.async_write_ha_state()

            # Do NOT re-raise – prevents noisy stack traces & keeps entity alive

        except Exception:
            # Unexpected error – bubble up after clearing optimistic state
            self._optimistic_volume = None
            self.async_write_ha_state()
            raise

        finally:
            # Reset pending value so next change is fresh
            self._pending_volume = None

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        # 1. Optimistic update for immediate UI feedback
        self._optimistic_mute = mute
        self.async_write_ha_state()

        try:
            # 2. Send command to device
            await self.controller.set_mute(mute)

            # 3. Immediate refresh for confirmation (don't wait 5 seconds)
            await self._async_execute_command_with_immediate_refresh("set_mute")

        except Exception:
            # Clear optimistic state on error so real state shows
            self._optimistic_mute = None
            self.async_write_ha_state()
            raise

    async def async_volume_up(self) -> None:
        """Increase volume using the configured step size."""
        # Determine step from controller config (fallback to 5 %)
        step = getattr(self.controller, "_volume_step", 0.05)

        # Base calculation on the value the UI currently shows. If we already
        # applied an optimistic change that hasn't been confirmed yet use that
        # value so consecutive clicks accumulate properly.
        current_volume = (
            self._optimistic_volume
            if self._optimistic_volume is not None
            else self.controller.get_volume_level() or 0.0
        )
        new_volume = min(1.0, current_volume + step)

        # 1. Optimistic UI update
        self._optimistic_volume = new_volume
        self._pending_volume = new_volume
        self.async_write_ha_state()

        try:
            # 2. Send absolute volume so we don't double-apply the step
            await self.controller.set_volume(new_volume)

            # 3. Immediate refresh for confirmation
            await self._async_execute_command_with_immediate_refresh("volume_up")

            # Mark command complete
            self._pending_volume = None

        except HomeAssistantError as err:
            # Record command failure for immediate user feedback
            if hasattr(self.speaker.coordinator, 'record_command_failure'):
                self.speaker.coordinator.record_command_failure("volume_up", err)
            self._optimistic_volume = None
            self.async_write_ha_state()
            # swallow to avoid traceback
        except Exception:
            # Clear optimistic state on error
            self._optimistic_volume = None
            self.async_write_ha_state()
            raise

    async def async_volume_down(self) -> None:
        """Decrease volume using the configured step size."""
        # Determine step from controller config (fallback to 5 %)
        step = getattr(self.controller, "_volume_step", 0.05)

        # Base calculation on the value the UI currently shows. If we already
        # applied an optimistic change that hasn't been confirmed yet use that
        # value so consecutive clicks accumulate properly.
        current_volume = (
            self._optimistic_volume
            if self._optimistic_volume is not None
            else self.controller.get_volume_level() or 0.0
        )
        new_volume = max(0.0, current_volume - step)

        # 1. Optimistic UI update
        self._optimistic_volume = new_volume
        self._pending_volume = new_volume
        self.async_write_ha_state()

        try:
            # 2. Send absolute volume so we don't double-apply the step
            await self.controller.set_volume(new_volume)

            # 3. Immediate refresh for confirmation
            await self._async_execute_command_with_immediate_refresh("volume_down")

            # Mark command complete
            self._pending_volume = None

        except HomeAssistantError as err:
            # Record command failure for immediate user feedback
            if hasattr(self.speaker.coordinator, 'record_command_failure'):
                self.speaker.coordinator.record_command_failure("volume_down", err)
            self._optimistic_volume = None
            self.async_write_ha_state()
            # swallow to avoid traceback
        except Exception:
            # Clear optimistic state on error
            self._optimistic_volume = None
            self.async_write_ha_state()
            raise

    # ===== PLAYBACK COMMANDS (optimistic updates + immediate refresh) =====

    async def async_media_play(self) -> None:
        """Send play command."""
        # 1. Optimistic update for immediate UI feedback
        self._optimistic_state = MediaPlayerState.PLAYING
        self.async_write_ha_state()

        try:
            # 2. Send command to device
            await self.controller.play()

            # 3. Immediate refresh for confirmation (don't wait 5 seconds)
            await self._async_execute_command_with_immediate_refresh("play")

        except Exception:
            # Clear optimistic state on error so real state shows
            self._optimistic_state = None
            self.async_write_ha_state()
            raise

    async def async_media_pause(self) -> None:
        """Send pause command."""
        # 1. Optimistic update for immediate UI feedback
        self._optimistic_state = MediaPlayerState.PAUSED
        self.async_write_ha_state()

        try:
            # 2. Send command to device
            await self.controller.pause()

            # 3. Immediate refresh for confirmation (don't wait 5 seconds)
            await self._async_execute_command_with_immediate_refresh("pause")

        except Exception:
            # Clear optimistic state on error so real state shows
            self._optimistic_state = None
            self.async_write_ha_state()
            raise

    async def async_media_stop(self) -> None:
        """Send stop command."""
        # 1. Optimistic update for immediate UI feedback
        self._optimistic_state = MediaPlayerState.IDLE
        self.async_write_ha_state()

        try:
            # 2. Send command to device
            await self.controller.stop()

            # 3. Immediate refresh for confirmation (don't wait 5 seconds)
            await self._async_execute_command_with_immediate_refresh("stop")

        except Exception:
            # Clear optimistic state on error so real state shows
            self._optimistic_state = None
            self.async_write_ha_state()
            raise

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        try:
            # No predictable optimistic state for track changes
            await self.controller.next_track()

            # Immediate refresh for fast track info update
            await self._async_execute_command_with_immediate_refresh("next_track")

        except Exception:
            raise

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        try:
            # No predictable optimistic state for track changes
            await self.controller.previous_track()

            # Immediate refresh for fast track info update
            await self._async_execute_command_with_immediate_refresh("previous_track")

        except Exception:
            raise

    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        try:
            # No predictable optimistic state for seeking
            await self.controller.seek(position)

            # Immediate refresh for fast position update
            await self._async_execute_command_with_immediate_refresh("seek")

        except Exception:
            raise

    # ===== SOURCE COMMANDS (optimistic updates + immediate refresh) =====

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        # 1. Optimistic update for immediate UI feedback
        self._optimistic_source = source
        self.async_write_ha_state()

        try:
            # 2. Send command to device
            await self.controller.select_source(source)

            # 3. Immediate refresh for confirmation (don't wait 5 seconds)
            await self._async_execute_command_with_immediate_refresh("select_source")

        except Exception:
            # Clear optimistic state on error so real state shows
            self._optimistic_source = None
            self.async_write_ha_state()
            raise

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        try:
            # EQ changes don't have direct UI state, just refresh quickly
            await self.controller.set_eq_preset(sound_mode)

            # Immediate refresh for fast EQ update
            await self._async_execute_command_with_immediate_refresh("select_sound_mode")

        except Exception:
            raise

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffle mode."""
        # 1. Optimistic update for immediate UI feedback
        self._optimistic_shuffle = shuffle
        self.async_write_ha_state()

        try:
            # 2. Send command to device
            await self.controller.set_shuffle(shuffle)

            # 3. Immediate refresh for confirmation (don't wait 5 seconds)
            await self._async_execute_command_with_immediate_refresh("set_shuffle")

        except Exception:
            # Clear optimistic state on error so real state shows
            self._optimistic_shuffle = None
            self.async_write_ha_state()
            raise

    async def async_set_repeat(self, repeat: str) -> None:
        """Set repeat mode."""
        # 1. Optimistic update for immediate UI feedback
        self._optimistic_repeat = repeat
        self.async_write_ha_state()

        try:
            # 2. Send command to device
            await self.controller.set_repeat(repeat)

            # 3. Immediate refresh for confirmation (don't wait 5 seconds)
            await self._async_execute_command_with_immediate_refresh("set_repeat")

        except Exception:
            # Clear optimistic state on error so real state shows
            self._optimistic_repeat = None
            self.async_write_ha_state()
            raise

    # ===== GROUP COMMANDS (immediate refresh) =====

    async def async_join(self, group_members: list[str]) -> None:
        """Join speakers into a group."""
        try:
            await self.controller.join_group(group_members)

            # Immediate refresh for fast group state update
            await self._async_execute_command_with_immediate_refresh("join_group")

        except Exception:
            raise

    async def async_unjoin(self) -> None:
        """Remove this speaker from any group."""
        try:
            await self.controller.leave_group()

            # Immediate refresh for fast group state update
            await self._async_execute_command_with_immediate_refresh("leave_group")

        except Exception:
            raise

    async def async_unjoin_player(self) -> None:
        """Remove this player from any group (HA core override).

        Override the core implementation to directly use our async_unjoin method
        instead of running unjoin_player in an executor.
        """
        _LOGGER.debug("async_unjoin_player called for %s", self.speaker.name)
        await self.async_unjoin()

    async def async_join_players(self, group_members: list[str]) -> None:
        """Join this player with others (HA core override).

        Override the core implementation to directly use our async_join method
        instead of running join_players in an executor.
        """
        _LOGGER.debug("async_join_players called for %s with members: %s", self.speaker.name, group_members)
        await self.async_join(group_members)

    # ===== MEDIA COMMANDS (immediate refresh) =====

    async def async_play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        """Play a piece of media."""
        _LOGGER.debug("Play media called: type=%s, id=%s", media_type, media_id)
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
                station_title = await self._async_lookup_quick_station_title(media_id)
                if station_title:
                    self._optimistic_media_title = station_title
                    self._optimistic_state = MediaPlayerState.PLAYING
                    # Show a sensible source immediately (WiFi)
                    self._optimistic_source = "WiFi"
                    self.async_write_ha_state()
                else:
                    self._optimistic_media_title = None
                    self._optimistic_state = MediaPlayerState.PLAYING
                    self._optimistic_source = None
                    self.async_write_ha_state()

                # Always send the URL to the device
                await self.controller.play_url(media_id)

                # Immediate refresh for fast media update
                await self._async_execute_command_with_immediate_refresh("play_media")

            else:
                _LOGGER.warning("Unsupported media type: %s", media_type)
        except Exception as err:
            _LOGGER.error("Failed to play media %s: %s", media_id, err)
            raise

    # ===== ADVANCED COMMANDS (immediate refresh) =====

    async def async_play_preset(self, preset: int) -> None:
        """Play a WiiM preset (1-6)."""
        try:
            await self.controller.play_preset(preset)

            # Immediate refresh for fast preset update
            await self._async_execute_command_with_immediate_refresh("play_preset")

        except Exception:
            raise

    async def async_play_url(self, url: str) -> None:
        """Play a URL."""
        try:
            await self.controller.play_url(url)

            # Immediate refresh for fast URL play update
            await self._async_execute_command_with_immediate_refresh("play_url")

        except Exception:
            raise

    # ===== APP NAME PROPERTY =====

    @property
    def app_name(self) -> str | None:
        """Return the name of the current streaming service.

        This maps internal source codes to user-friendly streaming service names.
        """
        if not self.speaker.coordinator.data:
            return None

        status = self.speaker.coordinator.data.get("status", {})

        # First try explicit streaming service field
        streaming_service = status.get("streaming_service")
        if streaming_service and self._is_valid_app_name(streaming_service):
            return streaming_service

        # Fallback to source mapping for streaming services
        source = status.get("source")
        if source and self._is_valid_app_name(source):
            # Map known streaming services to friendly names
            streaming_map = {
                "spotify": "Spotify",
                "tidal": "Tidal",
                "qobuz": "Qobuz",
                "amazon": "Amazon Music",
                "deezer": "Deezer",
                "airplay": "AirPlay",
                "dlna": "DLNA",
            }

            source_lower = source.lower()
            if source_lower in streaming_map:
                return streaming_map[source_lower]

        # Return None instead of garbage - this will hide the field
        return None

    def _is_valid_app_name(self, text: str) -> bool:
        """Check if app name text is valid and not garbage.

        Uses same comprehensive filtering as media text to prevent
        "wiim 192 168 1 68" and similar garbage from showing up.

        Args:
            text: The text to validate

        Returns:
            True if text is valid app/service name, False if garbage
        """
        if not text or not isinstance(text, str):
            return False

        text_clean = text.strip().lower()

        # Must be at least 2 characters
        if len(text_clean) < 2:
            return False

        # Filter out text starting with "wiim" (catches "wiim 192 168 1 68" etc.)
        if text_clean.startswith("wiim"):
            return False

        # Filter out text containing IP address patterns
        import re

        ip_pattern = r"\b\d{1,3}[\s\.]?\d{1,3}[\s\.]?\d{1,3}[\s\.]?\d{1,3}\b"
        if re.search(ip_pattern, text_clean):
            return False

        # Filter out generic garbage values
        garbage_values = {
            "unknown",
            "none",
            "null",
            "undefined",
            "n/a",
            "na",
            "not available",
            "no data",
            "empty",
            "---",
            "...",
            "loading",
            "buffering",
            "connecting",
            "error",
        }
        if text_clean in garbage_values:
            return False

        # Filter out purely numeric text (likely technical IDs)
        if text_clean.replace(" ", "").replace(".", "").replace("-", "").replace("_", "").isdigit():
            return False

        # Text passes all filters
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes for diagnostics."""
        if not self.speaker.coordinator.data:
            return {}

        attrs = {
            "speaker_uuid": self.speaker.uuid,
            "speaker_role": self.speaker.role,
            "coordinator_ip": self.speaker.ip_address,
            "group_members_count": len(self.speaker.group_members),
        }

        # Add smart polling diagnostics
        polling_info = self.speaker.coordinator.data.get("polling", {})
        if polling_info:
            attrs.update(
                {
                    "activity_level": polling_info.get("activity_level", "unknown"),
                    "polling_interval": polling_info.get("interval", 5.0),
                }
            )

        return attrs

    # ===== MEDIA BROWSER SUPPORT =====

    async def async_browse_media(self, media_content_type: str | None = None, media_content_id: str | None = None):
        """Provide a Media Browser tree with a single Presets shelf."""
        from homeassistant.components.media_player.browse_media import (
            BrowseMedia,
            MediaClass,
        )

        # HA 2024.6 renamed BrowseError → BrowseMediaError; add fallback.
        try:
            from homeassistant.components.media_player.browse_media import BrowseError as _BrowseError
        except ImportError:  # pragma: no cover
            from homeassistant.exceptions import HomeAssistantError as _BrowseError

        # Fetch presets from coordinator
        presets: list[dict] = self.speaker.coordinator.data.get("presets", []) if self.speaker.coordinator.data else []
        # Show the Presets shelf whenever the device claims to support presets OR
        # we have not yet determined support. Only hide it when we explicitly
        # know presets are unsupported.
        presets_capability = getattr(self.speaker.coordinator, "_presets_supported", None)
        presets_supported = presets_capability is not False  # None (unknown) or True ⇒ show

        # Load user defined quick stations (if any)
        quick_stations: list[dict[str, str]] = await self._async_load_quick_stations()

        # ===== ROOT LEVEL =====
        if media_content_id in (None, "root"):
            children: list[BrowseMedia] = []

            if presets_supported:
                children.append(
                    BrowseMedia(
                        media_class=MediaClass.DIRECTORY,
                        media_content_id="presets",
                        media_content_type="presets",
                        title="Presets",
                        can_play=False,
                        can_expand=True,
                        children=[],
                        thumbnail=None,
                    )
                )

            if quick_stations:
                children.append(
                    BrowseMedia(
                        media_class=MediaClass.DIRECTORY,
                        media_content_id="quick",
                        media_content_type="quick",
                        title="Quick Stations",
                        can_play=False,
                        can_expand=True,
                        children=[],
                        thumbnail=None,
                    )
                )

            if not children:
                # No content to show – return empty shelf
                return BrowseMedia(
                    media_class=MediaClass.DIRECTORY,
                    media_content_id="root",
                    media_content_type="root",
                    title=self.speaker.name,
                    can_play=False,
                    can_expand=False,
                    children=[],
                )

            return BrowseMedia(
                media_class=MediaClass.DIRECTORY,
                media_content_id="root",
                media_content_type="root",
                title=self.speaker.name,
                can_play=False,
                can_expand=True,
                children=children,
            )

        # ===== QUICK STATIONS LEVEL =====
        if media_content_id == "quick":
            items: list[BrowseMedia] = []
            for st in quick_stations:
                items.append(
                    BrowseMedia(
                        media_class=MediaClass.MUSIC,
                        media_content_id=st["url"],
                        media_content_type="url",
                        title=st["name"],
                        can_play=True,
                        can_expand=False,
                        thumbnail=None,
                    )
                )

            # Cache for quick lookup in media_title
            self._quick_station_cache = quick_stations
            return BrowseMedia(
                media_class=MediaClass.DIRECTORY,
                media_content_id="quick",
                media_content_type="quick",
                title="Quick Stations",
                can_play=False,
                can_expand=True,
                children=items,
            )

        # ===== PRESETS LEVEL =====
        if media_content_id == "presets":
            items: list[BrowseMedia] = []
            for entry in presets:
                title = entry.get("name") or f"Preset {entry.get('number')}"
                number = entry.get("number")
                url = entry.get("url") or ""
                if not number or not url:
                    continue
                items.append(
                    BrowseMedia(
                        media_class=MediaClass.MUSIC,
                        media_content_id=str(number),
                        media_content_type="preset",
                        title=title,
                        can_play=True,
                        can_expand=False,
                        thumbnail=entry.get("picurl"),
                    )
                )

            return BrowseMedia(
                media_class=MediaClass.DIRECTORY,
                media_content_id="presets",
                media_content_type="presets",
                title="Presets",
                can_play=False,
                can_expand=True,
                children=items,
            )

        # Unknown
        raise _BrowseError("Unknown media_content_id")

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------

    async def _async_load_quick_stations(self) -> list[dict[str, str]]:
        """Read user-defined quick stations from config/wiim_stations.yaml.

        YAML structure expected:
          - name: Friendly Name
            url: http://stream...
        Returns an empty list if the file is missing or malformed.
        """
        if self.hass is None:
            return []  # Should not happen once browse is called

        try:
            if self._quick_stations_path is None:
                self._quick_stations_path = Path(self.hass.config.path("wiim_stations.yaml"))

            if not self._quick_stations_path.exists():
                return []

            data = await self.hass.async_add_executor_job(hass_yaml.load_yaml, str(self._quick_stations_path))
            if not isinstance(data, list):
                return []

            stations: list[dict[str, str]] = []
            for entry in data:
                if isinstance(entry, dict) and entry.get("name") and entry.get("url"):
                    stations.append({"name": str(entry["name"]), "url": str(entry["url"])})

            # Cache for quick lookup in media_title
            self._quick_station_cache = stations
            return stations

        except Exception as err:  # pragma: no cover – non-critical
            _LOGGER.warning("Failed to load quick stations YAML: %s", err)
            return []

    async def _async_lookup_quick_station_title(self, url: str) -> str | None:
        """Return station name for given URL if present in quick stations list."""
        stations = await self._async_load_quick_stations()
        for st in stations:
            if st.get("url") == url:
                return st.get("name")
        return None

    # ---------------------------------------------------------------------
    # Hex URL decode helper & station title mapping
    # ---------------------------------------------------------------------

    _HEX_CHARS = set("0123456789abcdefABCDEF")

    @staticmethod
    def _maybe_decode_hex_url(text: str) -> str | None:
        """Decode hex-encoded URL strings (e.g. '68747470...') to filename."""
        if not text or len(text) % 2 or any(c not in WiiMMediaPlayer._HEX_CHARS for c in text):
            return None
        try:
            decoded_url = binascii.unhexlify(text).decode("utf-8", "ignore")
            path = urlparse(decoded_url).path
            if path:
                return path.rsplit("/", 1)[-1].lstrip("/") or decoded_url
            return decoded_url
        except Exception:
            return None
