"""WiiM virtual group coordinator media player.

This entity appears when a speaker becomes master with slaves, providing
unified control for the entire multiroom group.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.components.media_player.const import MediaType, RepeatMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from pywiim.exceptions import WiiMConnectionError, WiiMError, WiiMTimeoutError

from .const import CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP
from .coordinator import WiiMCoordinator
from .entity import WiimEntity
from .media_player_base import WiiMMediaPlayerMixin

_LOGGER = logging.getLogger(__name__)


class WiiMGroupMediaPlayer(WiiMMediaPlayerMixin, WiimEntity, MediaPlayerEntity):
    """Virtual group coordinator media player for WiiM multiroom groups.

    This entity dynamically appears when a speaker becomes master with slaves,
    providing unified control for the entire multiroom group. It disappears when
    the group is disbanded (no slaves remain).

    Design decisions per pywiim grouping architecture:
    - Volume shows MAX of all devices (LinkPlay firmware behavior)
    - Mute only true if ALL devices are muted (LinkPlay firmware behavior)
    - All playback commands (play/pause/stop/next/previous) delegate to physical master
    - Media metadata (title/artist/album/cover art) comes from physical master
    - Shuffle/repeat capabilities determined by pywiim (source-aware detection handled internally)
    - Source selection and sound mode/EQ must use individual speaker entities
    - Join/unjoin operations must use individual speaker entities (blocked here)
    - All state management handled by pywiim via callbacks (no manual sync needed)
    """

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the group coordinator media player."""
        super().__init__(coordinator, config_entry)
        uuid = config_entry.unique_id or coordinator.player.host
        self._attr_unique_id = f"{uuid}_group_master"
        self._attr_name = None  # Use dynamic name property

    def _update_position_from_coordinator(self) -> None:
        """Update media position attributes from coordinator data (LinkPlay pattern).

        Uses group object properties (pywiim 2.1.45+) for virtual group media state.
        """
        # Override mixin to skip feature updates (group player doesn't need them)
        if not self.available:
            self._attr_state = None
            self._attr_media_position = None
            self._attr_media_position_updated_at = None
            self._attr_media_duration = None
            return

        player = self._get_player()
        if not player or not player.group:
            self._attr_state = None
            self._attr_media_position = None
            self._attr_media_position_updated_at = None
            self._attr_media_duration = None
            return

        # Use group object for state and position (pywiim 2.1.45+)
        group = player.group
        # Use group's play_state for virtual group entity (pywiim 2.1.45+)
        # Group.play_state comes from master's cached state
        group_play_state = group.play_state
        if not group_play_state:
            # Fallback to player's play_state if group doesn't have it
            group_play_state = player.play_state

        # Derive state from play_state string (group uses master's play_state)
        if group_play_state in ("play", "playing"):
            current_state = MediaPlayerState.PLAYING
        elif group_play_state == "pause":
            current_state = MediaPlayerState.PAUSED
        elif group_play_state in ("buffering", "load"):
            current_state = MediaPlayerState.BUFFERING
        else:
            current_state = MediaPlayerState.IDLE
        self._attr_state = current_state

        # Get values from group object (pywiim 2.1.45+ provides group media properties)
        new_position = group.media_position
        # If duration is 0, return None (unknown) to avoid 00:00 display
        new_duration = group.media_duration if group.media_duration else None

        # Update duration (keep existing if new is invalid during playback)
        if new_duration:
            self._attr_media_duration = new_duration
        elif current_state == MediaPlayerState.IDLE:
            self._attr_media_duration = None
        # Else: Keep existing duration (don't clear on transient errors during playback)

        # Simple Position Update (Robust)
        if new_position is None:
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
            # Freeze timestamp

    @property
    def name(self) -> str:
        """Return dynamic name based on role.

        Always returns a distinct name to ensure entity_id doesn't collide with
        the main player entity. The entity_id is set during first registration and
        never changes, so we need a unique name even when unavailable.
        """
        device_name = self.player.name or self._config_entry.title or "WiiM Speaker"
        return f"{device_name} Group Master"

    @property
    def available(self) -> bool:
        """Return True only when master with slaves.

        This entity dynamically appears/disappears based on group status:
        - Appears when device is master with at least one slave
        - Disappears when group is disbanded (no slaves) or device is slave/solo

        Uses player.role (device API source of truth), NOT group.all_players which
        may be empty even if device has slaves.
        """
        if not self.coordinator.last_update_success:
            return False

        player = self._get_player()
        if not player:
            return False

        # Virtual group only available for masters
        # player.is_master is computed from device API state (source of truth)
        return player.is_master

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features supported by group coordinator.

        The virtual group coordinator provides:
        - Volume/mute control (group-wide via pywiim's Group object)
        - Basic playback control (play/pause/stop/next/previous to master)
        - Play media and announcements
        - Shuffle/repeat (if master's source supports them)

        Intentionally excluded (use individual speaker entities instead):
        - GROUPING (virtual entity shouldn't appear in group dialogs)
        - SELECT_SOURCE (source is per-device, not per-group)
        - SELECT_SOUND_MODE (EQ/sound mode is per-device, not per-group)
        - BROWSE_MEDIA (browse from individual entity)
        - MEDIA_ENQUEUE (queue management on individual entity)
        """
        if not self.available:
            # Return basic features even when unavailable
            return (
                MediaPlayerEntityFeature.VOLUME_SET
                | MediaPlayerEntityFeature.VOLUME_MUTE
                | MediaPlayerEntityFeature.VOLUME_STEP
            )

        features = (
            MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.PLAY_MEDIA
            | MediaPlayerEntityFeature.MEDIA_ANNOUNCE
        )

        # Track controls - pywiim handles source-aware capability detection
        # This ensures consistency with the individual master player entity
        if self._next_track_supported():
            features |= MediaPlayerEntityFeature.NEXT_TRACK
            features |= MediaPlayerEntityFeature.PREVIOUS_TRACK

        # Shuffle/repeat - pywiim handles source-aware capability detection
        if self._shuffle_supported():
            features |= MediaPlayerEntityFeature.SHUFFLE_SET
        if self._repeat_supported():
            features |= MediaPlayerEntityFeature.REPEAT_SET

        return features

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the current state."""
        if not self.available:
            return None
        if self._attr_state is not None:
            return self._attr_state

        player = self._get_player()
        return self._derive_state_from_player(player)

    @property
    def volume_level(self) -> float | None:
        """Return group volume level from pywiim group object.

        Uses player.group.volume_level which returns the MAXIMUM volume of any device.
        """
        if not self.available:
            return None
        player = self._get_player()
        if not player or not player.group:
            return None
        return player.group.volume_level

    @property
    def is_volume_muted(self) -> bool | None:
        """Return group mute state from pywiim group object.

        Uses player.group.is_muted which returns True only if ALL devices are muted.
        """
        if not self.available:
            return None
        player = self._get_player()
        if not player or not player.group:
            return None
        return player.group.is_muted

    @property
    def volume_step(self) -> float:
        """Return the step to be used by the volume_up and volume_down services.

        Reads the configured volume step from the config entry options.
        Defaults to 5% (0.05) if not configured.
        """
        volume_step = self._config_entry.options.get(CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP)
        return float(volume_step)

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level for all group members proportionally.

        Uses pywiim's group.set_volume_all() which sets volume on all members
        while maintaining their relative volume differences. For example, if
        master is at 50% and slave at 30% (60% of master), setting group to
        80% results in master at 80% and slave at 48% (still 60% of master).
        """
        if not self.available:
            return

        player = self._get_player()
        if not player or not player.group:
            return

        try:
            await player.group.set_volume_all(volume)
            # State updates automatically via callback - no manual refresh needed
        except WiiMError as err:
            if isinstance(err, (WiiMConnectionError, WiiMTimeoutError)):
                # Connection/timeout errors are transient - log at warning level
                _LOGGER.warning(
                    "Connection issue setting group volume on %s: %s. The device may be temporarily unreachable.",
                    self.name,
                    err,
                )
                raise HomeAssistantError(
                    f"Unable to set group volume on {self.name}: device temporarily unreachable"
                ) from err
            # Other errors are actual problems - log at error level
            _LOGGER.error("Failed to set group volume on %s: %s", self.name, err, exc_info=True)
            raise HomeAssistantError(f"Failed to set group volume: {err}") from err

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute/unmute all group members simultaneously.

        Uses pywiim's group.mute_all() which sets mute state on all members.
        """
        if not self.available:
            return

        player = self._get_player()
        if not player or not player.group:
            return

        try:
            await player.group.mute_all(mute)
            # State updates automatically via callback - no manual refresh needed
        except WiiMError as err:
            if isinstance(err, (WiiMConnectionError, WiiMTimeoutError)):
                # Connection/timeout errors are transient - log at warning level
                _LOGGER.warning(
                    "Connection issue setting group mute on %s: %s. The device may be temporarily unreachable.",
                    self.name,
                    err,
                )
                raise HomeAssistantError(
                    f"Unable to set group mute on {self.name}: device temporarily unreachable"
                ) from err
            # Other errors are actual problems - log at error level
            _LOGGER.error("Failed to set group mute on %s: %s", self.name, err, exc_info=True)
            raise HomeAssistantError(f"Failed to set group mute: {err}") from err

    async def async_media_play(self) -> None:
        """Start playback on master (slaves follow automatically).

        Commands sent to coordinator.player (the physical master) are automatically
        synchronized to all slaves by the LinkPlay firmware.
        """
        if not self.available:
            return

        try:
            await self.coordinator.player.play()
            # State updates automatically via callback - no manual refresh needed
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to play: {err}") from err

    async def async_media_pause(self) -> None:
        """Pause playback on master (slaves follow automatically).

        Commands sent to coordinator.player (the physical master) are automatically
        synchronized to all slaves by the LinkPlay firmware.
        """
        if not self.available:
            return

        try:
            await self.coordinator.player.pause()
            # State updates automatically via callback - no manual refresh needed
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to pause: {err}") from err

    async def async_media_stop(self) -> None:
        """Stop playback on master (slaves follow automatically).

        Commands sent to coordinator.player (the physical master) are automatically
        synchronized to all slaves by the LinkPlay firmware.
        """
        if not self.available:
            return

        try:
            await self.coordinator.player.stop()
            # State updates automatically via callback - no manual refresh needed
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to stop: {err}") from err

    async def async_media_next_track(self) -> None:
        """Skip to next track on master (slaves follow automatically).

        Commands sent to coordinator.player (the physical master) are automatically
        synchronized to all slaves by the LinkPlay firmware.
        """
        if not self.available:
            return

        try:
            await self.coordinator.player.next_track()
            # State updates automatically via callback - no manual refresh needed
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to skip track: {err}") from err

    async def async_media_previous_track(self) -> None:
        """Skip to previous track on master (slaves follow automatically).

        Commands sent to coordinator.player (the physical master) are automatically
        synchronized to all slaves by the LinkPlay firmware.
        """
        if not self.available:
            return

        try:
            await self.coordinator.player.previous_track()
            # State updates automatically via callback - no manual refresh needed
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to go to previous track: {err}") from err

    async def async_play_media(self, _media_type: str, media_id: str, **_kwargs: Any) -> None:
        """Play media on master (slaves follow automatically).

        Commands sent to coordinator.player (the physical master) are automatically
        synchronized to all slaves by the LinkPlay firmware.
        """
        if not self.available:
            return

        try:
            await self.coordinator.player.play_url(media_id)
            # State updates automatically via callback - no manual refresh needed
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to play media: {err}") from err

    # ===== SHUFFLE & REPEAT =====

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffle mode on master (affects group playback).

        State changes are automatically synchronized via pywiim's on_state_changed
        callback, which triggers coordinator updates for all entities.
        """
        if not self.available:
            return
        try:
            await self.coordinator.player.set_shuffle(shuffle)
            # State updates automatically via callback - no manual refresh needed
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to set shuffle: {err}") from err

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode on master (affects group playback).

        State changes are automatically synchronized via pywiim's on_state_changed
        callback, which triggers coordinator updates for all entities.
        """
        if not self.available:
            return
        try:
            await self.coordinator.player.set_repeat(repeat.value)
            # State updates automatically via callback - no manual refresh needed
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to set repeat: {err}") from err

    # ===== MEDIA PROPERTIES =====
    # All media metadata uses group object properties (pywiim 2.1.45+).
    # The group object provides unified metadata for the virtual group entity.

    @property
    def media_content_type(self) -> MediaType:
        """Return content type."""
        return MediaType.MUSIC

    @property
    def media_content_id(self) -> str | None:
        """Return the content ID (URL) of currently playing media.

        This is used by Home Assistant for scene restoration. When a URL is played
        via play_url(), pywiim tracks it and exposes it here.

        Returns the URL if playing URL-based media and in PLAYING or PAUSED state.
        Returns None for other sources (Spotify, Bluetooth, etc.) or when idle.
        """
        # Only return URL if we're in a state where media could be playing
        if self.state not in (MediaPlayerState.PLAYING, MediaPlayerState.PAUSED):
            return None

        # Use group object properties (pywiim 2.1.45+) for virtual group media
        player = self._get_player()
        if not player or not player.group:
            return None
        # Group object provides media_content_id directly (pywiim 2.1.45+)
        # Note: media_content_id may not be on group, fallback to player
        group = player.group
        if hasattr(group, "media_content_id") and group.media_content_id is not None:
            return group.media_content_id
        return player.media_content_id

    @property
    def media_title(self) -> str | None:
        """Return media title from group (pywiim 2.1.45+ provides group metadata)."""
        if not self.available:
            return None
        player = self._get_player()
        if not player or not player.group:
            return None
        # Group object provides media_title directly (pywiim 2.1.45+)
        return player.group.media_title

    @property
    def media_artist(self) -> str | None:
        """Return media artist from group (pywiim 2.1.45+ provides group metadata)."""
        if not self.available:
            return None
        player = self._get_player()
        if not player or not player.group:
            return None
        # Group object provides media_artist directly (pywiim 2.1.45+)
        return player.group.media_artist

    @property
    def media_album_name(self) -> str | None:
        """Return media album from group (pywiim 2.1.45+ provides group metadata)."""
        if not self.available:
            return None
        player = self._get_player()
        if not player or not player.group:
            return None
        # Group object provides media_album directly (pywiim 2.1.45+)
        return player.group.media_album

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media from group (pywiim 2.1.45+ provides group metadata)."""
        if not self.available:
            return None
        player = self._get_player()
        if not player or not player.group:
            return None
        group = player.group

        # Use group object properties (pywiim 2.1.45+)
        # Note: media_image_url may not be on group object, use master's URL
        if hasattr(group, "media_image_url") and group.media_image_url:
            return group.media_image_url

        # Fallback to master player's image URL
        if player.media_image_url:
            return player.media_image_url

        # Use mixin's placeholder URL logic (calls async_get_media_image)
        title = self.media_title or ""
        artist = self.media_artist or ""
        state = str(self.state or "idle")

        track_hash = self._generate_cover_art_hash(state, title, artist)
        return f"wiim://group-cover-art/{track_hash}"

    async def async_get_media_image(self) -> tuple[bytes | None, str | None]:
        """Return image bytes and content type of current playing media from group.

        Uses group object for metadata (pywiim 2.1.45+).
        """
        if not self.available:
            return None, None

        player = self._get_player()
        if not player or not player.group:
            return None, None

        group = player.group

        # Try to use group's fetch_cover_art if available (pywiim 2.1.45+)
        if hasattr(group, "fetch_cover_art"):
            try:
                result = await group.fetch_cover_art()
                if result and len(result) >= 2 and result[0] and len(result[0]) > 0:
                    return result
            except Exception as e:
                _LOGGER.debug("Group fetch_cover_art failed, falling back to player: %s", e)

        # Fallback to player's fetch_cover_art
        return await super().async_get_media_image()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_position_from_coordinator()
        super()._handle_coordinator_update()

    # Properties now use _attr values set during coordinator update
    # No mutation in property getters - following LinkPlay pattern

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes for the virtual group coordinator.

        Minimal attributes - all state is managed by pywiim:
        - group_leader: Name of the physical master device
        - group_status: "active" when coordinating, "inactive" otherwise
        """
        device_name = self.player.name or self._config_entry.title or "WiiM Speaker"
        attrs = {
            "group_leader": device_name,
            "group_status": "active" if self.available else "inactive",
        }
        return attrs
