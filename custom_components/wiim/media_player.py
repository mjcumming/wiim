"""WiiM media player platform."""

from __future__ import annotations

import datetime
import logging
from typing import Any

import voluptuous as vol
from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform,
)

from .data import Speaker, get_speaker_from_config_entry
from .entity import WiimEntity
from .group_media_player import WiiMGroupMediaPlayer
from .media_controller import MediaPlayerController

# Conditional import to avoid coroutine issues during testing
try:
    from .media_player_browser import (
        AppNameValidatorMixin,
        HexUrlDecoderMixin,
        MediaBrowserMixin,
        QuickStationsMixin,
    )
except Exception:
    # Fallback for testing environment
    class AppNameValidatorMixin:
        def _is_valid_app_name(self, text: str) -> bool:
            return bool(text and isinstance(text, str) and len(text.strip()) >= 2)

        def get_app_name(self) -> str | None:
            return None

    class HexUrlDecoderMixin:
        _HEX_CHARS = set("0123456789abcdefABCDEF")

        @staticmethod
        def _maybe_decode_hex_url(text: str) -> str | None:
            return None

    class MediaBrowserMixin:
        def _is_audio_content(self, browse_item) -> bool:
            return True

        async def async_browse_media(
            self,
            media_content_type: str | None = None,
            media_content_id: str | None = None,
        ):
            return None

    class QuickStationsMixin:
        def __init__(self) -> None:
            pass

        async def _async_load_quick_stations(self) -> list[dict[str, str]]:
            return []

        async def _async_lookup_quick_station_title(self, url: str) -> str | None:
            return None


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

    # Create both standard and group media players
    # Group player is always created but only becomes available when needed
    entities = [
        WiiMMediaPlayer(speaker),
        WiiMGroupMediaPlayer(speaker),
    ]

    async_add_entities(entities)
    _LOGGER.info("Created media player entities for %s including group coordinator", speaker.name)

    # Register WiiM custom services
    platform = async_get_current_platform()

    # Play Preset service
    platform.async_register_entity_service(
        "play_preset",
        {vol.Required("preset"): vol.All(vol.Coerce(int), vol.Range(min=1, max=20))},
        "async_play_preset",
    )

    # Play URL service
    platform.async_register_entity_service(
        "play_url",
        {vol.Required("url"): str},
        "async_play_url",
    )

    # Play Playlist service
    platform.async_register_entity_service(
        "play_playlist",
        {vol.Required("playlist_url"): str},
        "async_play_playlist",
    )

    # Set EQ service
    platform.async_register_entity_service(
        "set_eq",
        {
            vol.Required("preset"): vol.In(
                [
                    "flat",
                    "classical",
                    "jazz",
                    "vocal",
                    "pop",
                    "rock",
                    "dance",
                    "country",
                    "blues",
                    "custom",
                ]
            ),
            vol.Optional("custom_values"): vol.All(
                vol.Coerce(list),
                vol.Length(min=10, max=10),
                [vol.All(vol.Coerce(float), vol.Range(min=-12, max=12))],
            ),
        },
        "async_set_eq",
    )

    # Play Notification service
    platform.async_register_entity_service(
        "play_notification",
        {vol.Required("url"): str},
        "async_play_notification",
    )

    # Reboot Device service
    platform.async_register_entity_service(
        "reboot_device",
        None,
        "async_reboot_device",
    )

    # Sync Time service
    platform.async_register_entity_service(
        "sync_time",
        None,
        "async_sync_time",
    )


