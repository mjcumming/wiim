"""WiiM media player platform."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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

        _LOGGER.debug(
            "WiiMMediaPlayer initialized for %s with controller delegation",
            speaker.name,
        )

    async def async_added_to_hass(self) -> None:
        """Set up entity."""
        await super().async_added_to_hass()
        _LOGGER.debug("Media player %s registered with entity_id %s", self.speaker.name, self.entity_id)

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
                        _LOGGER.info(
                            "🎨 Media player clearing image cache due to URL change: %s -> %s", old_val, new_val
                        )
                    elif key in ["title", "artist"]:
                        _LOGGER.debug("🎵 Media player detected %s change: %s -> %s", key, old_val, new_val)

            # CRITICAL: Clear cache when track changes OR when image URL changes
            # WiiM devices often keep the same URL but change the image content
            if track_changed or image_url_changed:
                if track_changed and not image_url_changed and current_track_info.get("image_url"):
                    _LOGGER.info(
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
        return self.controller.get_media_title()

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
        self._optimistic_volume = None
        self._optimistic_mute = None
        self._optimistic_state = None
        self._optimistic_source = None
        self._optimistic_shuffle = None
        self._optimistic_repeat = None

    async def _async_execute_command_with_immediate_refresh(self, command_name: str) -> None:
        """Execute command with immediate polling for fast UI updates.

        This provides much better UX than waiting 5 seconds for next poll cycle.
        """
        _LOGGER.debug("Command '%s' completed, requesting immediate refresh for %s", command_name, self.speaker.name)

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
        self.async_write_ha_state()

        try:
            # 2. Send command to device
            await self.controller.set_volume(volume)

            # 3. Immediate refresh for confirmation (don't wait 5 seconds)
            await self._async_execute_command_with_immediate_refresh("set_volume")

        except Exception:
            # Clear optimistic state on error so real state shows
            self._optimistic_volume = None
            self.async_write_ha_state()
            raise

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
        """Volume up the media player."""
        # Calculate new optimistic volume
        current_volume = self.controller.get_volume_level() or 0.0
        new_volume = min(1.0, current_volume + 0.05)  # 5% step

        # 1. Optimistic update for immediate UI feedback
        self._optimistic_volume = new_volume
        self.async_write_ha_state()

        try:
            # 2. Send command to device
            await self.controller.volume_up()

            # 3. Immediate refresh for confirmation (don't wait 5 seconds)
            await self._async_execute_command_with_immediate_refresh("volume_up")

        except Exception:
            # Clear optimistic state on error so real state shows
            self._optimistic_volume = None
            self.async_write_ha_state()
            raise

    async def async_volume_down(self) -> None:
        """Volume down the media player."""
        # Calculate new optimistic volume
        current_volume = self.controller.get_volume_level() or 0.0
        new_volume = max(0.0, current_volume - 0.05)  # 5% step

        # 1. Optimistic update for immediate UI feedback
        self._optimistic_volume = new_volume
        self.async_write_ha_state()

        try:
            # 2. Send command to device
            await self.controller.volume_down()

            # 3. Immediate refresh for confirmation (don't wait 5 seconds)
            await self._async_execute_command_with_immediate_refresh("volume_down")

        except Exception:
            # Clear optimistic state on error so real state shows
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
            # For URLs, use play_url
            if media_type in [MediaType.URL, MediaType.MUSIC, "url"]:
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
        if streaming_service and not streaming_service.lower().startswith("wiim"):
            return streaming_service

        # Fallback to source mapping for streaming services
        source = status.get("source")
        if source and not source.lower().startswith("wiim"):
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
