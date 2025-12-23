"""Base mixin for shared media player functionality."""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.media_player import MediaPlayerState, RepeatMode
from homeassistant.util import dt as dt_util
from pywiim.exceptions import WiiMError

if TYPE_CHECKING:
    from .coordinator import WiiMCoordinator

_LOGGER = logging.getLogger(__name__)


class WiiMMediaPlayerMixin:
    """Mixin providing shared media player functionality.

    This mixin provides common methods and properties for both WiiMMediaPlayer
    and WiiMGroupMediaPlayer to eliminate code duplication.

    Requirements for classes using this mixin:
    - Must have a `coordinator` attribute of type WiiMCoordinator
    - Must have a `player` property that returns `coordinator.player` (provided by WiimEntity)
    - Must have `available`, `name`, `state` properties
    - Must have `media_title`, `media_artist`, `media_album_name` properties
    - Must have `_attr_state`, `_attr_media_position`, etc. attributes
    """

    # Type hints for attributes expected from the class using this mixin
    coordinator: WiiMCoordinator
    name: str
    available: bool
    state: MediaPlayerState | None
    media_title: str | None
    media_artist: str | None
    media_album_name: str | None
    _attr_state: MediaPlayerState | None
    _attr_media_position: float | None
    _attr_media_position_updated_at: Any
    _attr_media_duration: float | None
    _attr_unique_id: str | None
    _attr_supported_features: int

    @property
    def player(self):
        """Access pywiim Player directly - provided by WiimEntity base class."""
        return self.coordinator.player

    def _get_player(self):
        """Get Player object from coordinator (always available after setup)."""
        return self.player

    def _derive_state_from_player(self, player) -> MediaPlayerState | None:
        """Map pywiim's player state to MediaPlayerState.

        Uses pywiim v2.1.37+ clean state properties: is_playing, is_paused, is_buffering.
        """
        if not self.available or not player:
            return None

        # Use pywiim's clean state properties (v2.1.37+)
        if player.is_playing:
            return MediaPlayerState.PLAYING
        if player.is_paused:
            return MediaPlayerState.PAUSED
        # is_buffering maps to BUFFERING in HA
        if player.is_buffering:
            return MediaPlayerState.BUFFERING
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
            # For PAUSED, we want to show the static position.

        _LOGGER.debug(
            "[%s] Published position=%s (ts=%s) duration=%s",
            self.name,
            self._attr_media_position,
            self._attr_media_position_updated_at,
            self._attr_media_duration,
        )

        # Update supported features (includes SEEK based on duration)
        # Note: group player may override this to skip feature updates
        if hasattr(self, "_update_supported_features"):
            self._update_supported_features()

    def _get_metadata_player(self):
        """Return the player that should be used for metadata display.

        Default implementation returns the main player. Individual players
        can override this (e.g., slaves use master's metadata).
        """
        return self._get_player()

    def _next_track_supported(self) -> bool:
        """Check if next/previous track is supported - query from pywiim Player.

        Delegates to pywiim's supports_next_track property, which handles all source-aware
        capability detection internally.
        """
        if not self.available:
            return False
        player = self._get_player()
        if not player:
            return False
        return player.supports_next_track

    def _shuffle_supported(self) -> bool:
        """Check if shuffle is supported - query from pywiim Player."""
        if not self.available:
            return False
        return self._get_player().shuffle_supported

    def _repeat_supported(self) -> bool:
        """Check if repeat is supported - query from pywiim Player."""
        if not self.available:
            return False
        return self._get_player().repeat_supported

    @property
    def shuffle(self) -> bool | None:
        """Return True if shuffle is enabled (pywiim v2.1.37+ returns bool)."""
        if not self.available:
            return None
        player = self._get_player()
        if not player:
            return None
        return player.shuffle

    @property
    def repeat(self) -> RepeatMode | None:
        """Return current repeat mode.

        Converts pywiim's string ('one', 'all', 'off') to HA RepeatMode.
        """
        if not self.available:
            return None

        repeat = self._get_player().repeat
        if repeat is None:
            return None

        # pywiim returns 'one', 'all', 'off' strings
        repeat_str = str(repeat).lower()
        if repeat_str in ("1", "one", "track"):
            return RepeatMode.ONE
        elif repeat_str in ("all", "playlist"):
            return RepeatMode.ALL
        return RepeatMode.OFF

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media.

        Returns a placeholder URL to ensure Home Assistant calls async_get_media_image(),
        which allows pywiim to serve its default WiiM logo when nothing is playing
        or no cover art is available.
        """
        if not self.available:
            return None
        player = self._get_metadata_player()
        if not player:
            return None

        # If pywiim has a URL, use it directly
        # pywiim guarantees media_image_url is always a property (may be None)
        if player.media_image_url:
            return player.media_image_url

        # Always return a placeholder URL to trigger async_get_media_image()
        # This ensures HA calls our override in all states (including IDLE)
        # When nothing is playing, pywiim can serve its default WiiM logo
        # Create a unique identifier based on current state and metadata
        title = self.media_title or ""
        artist = self.media_artist or ""
        state = str(self.state or "idle")

        # Use state + metadata to generate hash, ensuring it changes when track/state changes
        track_hash = self._generate_cover_art_hash(state, title, artist)
        # Use different URL scheme for group vs individual players
        url_prefix = (
            "wiim://group-cover-art/"
            if hasattr(self, "_attr_unique_id") and "group_coordinator" in str(self._attr_unique_id)
            else "wiim://cover-art/"
        )
        return f"{url_prefix}{track_hash}"

    @property
    def media_image_hash(self) -> str | None:
        """Hash value for media image.

        Uses state and track metadata to generate a hash that changes when
        track or state changes, ensuring Home Assistant fetches new cover art.
        """
        player = self._get_metadata_player()
        if not player:
            return None

        # If we have a URL from pywiim, hash it
        # pywiim guarantees media_image_url is always a property (may be None)
        if player.media_image_url:
            return hashlib.sha256(player.media_image_url.encode("utf-8")).hexdigest()[:16]

        # Always create hash from state and metadata (including IDLE state)
        # This ensures cover art updates when state changes (e.g., IDLE -> PLAYING)
        title = self.media_title or ""
        artist = self.media_artist or ""
        album = self.media_album_name or ""
        state = str(self.state or "idle")

        return self._generate_cover_art_hash(state, title, artist, album)

    def _generate_cover_art_hash(
        self,
        state: str | None,
        title: str | None,
        artist: str | None,
        album: str | None = None,
    ) -> str:
        """Generate a hash for cover art based on state and metadata.

        Args:
            state: Current media player state
            title: Media title
            artist: Media artist
            album: Media album (optional)

        Returns:
            Hex digest hash string (16 characters)
        """
        title = title or ""
        artist = artist or ""
        album = album or ""
        state = str(state or "idle")

        if album:
            track_id = f"{state}|{title}|{artist}|{album}".encode()
        else:
            track_id = f"{state}|{title}|{artist}".encode()

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
        entity_name = (
            "group player"
            if hasattr(self, "_attr_unique_id") and "group_coordinator" in str(self._attr_unique_id)
            else "player"
        )
        _LOGGER.debug("async_get_media_image() called for %s %s", entity_name, self.name)

        player = self._get_metadata_player()
        if not player:
            _LOGGER.debug("No player object available for cover art fetch")
            return None, None

        _LOGGER.debug(
            "Cover art URL from player.media_image_url: %s (source: %s, state: %s)",
            player.media_image_url,
            player.source,
            self.state,
        )

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
                    player.media_image_url,
                )
        except AttributeError as e:
            _LOGGER.error("fetch_cover_art() method exists but raised AttributeError - possible pywiim issue: %s", e)
        except WiiMError as e:
            _LOGGER.warning("WiiM error fetching cover art (may be normal if no cover art available): %s", e)
        except Exception as e:
            _LOGGER.error("Unexpected error fetching cover art: %s", e, exc_info=True)

        return None, None
