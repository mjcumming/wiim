"""WiiM media player platform - minimal integration using pywiim."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import Any

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_ENQUEUE,
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaPlayerEnqueue,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.components.media_player.browse_media import async_process_play_media_url
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util
from pywiim.exceptions import WiiMConnectionError, WiiMError, WiiMTimeoutError

from .const import CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP, DOMAIN
from .data import Speaker, find_speaker_by_uuid, get_speaker_from_config_entry
from .entity import WiimEntity
from .group_media_player import WiiMGroupMediaPlayer

_LOGGER = logging.getLogger(__name__)

# Streaming sources that don't support next/previous track
STREAMING_SOURCES = ["wifi", "webradio", "iheartradio", "pandora", "tunein"]


def _is_connection_error(err: Exception) -> bool:
    """Check if error is a connection or timeout error (including in exception chain)."""
    if isinstance(err, (WiiMConnectionError, WiiMTimeoutError)):
        return True
    # Check exception chain for wrapped connection errors
    cause = getattr(err, "__cause__", None)
    if cause and isinstance(cause, (WiiMConnectionError, WiiMTimeoutError)):
        return True
    # Check for TimeoutError in chain (common underlying cause)
    if isinstance(err, TimeoutError):
        return True
    if cause and isinstance(cause, TimeoutError):
        return True
    return False


def media_source_filter(item: BrowseMedia) -> bool:
    """Filter media items to include audio and DLNA sources."""
    content_type = item.media_content_type
    # Include audio content types
    if content_type and content_type.startswith("audio/"):
        return True
    # Include DLNA sources (they use MediaType.CHANNEL/CHANNELS)
    if content_type in (MediaType.CHANNEL, MediaType.CHANNELS):
        return True
    return False


def _capitalize_source_name(source: str) -> str:
    """Capitalize source name properly (Amazon, USB, etc.).

    Handles common source names that need special capitalization:
    - amazon -> Amazon
    - usb -> USB
    - bluetooth -> Bluetooth
    - airplay -> AirPlay
    - spotify -> Spotify
    - etc.
    """
    source_lower = source.lower()

    # Special cases for proper capitalization
    special_cases = {
        "amazon": "Amazon",
        "usb": "USB",
        "bluetooth": "Bluetooth",
        "airplay": "AirPlay",
        "spotify": "Spotify",
        "tidal": "Tidal",
        "qobuz": "Qobuz",
        "deezer": "Deezer",
        "pandora": "Pandora",
        "iheartradio": "iHeartRadio",
        "tunein": "TuneIn",
        "chromecast": "Chromecast",
        "dlna": "DLNA",
        "upnp": "UPnP",
        "wifi": "WiFi",
        "coax": "Coax",
        "optical": "Optical",
        "toslink": "TOSLINK",
        "spdif": "S/PDIF",
        "rca": "RCA",
        "aux": "Aux",
        "line": "Line",
        "hdmi": "HDMI",
    }

    # Check for exact match first
    if source_lower in special_cases:
        return special_cases[source_lower]

    # Check for partial matches (e.g., "usb audio" -> "USB Audio")
    for key, value in special_cases.items():
        if source_lower.startswith(key):
            # Replace the matched part with capitalized version
            return value + source[len(key) :].title()

    # Default: title case (first letter of each word capitalized)
    return source.title()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM Media Player platform."""
    speaker = get_speaker_from_config_entry(hass, config_entry)
    # Create both individual media player and virtual group coordinator
    async_add_entities(
        [
            WiiMMediaPlayer(speaker),
            WiiMGroupMediaPlayer(speaker),
        ]
    )