class WiiMMediaPlayer(
    WiimEntity,
    VolumeCommandsMixin,
    PlaybackCommandsMixin,
    SourceCommandsMixin,
    GroupCommandsMixin,
    MediaCommandsMixin,
    MediaBrowserMixin,
    MediaPlayerEntity,
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
        self._optimistic_group_state: str | None = None
        self._optimistic_group_members: list[str] | None = None

        # Timestamps for optimistic state timeout (10 seconds)
        self._optimistic_state_timestamp: float | None = None
        self._optimistic_group_timestamp: float | None = None

        # Track info for album art cache management
        self._last_track_info: dict[str, Any] = {}

        # Track previous role for source handling
        self._previous_role: str | None = None

        # HA convention: Use device name as entity name
        self._attr_name = None

        # Override unique_id to match raw speaker UUID (tests expect this)
        self._attr_unique_id = self.speaker.uuid

        # Debouncer for high-frequency volume changes (slider drags)
        #   • cooldown = 0.5 s  → at most 2 cmds / s
        #   • immediate = False → send after user stops moving slider
        self._pending_volume: float | None = None
        self._volume_debouncer: Debouncer = Debouncer(
            speaker.hass,
            _LOGGER,
            cooldown=0.5,
            immediate=False,
            function=self._send_volume_debounced,
        )

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
        _LOGGER.debug(
            "Media player %s registered with entity_id %s",
            self.speaker.name,
            self.entity_id,
        )

        # Listen for state updates from the speaker
        from homeassistant.helpers.dispatcher import async_dispatcher_connect

        dispatcher_signal = f"wiim_state_updated_{self.speaker.uuid}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                dispatcher_signal,
                self._handle_coordinator_update,
            )
        )

        # Debouncer already created in __init__; nothing to do here

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator data update."""
        self.async_schedule_update_ha_state()

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
                            "🎨 Media player clearing image cache due to URL change: %s -> %s",
                            old_val,
                            new_val,
                        )
                    elif key in ["title", "artist"]:
                        _LOGGER.debug(
                            "🎵 Media player detected %s change: %s -> %s",
                            key,
                            old_val,
                            new_val,
                        )

            # CRITICAL: Clear cache when track changes OR when image URL changes
            # WiiM devices often keep the same URL but change the image content
            if track_changed or image_url_changed:
                if track_changed and not image_url_changed and current_track_info.get("image_url"):
                    _LOGGER.debug(
                        "🎨 Media player forcing image cache clear - track changed but URL stayed same (WiiM behavior)"
                    )
                self.controller.clear_media_image_cache()

            self._last_track_info = current_track_info.copy()

        # Track role changes for source handling
        current_role = self.speaker.role
        if self._previous_role != current_role:
            _LOGGER.info(
                "Media player %s role changed: %s -> %s",
                self.name,
                self._previous_role,
                current_role,
            )
            self._previous_role = current_role
            # Force immediate state update when role changes
            self.async_write_ha_state()

        # Call parent to write state
        super().async_write_ha_state()

    async def _send_volume_debounced(self) -> None:
        """Send the pending volume after debounce period."""
        if self._pending_volume is None:
            _LOGGER.debug("Debounce called but no pending volume, ignoring")
            return

        volume = self._pending_volume
        self._pending_volume = None  # Clear pending

        _LOGGER.debug("Debounced volume command: %.2f", volume)
        await self.controller.set_volume(volume)

    # ===== HOME ASSISTANT ENTITY PROPERTIES =====

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features supported by WiiM API, with conditional seek."""
        # Enable ALL features that WiiM API supports per design guide
        features = (
            # Volume & Mute (API: vol, mute)
            MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.VOLUME_STEP
            # Playback Control (API: status, curpos, totlen)
            | MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.STOP
            # Track Navigation (API: next/prev commands)
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
            # Sources & EQ (API: mode, eq)
            | MediaPlayerEntityFeature.SELECT_SOURCE
            | MediaPlayerEntityFeature.SELECT_SOUND_MODE
            # Shuffle & Repeat (API: loop_mode bit flags)
            | MediaPlayerEntityFeature.SHUFFLE_SET
            | MediaPlayerEntityFeature.REPEAT_SET
            # Media Playback (API: supports URLs and streams)
            | MediaPlayerEntityFeature.PLAY_MEDIA
            # TTS Announcements (API: supports TTS via media sources)
            | MediaPlayerEntityFeature.MEDIA_ANNOUNCE
            # Multiroom Grouping (API: multiroom commands)
            | MediaPlayerEntityFeature.GROUPING
            # Media Browsing (API: preset navigation)
            | MediaPlayerEntityFeature.BROWSE_MEDIA
        )

        # Only enable seek when we have actual duration data
        # Streaming services like Amazon Music provide position but not duration due to DRM
        duration = self.media_duration
        if duration and duration > 0:
            features |= MediaPlayerEntityFeature.SEEK

        # Debug logging for group join issue
        if not hasattr(self, "_debug_logged_features"):
            _LOGGER.info(
                "WiiM %s supported features: %s (GROUPING: %s, Available: %s, State: %s)",
                self.speaker.name,
                features,
                bool(features & MediaPlayerEntityFeature.GROUPING),
                self.available,
                self.state,
            )
            self._debug_logged_features = True

        return features

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Check speaker availability first
        speaker_available = bool(getattr(self.speaker, "_available", True))

        # Check coordinator availability - be more lenient for grouping functionality
        coordinator = getattr(self.speaker, "coordinator", None)
        if coordinator is None:
            # No coordinator means device is offline/unavailable
            return False

        coordinator_success = bool(getattr(coordinator, "last_update_success", True))

        # Entity is available if speaker is available AND coordinator is working
        # This ensures group join controls are visible when the device is reachable
        return speaker_available and coordinator_success

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
    def state(self) -> MediaPlayerState | None:
        """State of the media player.

        Shows real device state immediately - no smoothing or filtering.
        Optimistic state provides immediate feedback for user commands.
        """
        # Check availability first - if device is offline, return None
        if not self.available:
            return None  # Device offline - let HA show as unavailable

        # Use optimistic state if available for immediate feedback
        if self._optimistic_state is not None:
            return self._optimistic_state

        # Show real device state immediately - no smoothing needed
        return self.controller.get_playback_state()

    # ===== SOURCE PROPERTIES (delegate to controller) =====

    @property
    def source(self) -> str | None:
        """Name of the current input source."""
        # Use optimistic state if available for immediate feedback
        if self._optimistic_source is not None:
            result = self._optimistic_source
            _LOGGER.debug(
                "[DEBUG] %s: source property (optimistic) - result=%s",
                self.speaker.name,
                result,
            )
            return result

        # Check for role transition from slave to solo
        current_role = self.speaker.role
        if (
            self._previous_role == "slave"
            and current_role == "solo"
            and self.controller.get_current_source() == "Follower"
        ):
            # Speaker just ungrouped from slave to solo, show unknown instead of Follower
            result = "unknown"
            _LOGGER.debug(
                "[DEBUG] %s: source property (role transition) - result=%s",
                self.speaker.name,
                result,
            )
            return result

        result = self.controller.get_current_source()
        _LOGGER.debug(
            "[DEBUG] %s: source property (normal) - result=%s",
            self.speaker.name,
            result,
        )
        return result

    @property
    def source_list(self) -> list[str]:
        """List of available input sources."""
        result = self.controller.get_source_list()
        _LOGGER.debug(
            "[DEBUG] %s: source_list property - result=%s",
            self.speaker.name,
            result,
        )
        return result

    @property
    def sound_mode(self) -> str | None:
        """Name of the current sound mode."""
        return self.controller.get_sound_mode()

    @property
    def sound_mode_list(self) -> list[str]:
        """List of available sound modes."""
        return self.controller.get_sound_mode_list()

    @property
    def media_content_source(self) -> str | None:
        """Return the content source (streaming service name)."""
        result = self.get_app_name()
        _LOGGER.debug(
            "[DEBUG] %s: media_content_source property - result=%s",
            self.speaker.name,
            result,
        )
        return result

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
    def media_content_id(self) -> str | None:
        """Content ID of current playing media."""
        # Return the current source as the content ID
        result = self.get_app_name()
        _LOGGER.debug(
            "[DEBUG] %s: media_content_id property - result=%s",
            self.speaker.name,
            result,
        )
        return result

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
        position = self.controller.get_media_position()
        # Ensure position is valid (non-negative integer)
        if position is not None and isinstance(position, int | float) and position >= 0:
            return int(position)
        return None

    @property
    def media_position_updated_at(self) -> datetime.datetime | None:
        """When the position was last updated."""
        # Only return timestamp if entity is available
        if not self.available:
            return None

        # Ensure we always return a valid timestamp for Music Assistant compatibility
        timestamp = self.controller.get_media_position_updated_at()
        if timestamp is None:
            from homeassistant.util.dt import utcnow as _utcnow

            return _utcnow()

        # Convert Unix timestamp to datetime object
        from homeassistant.util.dt import utc_from_timestamp as _utc_from_timestamp

        result = _utc_from_timestamp(timestamp)
        return result

    @property
    def elapsed_time_last_updated(self) -> str | None:
        """ISO format timestamp when the elapsed time was last updated.

        This attribute is required by Music Assistant's hass_players provider.
        Returns an ISO format datetime string that can be parsed by fromisoformat().
        """
        # Only return timestamp if entity is available
        if not self.available:
            return None

        timestamp = self.controller.get_media_position_updated_at()
        if timestamp is None:
            import time as _time

            timestamp = _time.time()

        # Convert timestamp to ISO format string
        from datetime import datetime, timezone

        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)  # noqa: UP017
        return dt.isoformat()

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

    @property
    def media_image_hash(self) -> str | None:
        """Hash value for media image.

        WiiM devices often keep the same image URL but change the image content when
        tracks change. We create a hash based on both URL and track metadata to ensure
        Home Assistant's image cache updates when the track changes.
        """
        url = self.media_image_url
        if not url:
            return None

        # Include track metadata in hash to force cache refresh when track changes
        # even if URL stays the same (common WiiM behavior)
        track_info = f"{url}|{self.media_title}|{self.media_artist}|{self.media_album_name}"

        import hashlib

        return hashlib.sha256(track_info.encode("utf-8")).hexdigest()[:16]

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
        # Use optimistic state if available, otherwise use real state
        if self._optimistic_group_members is not None:
            return self._optimistic_group_members
        return self.controller.get_group_members()

    @property
    def group_state(self) -> str:
        """Current group state (solo, master, slave)."""
        # Use optimistic state if available, otherwise use real state
        if self._optimistic_group_state is not None:
            return self._optimistic_group_state
        return self.speaker.role

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
        self._optimistic_group_state = None
        self._optimistic_group_members = None

    async def _async_execute_command_with_immediate_refresh(self, command_name: str) -> None:
        """Execute command with immediate polling for fast UI updates.

        This provides much better UX than waiting 5 seconds for next poll cycle.
        """
        _LOGGER.debug(
            "Command '%s' completed, requesting immediate refresh for %s",
            command_name,
            self.speaker.name,
        )

        # Clear any previous command failures since this command succeeded
        if hasattr(self.speaker.coordinator, "clear_command_failures"):
            self.speaker.coordinator.clear_command_failures()

        # Request immediate coordinator refresh instead of waiting for next 5s cycle
        await self.coordinator.async_request_refresh()

        # DO NOT clear optimistic state immediately - let it persist until we get
        # real data from the device that confirms the state change. This prevents
        # the UI from flickering back to the old state before the device responds.

    # ===== VOLUME COMMANDS (provided by VolumeCommandsMixin) =====

    # ===== PLAYBACK COMMANDS (provided by PlaybackCommandsMixin) =====

    # ===== SOURCE COMMANDS (provided by SourceCommandsMixin) =====

    # ===== GROUP COMMANDS (provided by GroupCommandsMixin) =====

    # ===== MEDIA COMMANDS (provided by MediaCommandsMixin) =====

    # ===== ADDITIONAL WIIM SERVICES =====

    async def async_play_playlist(self, playlist_url: str) -> None:
        """Play an M3U playlist."""
        try:
            # Use the existing play_url method for playlists
            await self.async_play_url(playlist_url)
        except Exception as err:
            _LOGGER.error("Failed to play playlist for %s: %s", self.speaker.name, err)
            raise

    async def async_set_eq(self, preset: str, custom_values: list[float] | None = None) -> None:
        """Set equalizer preset or custom values."""
        controller: MediaPlayerController = self.controller

        try:
            if preset == "custom" and custom_values is not None:
                # For custom EQ, we need to use the API client directly
                # since the controller doesn't have set_eq_custom
                if len(custom_values) != 10:
                    raise ValueError("Custom EQ values must be exactly 10 bands")
                for value in custom_values:
                    if not -12 <= value <= 12:
                        raise ValueError("EQ values must be between -12 and +12 dB")

                # Use the API client directly for custom EQ
                await self.speaker.coordinator.client.set_eq_custom(custom_values)
            else:
                # Use the existing controller method for presets
                await controller.set_eq_preset(preset)

        except Exception as err:
            _LOGGER.error("Failed to set EQ for %s: %s", self.speaker.name, err)
            raise

    async def async_play_notification(self, url: str) -> None:
        """Play a notification sound."""
        try:
            # Use the existing play_url method for notifications
            await self.async_play_url(url)
        except Exception as err:
            _LOGGER.error("Failed to play notification for %s: %s", self.speaker.name, err)
            raise

    async def async_reboot_device(self) -> None:
        """Reboot the WiiM device."""
        try:
            # Use the API client directly for reboot
            await self.speaker.coordinator.client.reboot()
            _LOGGER.info("Reboot command sent successfully to %s", self.speaker.name)
        except Exception as err:
            # Reboot commands often don't return proper responses
            # Log the attempt but don't fail the service call
            _LOGGER.info(
                "Reboot command sent to %s (device may not respond): %s",
                self.speaker.name,
                err,
            )
            # Don't raise - reboot command was sent successfully
            # The device will reboot even if the response parsing fails

    async def async_sync_time(self) -> None:
        """Synchronize device time with Home Assistant."""
        try:
            # Use the API client directly for time sync
            await self.speaker.coordinator.client.sync_time()
        except Exception as err:
            _LOGGER.error("Failed to sync time for %s: %s", self.speaker.name, err)
            raise

    # ===== APP NAME PROPERTY (delegate to mixin) =====

    @property
    def app_name(self) -> str | None:
        """Return the name of the current streaming service."""
        result = self.get_app_name()
        _LOGGER.debug(
            "[DEBUG] %s: app_name property - result=%s",
            self.speaker.name,
            result,
        )
        return result

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attrs = {
            "device_model": self.speaker.model,
            "firmware_version": self.speaker.firmware,
            "ip_address": self.speaker.ip_address,
            "mac_address": self.speaker.mac_address,
            "group_role": self.speaker.role,
            "is_group_coordinator": self.speaker.is_group_coordinator,
            # Music Assistant compatibility attributes
            "music_assistant_compatible": True,
            "integration_purpose": "individual_speaker_control",
            # Audio output status
            "bluetooth_output_active": self.speaker.is_bluetooth_output_active(),
            "hardware_output_mode": self.speaker.get_hardware_output_mode(),
            "audio_cast_active": self.speaker.is_audio_cast_active(),
        }

        # Add group info if in a group
        if self.speaker.role in ["master", "slave"]:
            attrs["group_members"] = self.group_members
            attrs["group_state"] = self.group_state
            if self.speaker.coordinator_speaker:
                attrs["group_coordinator"] = self.speaker.coordinator_speaker.name

        # Add playback info
        if self.state == MediaPlayerState.PLAYING:
            attrs["playback_progress"] = f"{self.media_position or 0}/{self.media_duration or 0}"

        return attrs
