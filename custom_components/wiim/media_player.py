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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
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
        """Initialize media player entity."""
        super().__init__(speaker)
        self._attr_name = None  # Use cleaned device name from Speaker class

        # Create controller - this handles ALL media player complexity
        self.controller = MediaPlayerController(speaker)

        _LOGGER.debug(
            "WiiMMediaPlayer initialized for %s with controller delegation",
            speaker.name,
        )

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
            | MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
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

            # Enable media browsing for preset support (all WiiM devices support presets)
            features |= MediaPlayerEntityFeature.BROWSE_MEDIA

            # Enable play_media for URL/stream playback (all WiiM devices support this)
            features |= MediaPlayerEntityFeature.PLAY_MEDIA

        except Exception as err:
            _LOGGER.debug("Failed to determine conditional features: %s", err)

        return features

    # ===== VOLUME PROPERTIES (delegate to controller) =====

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        return self.controller.get_volume_level()

    @property
    def is_volume_muted(self) -> bool | None:
        """Boolean if volume is currently muted."""
        return self.controller.is_volume_muted()

    # ===== PLAYBACK PROPERTIES (delegate to controller) =====

    @property
    def state(self) -> MediaPlayerState:
        """State of the media player."""
        return self.controller.get_playback_state()

    # ===== SOURCE PROPERTIES (delegate to controller) =====

    @property
    def source(self) -> str | None:
        """Name of the current input source."""
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
        return self.controller.get_shuffle_state()

    @property
    def repeat(self) -> str | None:
        """Return current repeat mode."""
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

    # ===== GROUP PROPERTIES (delegate to controller) =====

    @property
    def group_members(self) -> list[str]:
        """List of group member entity IDs."""
        return self.controller.get_group_members()

    # ===== VOLUME COMMANDS (delegate to controller) =====

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self.controller.set_volume(volume)
        await self._async_execute_command_with_refresh("volume")

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        await self.controller.set_mute(mute)
        await self._async_execute_command_with_refresh("mute")

    async def async_volume_up(self) -> None:
        """Volume up the media player."""
        await self.controller.volume_up()
        await self._async_execute_command_with_refresh("volume")

    async def async_volume_down(self) -> None:
        """Volume down the media player."""
        await self.controller.volume_down()
        await self._async_execute_command_with_refresh("volume")

    # ===== PLAYBACK COMMANDS (delegate to controller) =====

    async def async_media_play(self) -> None:
        """Send play command."""
        await self.controller.play()
        await self._async_execute_command_with_refresh("play")

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self.controller.pause()
        await self._async_execute_command_with_refresh("pause")

    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self.controller.stop()
        await self._async_execute_command_with_refresh("stop")

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self.controller.next_track()
        await self._async_execute_command_with_refresh("next")

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self.controller.previous_track()
        await self._async_execute_command_with_refresh("previous")

    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        await self.controller.seek(position)
        await self._async_execute_command_with_refresh("seek")

    # ===== SOURCE COMMANDS (delegate to controller) =====

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        await self.controller.select_source(source)
        await self._async_execute_command_with_refresh("source")

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        await self.controller.set_eq_preset(sound_mode)
        await self._async_execute_command_with_refresh("eq")

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffle mode."""
        await self.controller.set_shuffle(shuffle)
        await self._async_execute_command_with_refresh("shuffle")

    async def async_set_repeat(self, repeat: str) -> None:
        """Set repeat mode."""
        await self.controller.set_repeat(repeat)
        await self._async_execute_command_with_refresh("repeat")

    # ===== POWER COMMANDS (delegate to controller) =====

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        await self.controller.turn_on()
        await self._async_execute_command_with_refresh("power")

    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        await self.controller.turn_off()
        await self._async_execute_command_with_refresh("power")

    # ===== GROUP COMMANDS (delegate to controller) =====

    async def async_join(self, group_members: list[str]) -> None:
        """Join speakers into a group."""
        await self.controller.join_group(group_members)
        await self._async_execute_command_with_refresh("group")

    async def async_unjoin(self) -> None:
        """Remove this speaker from any group."""
        await self.controller.leave_group()
        await self._async_execute_command_with_refresh("group")

    # ===== MEDIA COMMANDS (delegate to controller) =====

    async def async_get_media_image(self) -> tuple[bytes, str] | None:
        """Fetch media image of current playing image."""
        return await self.controller.get_media_image()

    async def async_play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        """Play a piece of media."""
        _LOGGER.debug("Play media called: type=%s, id=%s", media_type, media_id)
        try:
            # For URLs, use play_url
            if media_type in [MediaType.URL, MediaType.MUSIC, "url"]:
                await self.controller.play_url(media_id)
                await self._async_execute_command_with_refresh("play_media")
            else:
                _LOGGER.warning("Unsupported media type: %s", media_type)
        except Exception as err:
            _LOGGER.error("Failed to play media %s: %s", media_id, err)
            raise

    # ===== ADVANCED COMMANDS (delegate to controller) =====

    async def async_play_preset(self, preset: int) -> None:
        """Play a WiiM preset (1-6)."""
        await self.controller.play_preset(preset)
        await self._async_execute_command_with_refresh("preset")

    async def async_play_url(self, url: str) -> None:
        """Play a URL."""
        await self.controller.play_url(url)
        await self._async_execute_command_with_refresh("url")

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        """Implement the websocket media browsing helper."""
        return await self.controller.browse_media(media_content_type, media_content_id)
