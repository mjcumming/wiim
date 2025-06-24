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
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .data import Speaker, get_speaker_from_config_entry
from .entity import WiimEntity
from .media_controller import MediaPlayerController
from .media_player_browser import (
    AppNameValidatorMixin,
    HexUrlDecoderMixin,
    MediaBrowserMixin,
    QuickStationsMixin,
)
from .media_player_commands import (
    GroupCommandsMixin,
    MediaCommandsMixin,
    PlaybackCommandsMixin,
    SourceCommandsMixin,
    VolumeCommandsMixin,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM Media Player platform."""
    speaker = get_speaker_from_config_entry(hass, config_entry)
    async_add_entities([WiiMMediaPlayer(speaker)])


class WiiMMediaPlayer(
    WiimEntity,
    VolumeCommandsMixin,
    PlaybackCommandsMixin,
    SourceCommandsMixin,
    GroupCommandsMixin,
    MediaCommandsMixin,
    MediaPlayerEntity,
    MediaBrowserMixin,
    QuickStationsMixin,
    HexUrlDecoderMixin,
    AppNameValidatorMixin,
):
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

        # Timestamps for optimistic state timeout (10 seconds)
        self._optimistic_state_timestamp: float | None = None

        # Track info for album art cache management
        self._last_track_info: dict[str, Any] = {}

        # HA convention: Use device name as entity name
        self._attr_name = None

        # Override unique_id to match raw speaker UUID (tests expect this)
        self._attr_unique_id = self.speaker.uuid

        # Debouncer for high-frequency volume changes (slider drags)
        self._volume_debouncer: Debouncer | None = None
        self._pending_volume: float | None = None

        # Optimistic media title to show friendly station name immediately
        self._optimistic_media_title: str | None = None

        # Initialize mixins
        QuickStationsMixin.__init__(self)

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
                cooldown=0.4,  # max 1 cmd / 0.4 s  (~2.5 Hz)
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
            # TODO: Re-enable SEEK once behaviour confirmed with typed model only

            # Enable play_media universally (URL/stream support)
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

        # 2) Decode HTML entities (e.g., &apos; -> ')
        if title:
            import html

            title = html.unescape(title)

        # 3) Replace URL / filename with friendly name from Quick-Stations list
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
        if hasattr(self.speaker.coordinator, "clear_command_failures"):
            self.speaker.coordinator.clear_command_failures()

        # Request immediate coordinator refresh instead of waiting for next 5s cycle
        await self.coordinator.async_request_refresh()

        # DO NOT clear optimistic state immediately - let it persist until we get
        # real data from the device that confirms the state change. This prevents
        # the UI from flickering back to the old state before the device responds.

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update - smartly clear optimistic state when real data confirms changes."""
        import time

        # Only clear optimistic state if real data shows the change we expected
        real_state = self.controller.get_playback_state()
        real_volume = self.controller.get_volume_level()
        real_mute = self.controller.is_volume_muted()
        real_source = self.controller.get_current_source()
        real_shuffle = self.controller.get_shuffle_state()
        real_repeat = self.controller.get_repeat_mode()

        # Check for timeout - playback state should respond faster
        if self._optimistic_state_timestamp is not None:
            age = time.time() - self._optimistic_state_timestamp
            # Shorter timeout for playback state (3 seconds) since media players should respond quickly
            if age > 3.0:
                _LOGGER.debug("Optimistic playback state timeout (%.1fs), clearing state", age)
                self._optimistic_state = None
                self._optimistic_state_timestamp = None
            # General timeout for other optimistic state (10 seconds)
            elif age > 10.0:
                _LOGGER.debug("Optimistic state timeout (10s), clearing all optimistic state")
                self._optimistic_volume = None
                self._optimistic_mute = None
                self._optimistic_source = None
                self._optimistic_shuffle = None
                self._optimistic_repeat = None

        # Debug logging for state comparison (at debug level)
        if self._optimistic_state is not None:
            _LOGGER.debug(
                "Optimistic state comparison: optimistic=%s, real=%s, match=%s, age=%.1fs",
                self._optimistic_state,
                real_state,
                real_state == self._optimistic_state,
                time.time() - (self._optimistic_state_timestamp or 0),
            )

        # Clear optimistic state only when real data matches expected changes
        if self._optimistic_state is not None and real_state == self._optimistic_state:
            _LOGGER.debug("Real state matches optimistic state (%s), clearing optimistic state", real_state)
            self._optimistic_state = None
            self._optimistic_state_timestamp = None

        if (
            self._optimistic_volume is not None
            and real_volume is not None
            and abs(real_volume - self._optimistic_volume) < 0.01
        ):
            _LOGGER.debug("Real volume matches optimistic volume (%.2f), clearing optimistic volume", real_volume)
            self._optimistic_volume = None

        if self._optimistic_mute is not None and real_mute == self._optimistic_mute:
            _LOGGER.debug("Real mute matches optimistic mute (%s), clearing optimistic mute", real_mute)
            self._optimistic_mute = None

        if self._optimistic_source is not None and real_source == self._optimistic_source:
            _LOGGER.debug("Real source matches optimistic source (%s), clearing optimistic source", real_source)
            self._optimistic_source = None

        if self._optimistic_shuffle is not None and real_shuffle == self._optimistic_shuffle:
            _LOGGER.debug("Real shuffle matches optimistic shuffle (%s), clearing optimistic shuffle", real_shuffle)
            self._optimistic_shuffle = None

        if self._optimistic_repeat is not None and real_repeat == self._optimistic_repeat:
            _LOGGER.debug("Real repeat matches optimistic repeat (%s), clearing optimistic repeat", real_repeat)
            self._optimistic_repeat = None

        # Always clear optimistic media title - it's transient
        if self._optimistic_media_title is not None:
            self._optimistic_media_title = None

        # Call parent to handle normal coordinator entity lifecycle
        super()._handle_coordinator_update()

    # ===== VOLUME COMMANDS (provided by VolumeCommandsMixin) =====

    # ===== PLAYBACK COMMANDS (provided by PlaybackCommandsMixin) =====

    # ===== SOURCE COMMANDS (provided by SourceCommandsMixin) =====

    # ===== GROUP COMMANDS (provided by GroupCommandsMixin) =====

    # ===== MEDIA COMMANDS (provided by MediaCommandsMixin) =====

    # ===== APP NAME PROPERTY (delegate to mixin) =====

    @property
    def app_name(self) -> str | None:
        """Return the name of the current streaming service."""
        return self.get_app_name()

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

    # ===== MEDIA BROWSER SUPPORT (delegate to mixin) =====

    # async_browse_media method provided by MediaBrowserMixin