class WiiMMediaPlayer(WiimEntity, MediaPlayerEntity):
    """WiiM media player entity - minimal integration using pywiim."""

    def __init__(self, speaker: Speaker) -> None:
        """Initialize the media player."""
        super().__init__(speaker)
        self._attr_unique_id = speaker.uuid
        self._attr_name = None  # Use device name
        self._attr_media_content_id: str | None = None  # Track URL for scene restoration

    def _derive_state_from_player(self, player) -> MediaPlayerState | None:
        """Map pywiim's play_state to MediaPlayerState."""
        if not self.available or not player:
            return None

        play_state = getattr(player, "play_state", None)
        if not play_state:
            return MediaPlayerState.IDLE

        play_state_str = str(play_state).lower()
        if play_state_str in ("play", "playing", "load"):
            return MediaPlayerState.PLAYING
        if play_state_str == "pause":
            return MediaPlayerState.PAUSED
        return MediaPlayerState.IDLE

    def _update_position_from_coordinator(self) -> None:
        """Update media position attributes from coordinator data (LinkPlay pattern)."""
        player = self._get_metadata_player()
        if not player:
            self._attr_state = None
            self._attr_media_position = None
            self._attr_media_position_updated_at = None
            self._attr_media_duration = None
            return

        current_state = self._derive_state_from_player(player)
        self._attr_state = current_state

        # Get values from pywiim
        new_position = player.media_position
        # If duration is 0, return None (unknown) to avoid 00:00 display
        new_duration = player.media_duration if player.media_duration else None
        _LOGGER.debug(
            "[%s] Coordinator update (state=%s, raw_pos=%s, raw_dur=%s)",
            self.name,
            current_state,
            new_position,
            new_duration,
        )

        # Update duration (keep existing if new is invalid during playback)
        if new_duration:
            self._attr_media_duration = new_duration
        elif current_state == MediaPlayerState.IDLE:
            self._attr_media_duration = None
        # Else: Keep existing duration (don't clear on transient errors during playback)

        # Simple Position Update (Robust)
        if new_position is None:
            # Clear stale progress when the device hasn't reported a value yet (e.g., immediately after track change)
            self._attr_media_position = None
            self._attr_media_position_updated_at = None
        elif current_state == MediaPlayerState.PLAYING:
            self._attr_media_position = new_position
            self._attr_media_position_updated_at = dt_util.utcnow()
        elif current_state == MediaPlayerState.IDLE or current_state is None:
            self._attr_media_position = None
            self._attr_media_position_updated_at = None
        else:  # PAUSED or STOPPED
            self._attr_media_position = new_position
            # Freeze timestamp (don't update it, just keep the last one or let it be stale as it's unused in PAUSED)
            # Actually, LinkPlay clears it on STOPPED. We can keep it as is or set to None if it makes sense.
            # For PAUSED, we want to show the static position.

        _LOGGER.debug(
            "[%s] Published position=%s (ts=%s) duration=%s",
            self.name,
            self._attr_media_position,
            self._attr_media_position_updated_at,
            self._attr_media_duration,
        )

        # Update supported features (includes SEEK based on duration)
        self._update_supported_features()

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self.speaker.name

    def _is_streaming_source(self) -> bool:
        """Check if current source is a streaming source (radio/web stream).

        Checks multiple indicators:
        - Source name matches known streaming sources
        - Media title contains stream file extensions (.m3u8, .pls, .m3u)
        - No duration (streams typically don't have fixed duration)
        """
        player = self._get_player()
        if not player:
            return False

        # Check if source name matches known streaming sources
        if player.source:
            source_lower = str(player.source).lower()
            if source_lower in STREAMING_SOURCES:
                return True

        # Check media title for stream indicators
        if hasattr(player, "media_title") and player.media_title:
            title_lower = str(player.media_title).lower()
            # Check for common stream file extensions
            stream_extensions = [".m3u8", ".m3u", ".pls", ".asx"]
            if any(ext in title_lower for ext in stream_extensions):
                return True

        # Check if no duration (streams typically don't have fixed duration)
        # But only if we're actually playing something
        if self.state in (MediaPlayerState.PLAYING, MediaPlayerState.PAUSED):
            if not self.media_duration or self.media_duration == 0:
                # Additional check: if source is wifi and no duration, likely a stream
                if player.source and str(player.source).lower() == "wifi":
                    return True

        return False

    def _update_supported_features(self) -> None:
        """Update supported features based on current state (LinkPlay pattern)."""
        # Check if player is a slave in a multiroom group
        player = self._get_player()
        is_slave = player.is_slave if player else False

        # Base features available to all players (including slaves)
        features = (
            MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.STOP
        )

        # Slaves don't control their own playback/sources - master controls everything
        # Only add these features if not a slave
        if not is_slave:
            features |= (
                MediaPlayerEntityFeature.SELECT_SOURCE
                | MediaPlayerEntityFeature.PLAY_MEDIA
                | MediaPlayerEntityFeature.BROWSE_MEDIA
                | MediaPlayerEntityFeature.MEDIA_ANNOUNCE
                | MediaPlayerEntityFeature.CLEAR_PLAYLIST
            )

        # Exclude next/previous track for streaming sources (radio/web streams)
        # Slaves also shouldn't have track control (master controls that)
        if not self._is_streaming_source() and not is_slave:
            features |= MediaPlayerEntityFeature.NEXT_TRACK
            features |= MediaPlayerEntityFeature.PREVIOUS_TRACK

        # Always include grouping feature so players appear in join dialog
        # Slaves can be joined by masters, but cannot initiate joins themselves
        # The role check is enforced in async_join_players() to prevent slaves from initiating joins
        features |= MediaPlayerEntityFeature.GROUPING

        # Only include shuffle/repeat if pywiim says they're supported and not a slave
        if not is_slave:
            if self._shuffle_supported():
                features |= MediaPlayerEntityFeature.SHUFFLE_SET
            if self._repeat_supported():
                features |= MediaPlayerEntityFeature.REPEAT_SET

        # Enable EQ (sound mode) only if device supports it and not a slave
        if not is_slave and self._is_eq_supported():
            features |= MediaPlayerEntityFeature.SELECT_SOUND_MODE

        # Enable seek if we have duration and not a slave
        # Use _attr_media_duration (set during coordinator update) not property
        if not is_slave and self._attr_media_duration and self._attr_media_duration > 0:
            features |= MediaPlayerEntityFeature.SEEK

        # Enable queue management if UPnP client is available and not a slave
        if not is_slave and self._has_queue_support():
            features |= MediaPlayerEntityFeature.MEDIA_ENQUEUE

        self._attr_supported_features = features

    def _is_eq_supported(self) -> bool:
        """Check if device supports EQ - query from pywiim.

        pywiim detects EQ support during capability detection and caches it in
        player.client.capabilities["supports_eq"]. The coordinator stores this
        in _capabilities for the integration to use.
        """
        if hasattr(self.coordinator, "_capabilities") and self.coordinator._capabilities:
            return bool(self.coordinator._capabilities.get("supports_eq", False))
        return False

    def _has_queue_support(self) -> bool:
        """Check if queue management is available - query from Player."""
        if not hasattr(self.coordinator, "player") or self.coordinator.player is None:
            return False
        # Check if Player has UPnP client (required for queue management)
        return hasattr(self.coordinator.player, "_upnp_client") and self.coordinator.player._upnp_client is not None

    async def _ensure_upnp_ready(self) -> None:
        """Ensure UPnP client is available when queue management is requested."""
        # PyWiim handles UPnP internally - just check if it's available
        if not self._has_queue_support():
            raise HomeAssistantError(
                "Queue management not available. The device may not support UPnP or it may not be initialized yet."
            )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.speaker.available and self.coordinator.last_update_success

    def _get_player(self):
        """Get Player object from coordinator data (always up-to-date via pywiim)."""
        if self.coordinator.data:
            return self.coordinator.data.get("player")
        return None

    # ===== STATE =====

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the current state."""
        if self._attr_state is not None:
            return self._attr_state

        player = self._get_player()
        return self._derive_state_from_player(player)

    # ===== VOLUME =====

    @property
    def volume_level(self) -> float | None:
        """Return volume level 0..1 (already converted by Player)."""
        player = self._get_player()
        return player.volume_level if player else None

    @property
    def volume_step(self) -> float:
        """Return the step to be used by the volume_up and volume_down services.

        Reads the configured volume step from the config entry options.
        Defaults to 5% (0.05) if not configured.
        """
        if hasattr(self, "speaker") and hasattr(self.speaker, "config_entry") and self.speaker.config_entry is not None:
            volume_step = self.speaker.config_entry.options.get(CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP)
            return float(volume_step)
        return DEFAULT_VOLUME_STEP

    @property
    def is_volume_muted(self) -> bool | None:
        """Return True if muted."""
        player = self._get_player()
        return player.is_muted if player else None

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level 0..1."""
        try:
            await self.coordinator.player.set_volume(volume)
            await self.coordinator.async_request_refresh()
        except WiiMError as err:
            if _is_connection_error(err):
                # Connection/timeout errors are transient - log at warning level
                _LOGGER.warning(
                    "Connection issue setting volume on %s: %s. The device may be temporarily unreachable.",
                    self.name,
                    err,
                )
                raise HomeAssistantError(
                    f"Unable to set volume on {self.name}: device temporarily unreachable"
                ) from err
            # Other errors are actual problems - log at error level
            _LOGGER.error("Failed to set volume on %s: %s", self.name, err, exc_info=True)
            raise HomeAssistantError(f"Failed to set volume: {err}") from err

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute/unmute volume."""
        try:
            await self.coordinator.player.set_mute(mute)
            await self.coordinator.async_request_refresh()
        except WiiMError as err:
            if _is_connection_error(err):
                # Connection/timeout errors are transient - log at warning level
                _LOGGER.warning(
                    "Connection issue setting mute on %s: %s. The device may be temporarily unreachable.",
                    self.name,
                    err,
                )
                raise HomeAssistantError(f"Unable to set mute on {self.name}: device temporarily unreachable") from err
            # Other errors are actual problems - log at error level
            _LOGGER.error("Failed to set mute on %s: %s", self.name, err, exc_info=True)
            raise HomeAssistantError(f"Failed to set mute: {err}") from err

    # ===== PLAYBACK =====

    async def async_media_play(self) -> None:
        """Start playback."""
        try:
            await self.coordinator.player.play()
            await self.coordinator.async_request_refresh()
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to start playback: {err}") from err

    async def async_media_pause(self) -> None:
        """Pause playback."""
        try:
            await self.coordinator.player.pause()
            await self.coordinator.async_request_refresh()
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to pause playback: {err}") from err

    async def async_media_play_pause(self) -> None:
        """Toggle play/pause."""
        try:
            await self.coordinator.player.media_play_pause()
            await self.coordinator.async_request_refresh()
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to toggle play/pause: {err}") from err

    async def async_media_stop(self) -> None:
        """Stop playback.

        For web radio streams, uses pause instead of stop as stop doesn't work reliably
        due to device firmware behavior.
        """
        player = self._get_player()
        if not player:
            raise HomeAssistantError("Player is not available")

        try:
            # Use pause for web streams (stop doesn't work reliably)
            if self._is_streaming_source():
                await player.pause()
            else:
                await player.stop()
                # Clear media_content_id when stopped (not paused, as pause preserves state)
                self._attr_media_content_id = None
            await self.coordinator.async_request_refresh()
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to stop playback: {err}") from err

    async def async_media_next_track(self) -> None:
        """Skip to next track."""
        try:
            await self.coordinator.player.next_track()
            await self.coordinator.async_request_refresh()
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to skip to next track: {err}") from err

    async def async_media_previous_track(self) -> None:
        """Skip to previous track."""
        try:
            await self.coordinator.player.previous_track()
            await self.coordinator.async_request_refresh()
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to skip to previous track: {err}") from err

    async def async_media_seek(self, position: float) -> None:
        """Seek to position in seconds."""
        _LOGGER.debug(
            "%s: Seeking to position %s (duration=%s, supported_features has SEEK=%s)",
            self.name,
            position,
            self._attr_media_duration,
            bool(self._attr_supported_features & MediaPlayerEntityFeature.SEEK),
        )
        try:
            await self.coordinator.player.seek(int(position))
            # Force immediate coordinator refresh to get new position
            await self.coordinator.async_request_refresh()
        except WiiMError as err:
            _LOGGER.error("%s: Seek failed: %s", self.name, err)
            raise HomeAssistantError(f"Failed to seek: {err}") from err

    # ===== SOURCE =====

    @property
    def source(self) -> str | None:
        """Return current source (properly capitalized for display).

        Ensures the returned source matches an item in source_list so the dropdown
        can correctly show the selected source. If the current source from pywiim
        doesn't match any selectable source, returns None.
        """
        player = self._get_player()
        if not player or not player.source:
            return None

        # Get the current source from pywiim and capitalize it
        current_source = _capitalize_source_name(str(player.source))

        # Get the list of available sources to ensure we return a match
        available_sources = getattr(player, "available_sources", None)
        if available_sources:
            # Create a mapping of capitalized names for matching
            capitalized_sources = {
                _capitalize_source_name(str(s)): _capitalize_source_name(str(s)) for s in available_sources
            }
            # Try exact match first
            if current_source in capitalized_sources:
                return current_source
            # Try case-insensitive match
            current_lower = current_source.lower()
            for cap_source in capitalized_sources:
                if cap_source.lower() == current_lower:
                    return cap_source

        # Fallback: check against input_list
        input_list = self.speaker.input_list
        if input_list:
            capitalized_inputs = {_capitalize_source_name(str(s)): _capitalize_source_name(str(s)) for s in input_list}
            if current_source in capitalized_inputs:
                return current_source
            # Try case-insensitive match
            current_lower = current_source.lower()
            for cap_input in capitalized_inputs:
                if cap_input.lower() == current_lower:
                    return cap_input

        # If current source doesn't match any selectable source, log a warning
        # This might indicate a pywiim issue where source doesn't match available_sources
        _LOGGER.debug(
            "[%s] Current source '%s' from pywiim doesn't match any selectable source in source_list. "
            "This might indicate a pywiim issue. available_sources=%s, input_list=%s",
            self.name,
            current_source,
            available_sources,
            input_list,
        )
        # Return None so dropdown doesn't show incorrect selection
        return None

    @property
    def source_list(self) -> list[str]:
        """Return list of available sources from Player.

        Uses available_sources from pywiim which should filter to only selectable sources.
        """
        player = self._get_player()
        if not player:
            return []

        # Get available_sources directly from Player object
        available_sources = getattr(player, "available_sources", None)
        if available_sources:
            capitalized = [_capitalize_source_name(str(s)) for s in available_sources]
            return capitalized

        # Fallback to input_list if available_sources not available
        input_list = self.speaker.input_list
        if input_list:
            capitalized = [_capitalize_source_name(str(s)) for s in input_list]
            return capitalized

        _LOGGER.warning(
            "[%s] source_list: No sources available - available_sources=%s, input_list=%s",
            self.name,
            available_sources,
            input_list,
        )
        return []

    async def async_select_source(self, source: str) -> None:
        """Select input source.

        Maps the display name (e.g., "Amazon", "USB") back to the device's
        expected source name (e.g., "amazon", "usb") using available_sources or input_list.
        """
        source_lower = source.lower()
        device_source = None

        # Try available_sources first (smart detection by pywiim)
        player = self._get_player()
        if player:
            available_sources = getattr(player, "available_sources", None)
            if available_sources:
                # Create a mapping of lowercase to original
                available_sources_map = {str(s).lower(): str(s) for s in available_sources}
                device_source = available_sources_map.get(source_lower)

        # Fallback to input_list if not found in available_sources
        if device_source is None:
            input_list = self.speaker.input_list
            if input_list:
                # Create a mapping of lowercase to original
                input_list_map = {s.lower(): s for s in input_list}
                device_source = input_list_map.get(source_lower)

        # Final fallback: use lowercase version of display name
        if device_source is None:
            device_source = source_lower
            _LOGGER.warning(
                "Source '%s' not found in available_sources or input_list, using lowercase version: '%s'",
                source,
                device_source,
            )

        try:
            await self.coordinator.player.set_source(device_source)
            # Clear media_content_id when source changes (new source may not be a URL)
            self._attr_media_content_id = None
            await self.coordinator.async_request_refresh()
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to select source '{source}': {err}") from err

    # ===== MEDIA =====

    @property
    def media_content_type(self) -> MediaType:
        """Return content type."""
        return MediaType.MUSIC

    @property
    def media_content_id(self) -> str | None:
        """Return the content ID (URL) of currently playing media.

        This is used by Home Assistant for scene restoration. When a URL is played
        via async_play_media(), we store it here so scenes can restore it.

        Returns the URL if we have one tracked and the player is in a state where
        media could be playing (PLAYING or PAUSED). This allows scenes to restore
        the URL that was playing when the scene was saved.
        """
        # Only return URL if we're in a state where media could be playing
        if self.state not in (MediaPlayerState.PLAYING, MediaPlayerState.PAUSED):
            return None

        # Return tracked URL if available
        # This will be set when async_play_media() is called with a URL
        return self._attr_media_content_id

    @property
    def media_title(self) -> str | None:
        """Return media title."""
        player = self._get_metadata_player()
        return player.media_title if player else None

    @property
    def media_artist(self) -> str | None:
        """Return media artist."""
        player = self._get_metadata_player()
        return player.media_artist if player else None

    @property
    def media_album_name(self) -> str | None:
        """Return media album."""
        player = self._get_metadata_player()
        return player.media_album if player else None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_position_from_coordinator()

        # Clear media_content_id if state becomes IDLE (nothing playing)
        # This handles cases where playback stops externally (not via our stop method)
        if self.state == MediaPlayerState.IDLE:
            self._attr_media_content_id = None

        super()._handle_coordinator_update()

    # Properties now use _attr values set during coordinator update
    # No mutation in property getters - following LinkPlay pattern

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media.

        Returns a placeholder URL to ensure Home Assistant calls async_get_media_image(),
        which allows pywiim to serve its default WiiM logo when nothing is playing
        or no cover art is available.
        """
        player = self._get_metadata_player()
        if not player:
            return None

        # If pywiim has a URL, use it
        if hasattr(player, "media_image_url") and player.media_image_url:
            return player.media_image_url

        # Always return a placeholder URL to trigger async_get_media_image()
        # This ensures HA calls our override in all states (including IDLE)
        # When nothing is playing, pywiim can serve its default WiiM logo
        import hashlib

        # Create a unique identifier based on current state and metadata
        title = self.media_title or ""
        artist = self.media_artist or ""
        state = str(self.state or "idle")

        # Use state + metadata to generate hash, ensuring it changes when track/state changes
        track_id = f"{state}|{title}|{artist}".encode()
        track_hash = hashlib.sha256(track_id).hexdigest()[:16]
        return f"wiim://cover-art/{track_hash}"

    @property
    def media_image_hash(self) -> str | None:
        """Hash value for media image.

        Uses state and track metadata to generate a hash that changes when
        track or state changes, ensuring Home Assistant fetches new cover art.
        """
        player = self._get_metadata_player()
        if not player:
            return None

        # If we have a URL from pywiim, hash it using the same method as HA base class
        if hasattr(player, "media_image_url") and player.media_image_url:
            import hashlib

            return hashlib.sha256(player.media_image_url.encode("utf-8")).hexdigest()[:16]

        # Always create hash from state and metadata (including IDLE state)
        # This ensures cover art updates when state changes (e.g., IDLE -> PLAYING)
        import hashlib

        title = self.media_title or ""
        artist = self.media_artist or ""
        album = self.media_album_name or ""
        state = str(self.state or "idle")

        track_id = f"{state}|{title}|{artist}|{album}".encode()
        return hashlib.sha256(track_id).hexdigest()[:16]

    @property
    def media_image_remotely_accessible(self) -> bool:
        """Return False to force Home Assistant to use our async_get_media_image() override.

        Per pywiim HA integration guide: using fetch_cover_art() is more reliable than
        passing URLs directly to HA, especially for handling expired URLs and caching.
        """
        return False

    async def async_get_media_image(self) -> tuple[bytes | None, str | None]:
        """Return image bytes and content type of current playing media.

        Per pywiim HA integration guide: fetch_cover_art() provides more reliable
        cover art serving with automatic caching and graceful handling of expired URLs.
        """
        _LOGGER.debug("async_get_media_image() called for %s", self.name)

        player = self._get_metadata_player()
        if not player:
            _LOGGER.debug("No player object available for cover art fetch")
            return None, None

        # Check what URL pywiim has (read directly from Player object)
        cover_art_url = player.media_image_url if hasattr(player, "media_image_url") else None
        _LOGGER.debug(
            "Cover art URL from player.media_image_url: %s (source: %s, state: %s)",
            cover_art_url,
            getattr(player, "source", None),
            self.state,
        )

        # Check if fetch_cover_art method exists
        if not hasattr(player, "fetch_cover_art"):
            _LOGGER.warning(
                "Player object does not have fetch_cover_art method - this may indicate a pywiim version issue"
            )
            # If we have a URL but no fetch method, we could return None to let HA handle it
            # But since media_image_remotely_accessible is False, HA will call this method
            return None, None

        try:
            _LOGGER.debug("Calling player.fetch_cover_art() for %s", self.name)
            result = await player.fetch_cover_art()
            if result and len(result) >= 2:
                image_bytes, content_type = result[0], result[1]
                if image_bytes and len(image_bytes) > 0:
                    _LOGGER.debug("Cover art fetched successfully: %d bytes, type=%s", len(image_bytes), content_type)
                    return result  # (image_bytes, content_type)
                else:
                    _LOGGER.debug("fetch_cover_art() returned empty image bytes")
            else:
                _LOGGER.debug(
                    "fetch_cover_art() returned None or invalid result - no cover art available. URL was: %s",
                    cover_art_url,
                )
        except AttributeError as e:
            _LOGGER.error("fetch_cover_art() method exists but raised AttributeError - possible pywiim issue: %s", e)
        except WiiMError as e:
            _LOGGER.warning("WiiM error fetching cover art (may be normal if no cover art available): %s", e)
        except Exception as e:
            _LOGGER.error("Unexpected error fetching cover art: %s", e, exc_info=True)

        return None, None

    async def async_play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        """Play media from URL or preset with optional queue management."""
        # Validate media_id is not empty
        if not media_id:
            raise HomeAssistantError("media_id cannot be empty")

        # Check for announce parameter - uses device's built-in playPromptUrl endpoint
        # The device firmware automatically:
        # - Lowers current playback volume
        # - Plays the notification audio
        # - Restores volume after completion
        # No state management needed - device handles it all
        announce = kwargs.get(ATTR_MEDIA_ANNOUNCE, False)
        if announce:
            # Handle media_source resolution for announcements
            if media_source.is_media_source_id(media_id):
                original_media_id = media_id
                try:
                    sourced_media = await media_source.async_resolve_media(self.hass, media_id, self.entity_id)
                    media_id = sourced_media.url
                    if not media_id:
                        raise HomeAssistantError(f"Media source resolved to empty URL: {original_media_id}")
                    media_id = async_process_play_media_url(self.hass, media_id)
                except Exception as err:
                    _LOGGER.error("Failed to resolve media source for announcement: %s", err, exc_info=True)
                    raise HomeAssistantError(f"Failed to resolve media source: {err}") from err

            # Use device's built-in notification endpoint (playPromptUrl)
            # Device automatically handles volume ducking and restoration
            try:
                _LOGGER.debug("[%s] Playing notification via device firmware: %s", self.name, media_id)
                await self.coordinator.player.play_notification(media_id)
                await self.coordinator.async_request_refresh()
            except WiiMError as err:
                raise HomeAssistantError(f"Failed to play notification: {err}") from err
            return

        # Handle preset numbers (presets don't support queue management)
        if media_type == "preset":
            preset_num = int(media_id)
            try:
                await self.coordinator.player.play_preset(preset_num)
                # Clear media_content_id when playing preset (not a URL)
                self._attr_media_content_id = None
                await self.coordinator.async_request_refresh()
            except WiiMError as err:
                raise HomeAssistantError(f"Failed to play preset: {err}") from err
            return

        # Handle media_source
        if media_source.is_media_source_id(media_id):
            original_media_id = media_id
            _LOGGER.debug("Resolving media source: %s", original_media_id)
            try:
                sourced_media = await media_source.async_resolve_media(self.hass, media_id, self.entity_id)
                _LOGGER.debug(
                    "Resolved media source - url: %s, mime_type: %s", sourced_media.url, sourced_media.mime_type
                )
                media_id = sourced_media.url
                # Validate that we have a valid URL before processing
                if not media_id:
                    _LOGGER.error(
                        "Media source resolved to empty URL. Original media_id: %s, mime_type: %s",
                        original_media_id,
                        sourced_media.mime_type,
                    )
                    raise HomeAssistantError(
                        f"Media source resolved to empty URL for: {original_media_id}. "
                        f"This may indicate the media source is not playable or not properly configured."
                    )
                # Process URL to handle relative paths
                media_id = async_process_play_media_url(self.hass, media_id)
            except Exception as err:
                _LOGGER.error(
                    "Failed to resolve media source %s: %s",
                    original_media_id,
                    err,
                    exc_info=True,
                )
                raise HomeAssistantError(f"Failed to resolve media source: {err}") from err

        enqueue: MediaPlayerEnqueue | None = kwargs.get(ATTR_MEDIA_ENQUEUE)
        if enqueue and enqueue != MediaPlayerEnqueue.REPLACE:
            await self._ensure_upnp_ready()
            if enqueue == MediaPlayerEnqueue.ADD:
                try:
                    await self.coordinator.player.add_to_queue(media_id)
                except WiiMError as err:
                    raise HomeAssistantError(f"Failed to add media to queue: {err}") from err
                return
            if enqueue == MediaPlayerEnqueue.NEXT:
                try:
                    await self.coordinator.player.insert_next(media_id)
                except WiiMError as err:
                    raise HomeAssistantError(f"Failed to insert media into queue: {err}") from err
                return
            if enqueue == MediaPlayerEnqueue.PLAY:
                try:
                    await self.coordinator.player.play_url(media_id)
                    # Store URL for scene restoration
                    self._attr_media_content_id = media_id
                    await self.coordinator.async_request_refresh()
                except WiiMError as err:
                    raise HomeAssistantError(f"Failed to play media immediately: {err}") from err
                return

        try:
            await self.coordinator.player.play_url(media_id)
            # Store URL for scene restoration
            self._attr_media_content_id = media_id
            await self.coordinator.async_request_refresh()
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to play media: {err}") from err

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement media browsing."""
        # Handle media source browsing
        if media_content_id and media_source.is_media_source_id(media_content_id):
            return await media_source.async_browse_media(
                self.hass,
                media_content_id,
                content_filter=media_source_filter,
            )

        # Root level - show Presets directory and media sources
        if media_content_id is None or media_content_id == "":
            # Only show root if we don't have a specific content type
            if not media_content_type or media_content_type == "":
                children: list[BrowseMedia] = [
                    BrowseMedia(
                        title="Presets",
                        media_class=MediaClass.DIRECTORY,
                        media_content_id="",
                        media_content_type="presets",
                        can_play=False,
                        can_expand=True,
                    )
                ]
                # Add Home Assistant media sources (including DLNA if configured)
                with suppress(BrowseError):
                    browse = await media_source.async_browse_media(
                        self.hass,
                        None,
                        content_filter=media_source_filter,
                    )
                    # If domain is None, it's an overview of available sources
                    if browse.domain is None and browse.children:
                        children.extend(browse.children)
                    else:
                        children.append(browse)

                # If there's only one child, return it directly (skip root level)
                if len(children) == 1 and children[0].can_expand:
                    return await self.async_browse_media(
                        children[0].media_content_type,
                        children[0].media_content_id,
                    )

                return BrowseMedia(
                    title=self.speaker.name,
                    media_class=MediaClass.DIRECTORY,
                    media_content_id="",
                    media_content_type="",
                    can_play=False,
                    can_expand=True,
                    children=children,
                )

        # Presets directory - show individual presets (1-20)
        if media_content_type == "presets":
            preset_children: list[BrowseMedia] = []
            player = self._get_player()

            # Try to get preset names from pywiim if available
            preset_names: dict[int, str] = {}
            if player:
                # Check if pywiim provides preset information
                # First, try to get all presets at once (more efficient)
                if hasattr(player, "presets"):
                    presets = getattr(player, "presets", None)
                    if isinstance(presets, dict):
                        for preset_num, preset_info in presets.items():
                            if isinstance(preset_num, int) and 1 <= preset_num <= 20:
                                if isinstance(preset_info, dict) and "name" in preset_info:
                                    preset_names[preset_num] = preset_info["name"]
                                elif hasattr(preset_info, "name"):
                                    preset_names[preset_num] = preset_info.name
                    elif isinstance(presets, list):
                        for idx, preset_info in enumerate(presets, start=1):
                            if 1 <= idx <= 20:
                                if isinstance(preset_info, dict) and "name" in preset_info:
                                    preset_names[idx] = preset_info["name"]
                                elif hasattr(preset_info, "name"):
                                    preset_names[idx] = preset_info.name
                # Fallback: try get_preset method if available (slower, but works if presets attr not available)
                elif hasattr(player, "get_preset"):
                    # Fetch preset names for presets 1-20
                    # Use asyncio.gather for parallel fetching if possible
                    try:

                        async def fetch_preset(preset_num: int) -> tuple[int, str | None]:
                            try:
                                preset_info = await player.get_preset(preset_num)
                                if preset_info and hasattr(preset_info, "name"):
                                    return (preset_num, preset_info.name)
                                elif preset_info and isinstance(preset_info, dict) and "name" in preset_info:
                                    return (preset_num, preset_info["name"])
                            except Exception:
                                pass
                            return (preset_num, None)

                        # Fetch all presets in parallel
                        results = await asyncio.gather(*[fetch_preset(i) for i in range(1, 21)])
                        for preset_num, preset_name in results:
                            if preset_name:
                                preset_names[preset_num] = preset_name
                    except Exception:
                        # If parallel fetching fails, fall back to sequential
                        for preset_num in range(1, 21):
                            try:
                                preset_info = await player.get_preset(preset_num)
                                if preset_info and hasattr(preset_info, "name"):
                                    preset_names[preset_num] = preset_info.name
                                elif preset_info and isinstance(preset_info, dict) and "name" in preset_info:
                                    preset_names[preset_num] = preset_info["name"]
                            except Exception:
                                # If get_preset fails or preset doesn't exist, use fallback
                                pass

            # Show presets 1-20 (device dependent, but max is 20 per service definition)
            for preset_num in range(1, 21):
                # Use actual preset name if available, otherwise fallback to "Preset N"
                preset_title = preset_names.get(preset_num, f"Preset {preset_num}")
                preset_children.append(
                    BrowseMedia(
                        title=preset_title,
                        media_class=MediaClass.MUSIC,
                        media_content_id=str(preset_num),
                        media_content_type="preset",
                        can_play=True,
                        can_expand=False,
                    )
                )
            return BrowseMedia(
                title="Presets",
                media_class=MediaClass.DIRECTORY,
                media_content_id="",
                media_content_type="presets",
                can_play=False,
                can_expand=True,
                children=preset_children,
            )

        # Unknown content type
        return BrowseMedia(
            title=self.speaker.name,
            media_class=MediaClass.DIRECTORY,
            media_content_id="",
            media_content_type="",
            can_play=False,
            can_expand=False,
            children=[],
        )

    async def async_clear_playlist(self) -> None:
        """Clear the current playlist."""
        try:
            await self.coordinator.player.clear_playlist()
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to clear playlist: {err}") from err

    # ===== GROUPING =====

    @property
    def group_members(self) -> list[str] | None:
        """Return list of entity IDs in the current group - using pywiim Player.group."""
        player = self._get_player()
        if not player:
            return None

        # If solo, return None (not in a group)
        if player.is_solo:
            return None

        # Use PyWiim's group object - it already knows all the players
        group = player.group
        if not group:
            return None

        entity_registry = er.async_get(self.hass)
        members: list[str] = []

        # PyWiim's group.all_players gives us all players (master + slaves)
        for group_player in group.all_players:
            entity_id = self._entity_id_from_player(group_player, entity_registry)
            if entity_id and entity_id not in members:
                members.append(entity_id)

        return members if members else None

    def _get_metadata_player(self):
        """Return the player that should be used for metadata display."""
        player = self._get_player()
        if not player:
            return None
        # Slaves should use master's metadata - PyWiim's group.master has it
        if player.is_slave and player.group:
            master = getattr(player.group, "master", None)
            if master:
                return master
        return player

    @staticmethod
    def _entity_id_from_player(player_obj: Any, entity_registry: er.EntityRegistry) -> str | None:
        """Resolve entity_id for a pywiim Player object."""
        if not player_obj:
            return None

        member_uuid = getattr(player_obj, "uuid", None) or getattr(player_obj, "mac", None)
        if not member_uuid:
            return None

        return entity_registry.async_get_entity_id("media_player", DOMAIN, member_uuid)

    def join_players(self, group_members: list[str]) -> None:
        """Join other players to form a group (sync version - not used)."""
        # This is called by async_join_players in base class, but we override async_join_players
        # so this shouldn't be called. Raise error if it is.
        raise NotImplementedError("Use async_join_players instead")

    async def async_join_players(self, group_members: list[str]) -> None:
        """Join/unjoin players to match the requested group configuration.

        Delegates to pywiim to handle all group management - pywiim manages
        state changes, role updates, and group membership automatically.

        Note: pywiim 2.1.26+ automatically detects firmware version and selects
        the appropriate grouping mode (Wi-Fi Direct for Gen1 devices with firmware
        < v4.2.8020, Router mode for newer devices). Audio Pro Gen1 devices
        (A26, C10, C5a) are now supported.
        """
        entity_registry = er.async_get(self.hass)
        master_player = self.coordinator.player
        if master_player is None:
            raise HomeAssistantError("Master player is not ready")

        # Normalize: ensure self is included in group_members (self is always the master)
        current_entity_id = self.entity_id
        if current_entity_id not in group_members:
            group_members = [current_entity_id] + group_members

        # Get current group members
        current_group = set(self.group_members or [])
        requested_group = set(group_members)

        # Determine which players to add and which to remove
        to_add = requested_group - current_group
        to_remove = current_group - requested_group

        # Remove players that are no longer in the group (deselected in UI)
        # pywiim handles all state management via callbacks
        unjoin_tasks = []
        for entity_id in to_remove:
            if entity_id == current_entity_id:
                # Don't unjoin self (master)
                continue

            entity_entry = entity_registry.async_get(entity_id)
            if not entity_entry:
                _LOGGER.warning("Entity %s not found when unjoining from group", entity_id)
                continue

            speaker = find_speaker_by_uuid(self.hass, entity_entry.unique_id)
            if not speaker or not speaker.coordinator.player:
                _LOGGER.warning("Speaker not available for entity %s", entity_id)
                continue

            # pywiim handles leaving groups and updating state automatically
            unjoin_tasks.append(speaker.coordinator.player.leave_group())

        # Execute all unjoin operations in parallel
        if unjoin_tasks:
            unjoin_results = await asyncio.gather(*unjoin_tasks, return_exceptions=True)
            for result in unjoin_results:
                if isinstance(result, Exception):
                    _LOGGER.error("Failed to remove player from group: %s", result)

        # Add players that are newly selected
        # pywiim handles joining groups, role changes, and state updates automatically
        join_tasks = []
        for entity_id in to_add:
            if entity_id == current_entity_id:
                # Skip self (already the master)
                continue

            entity_entry = entity_registry.async_get(entity_id)
            if not entity_entry:
                _LOGGER.warning("Entity %s not found when joining group", entity_id)
                continue

            speaker = find_speaker_by_uuid(self.hass, entity_entry.unique_id)
            if not speaker or not speaker.coordinator.player:
                _LOGGER.warning("Speaker not available for entity %s", entity_id)
                continue

            # pywiim handles joining groups, including slaves leaving their current group
            # and becoming masters if needed - all state updates happen via callbacks
            join_tasks.append(speaker.coordinator.player.join_group(master_player))

        # Execute all join operations in parallel
        if join_tasks:
            join_results = await asyncio.gather(*join_tasks, return_exceptions=True)
            for result in join_results:
                if isinstance(result, Exception):
                    raise HomeAssistantError(f"Failed to add player to group: {result}") from result

    def unjoin_player(self) -> None:
        """Leave the current group (sync version - not used)."""
        # This is called by async_unjoin_player in base class, but we override async_unjoin_player
        # so this shouldn't be called. Raise error if it is.
        raise NotImplementedError("Use async_unjoin_player instead")

    async def async_unjoin_player(self) -> None:
        """Leave the current group.

        Calls pywiim's leave_group() regardless of player role (master/slave/solo).
        PyWiim handles the complexity of what that means for each role.
        """
        player = self._get_player()
        if not player:
            raise HomeAssistantError("Player is not ready")

        try:
            await player.leave_group()
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to leave group: {err}") from err

    # ===== SHUFFLE & REPEAT =====

    def _shuffle_supported(self) -> bool:
        """Check if shuffle is supported - query from pywiim Player."""
        player = self._get_player()
        if not player:
            return False
        # Use pywiim's shuffle_supported property (per integration guide)
        return bool(getattr(player, "shuffle_supported", True))

    @property
    def shuffle(self) -> bool | None:
        """Return True if shuffle is enabled."""
        # Read directly from Player object (always up-to-date via pywiim)
        player = self._get_player()
        if not player:
            return None

        shuffle = getattr(player, "shuffle", None)
        if shuffle is not None:
            # Convert string to bool if needed
            if isinstance(shuffle, bool):
                return shuffle
            shuffle_str = str(shuffle).lower()
            return shuffle_str in ("1", "true", "on", "yes", "shuffle")
        return None

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffle mode - pass through to pywiim."""
        try:
            await self.coordinator.player.set_shuffle(shuffle)
            # pywiim updates Player state immediately and pushes event via on_state_changed callback
            # The callback triggers async_update_listeners() which notifies all entities automatically
            # We also force a refresh to ensure UI update in case callback is delayed
            await self.coordinator.async_request_refresh()
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to set shuffle: {err}") from err

    def _repeat_supported(self) -> bool:
        """Check if repeat is supported - query from pywiim Player."""
        player = self._get_player()
        if not player:
            return False
        # Use pywiim's repeat_supported property (per integration guide)
        return bool(getattr(player, "repeat_supported", True))

    @property
    def repeat(self) -> RepeatMode | None:
        """Return current repeat mode."""
        # Read directly from Player object (always up-to-date via pywiim)
        player = self._get_player()
        if not player:
            return None

        repeat = getattr(player, "repeat", None)
        if repeat is not None:
            repeat_str = str(repeat).lower()
            if repeat_str in ("1", "one", "track"):
                return RepeatMode.ONE
            elif repeat_str in ("all", "playlist"):
                return RepeatMode.ALL
            else:
                return RepeatMode.OFF
        return None

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode - pass through to pywiim."""
        try:
            await self.coordinator.player.set_repeat(repeat.value)
            # pywiim updates Player state immediately and pushes event via on_state_changed callback
            # The callback triggers async_update_listeners() which notifies all entities automatically
            # We also force a refresh to ensure UI update in case callback is delayed
            await self.coordinator.async_request_refresh()
        except AttributeError as err:
            # Fallback if set_repeat not yet available in pywiim Player
            raise HomeAssistantError(
                f"Repeat mode setting not yet supported. Please update pywiim library: {err}"
            ) from err
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to set repeat: {err}") from err

    # ===== SOUND MODE (EQ) =====

    @property
    def sound_mode(self) -> str | None:
        """Return current sound mode (EQ preset) from Player.

        pywiim provides the current preset in player.eq_preset.
        Returns in title case to match sound_mode_list format.
        """
        if not self._is_eq_supported():
            return None

        player = self._get_player()
        if not player:
            return None

        eq_preset = getattr(player, "eq_preset", None)
        if eq_preset:
            return str(eq_preset).title()
        return None

    @property
    def sound_mode_list(self) -> list[str] | None:
        """Return list of available sound modes (EQ presets) from Player object.

        pywiim caches EQ presets in player.eq_presets during refresh().
        """
        if not self._is_eq_supported():
            return None

        player = self._get_player()
        if not player:
            return None

        # Get cached presets from Player object (populated during refresh())
        eq_presets = getattr(player, "eq_presets", None)
        if eq_presets and isinstance(eq_presets, list):
            # Return list of preset names in title case for display
            return [str(preset).title() for preset in eq_presets]

        return None

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode (EQ preset) - pass through to pywiim.

        pywiim's player.set_eq_preset() handles the preset selection.
        We pass lowercase preset names as that's what the device API expects.
        """
        if not self._is_eq_supported():
            raise HomeAssistantError("EQ is not supported on this device")

        try:
            # Normalize to lowercase (device API expects lowercase)
            await self.coordinator.player.set_eq_preset(sound_mode.lower())
            await self.coordinator.async_request_refresh()
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to select sound mode: {err}") from err

    # ===== SLEEP TIMER & ALARMS =====

    async def set_sleep_timer(self, sleep_time: int) -> None:
        """Set the sleep timer on the player."""
        try:
            await self.coordinator.player.set_sleep_timer(sleep_time)
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to set sleep timer: {err}") from err

    async def clear_sleep_timer(self) -> None:
        """Clear the sleep timer on the player."""
        try:
            await self.coordinator.player.cancel_sleep_timer()
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to clear sleep timer: {err}") from err

    async def set_alarm(
        self,
        alarm_id: int,
        time: str | None = None,
        trigger: str | None = None,
        operation: str | None = None,
    ) -> None:
        """Set or update an alarm on the player.

        Args:
            alarm_id: Alarm slot ID (0-2)
            time: Alarm time in UTC format (HHMMSS, e.g., "070000" for 7:00 AM)
            trigger: Alarm trigger type (e.g., "daily", "2" for ALARM_TRIGGER_DAILY)
            operation: Alarm operation type (e.g., "playback", "1" for ALARM_OP_PLAYBACK)
        """
        try:
            from pywiim import ALARM_OP_PLAYBACK, ALARM_TRIGGER_DAILY

            # Get existing alarm if it exists
            try:
                existing_alarm = await self.coordinator.player.get_alarm(alarm_id)
            except Exception:
                existing_alarm = None

            # Parse trigger - accept string names or numeric values
            trigger_value = None
            if trigger is not None:
                trigger_lower = trigger.lower()
                if trigger_lower == "daily":
                    trigger_value = ALARM_TRIGGER_DAILY
                elif trigger.isdigit():
                    trigger_value = int(trigger)
                else:
                    # Try to find matching constant
                    try:
                        from pywiim import ALARM_TRIGGER_ONCE

                        if trigger_lower == "once":
                            trigger_value = ALARM_TRIGGER_ONCE
                    except ImportError:
                        pass
                    if trigger_value is None:
                        raise HomeAssistantError(f"Unknown trigger type: {trigger}")
            elif existing_alarm:
                # Use existing trigger if not provided
                trigger_value = getattr(existing_alarm, "trigger", ALARM_TRIGGER_DAILY)
            else:
                # Default to daily if creating new alarm
                trigger_value = ALARM_TRIGGER_DAILY

            # Parse operation - accept string names or numeric values
            operation_value = None
            if operation is not None:
                operation_lower = operation.lower()
                if operation_lower == "playback":
                    operation_value = ALARM_OP_PLAYBACK
                elif operation.isdigit():
                    operation_value = int(operation)
                else:
                    raise HomeAssistantError(f"Unknown operation type: {operation}")
            elif existing_alarm:
                # Use existing operation if not provided
                operation_value = getattr(existing_alarm, "operation", ALARM_OP_PLAYBACK)
            else:
                # Default to playback if creating new alarm
                operation_value = ALARM_OP_PLAYBACK

            # Parse time - convert HH:MM:SS or HHMMSS format to HHMMSS
            time_str = None
            if time is not None:
                # Remove colons if present
                time_str = time.replace(":", "")
                # Validate format (should be 6 digits)
                if not time_str.isdigit() or len(time_str) != 6:
                    raise HomeAssistantError(
                        f"Invalid time format: {time}. Expected HH:MM:SS or HHMMSS (e.g., '07:00:00' or '070000')"
                    )
            elif existing_alarm:
                # Use existing time if not provided
                existing_time = getattr(existing_alarm, "time", None)
                if existing_time:
                    # Convert existing time to string format if needed
                    if isinstance(existing_time, str):
                        time_str = existing_time.replace(":", "")
                    else:
                        raise HomeAssistantError("Cannot update alarm: time format not supported")
            else:
                raise HomeAssistantError("Time is required when creating a new alarm")

            # Set the alarm using the player object
            # For daily alarms, pass empty strings for day and url parameters
            # (device firmware requires them even though they're optional in the API)
            if trigger_value == ALARM_TRIGGER_DAILY:
                await self.coordinator.player.set_alarm(
                    alarm_id=alarm_id,
                    trigger=trigger_value,
                    operation=operation_value,
                    time=time_str,
                    day="",
                    url="",
                )
            else:
                await self.coordinator.player.set_alarm(
                    alarm_id=alarm_id,
                    trigger=trigger_value,
                    operation=operation_value,
                    time=time_str,
                )

            _LOGGER.debug("Alarm %d set successfully", alarm_id)
            return

        except WiiMError as err:
            raise HomeAssistantError(f"Failed to set alarm: {err}") from err
        except HomeAssistantError:
            raise
        except Exception as err:
            raise HomeAssistantError(f"Failed to set alarm: {err}") from err

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = {
            "device_model": self.speaker.model,
            "firmware_version": self.speaker.firmware,
            "ip_address": self.speaker.ip_address,
            "mac_address": self.speaker.mac_address,
            "group_role": self.speaker.role,
            "is_group_coordinator": self._get_player().is_master if self._get_player() else False,
            "music_assistant_compatible": True,
            "integration_purpose": "individual_speaker_control",
        }

        # Add shuffle state (always include for visibility)
        shuffle_state = self.shuffle
        attrs["shuffle"] = shuffle_state if shuffle_state is not None else False

        # Add repeat state (always include for visibility)
        repeat_state = self.repeat
        if repeat_state is not None:
            attrs["repeat"] = repeat_state.value if hasattr(repeat_state, "value") else str(repeat_state)
        else:
            attrs["repeat"] = "off"

        # Add sound mode (EQ) if supported (always include for visibility)
        sound_mode = self.sound_mode
        attrs["sound_mode"] = sound_mode if sound_mode is not None else "Not Available"
        # Note: sound_mode_list is None as presets come from pywiim/device dynamically

        # Add group members if in a group
        group_members = self.group_members
        if group_members:
            attrs["group_members"] = group_members
            # Determine group state
            player = self._get_player()
            if player:
                if player.is_master:
                    attrs["group_state"] = "coordinator"
                elif player.is_slave:
                    attrs["group_state"] = "member"
                else:
                    attrs["group_state"] = "solo"
            else:
                attrs["group_state"] = "solo"
        else:
            attrs["group_state"] = "solo"

        return attrs
