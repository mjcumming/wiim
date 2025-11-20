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
from homeassistant.components.media_player.const import RepeatMode
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pywiim.exceptions import WiiMConnectionError, WiiMError, WiiMTimeoutError

from .const import DOMAIN
from .data import Speaker, find_speaker_by_ip, find_speaker_by_uuid
from .entity import WiimEntity

_LOGGER = logging.getLogger(__name__)


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


class WiiMGroupMediaPlayer(WiimEntity, MediaPlayerEntity):
    """Virtual group coordinator media player.

    Only available when speaker is master with slaves. Provides unified
    control for the entire multiroom group.
    """

    def __init__(self, speaker: Speaker) -> None:
        """Initialize the group coordinator media player."""
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_group_coordinator"
        self._attr_name = None  # Use dynamic name property

    @property
    def name(self) -> str:
        """Return dynamic name based on role."""
        if self.available:
            return f"{self.speaker.name} Group Master"
        return self.speaker.name

    def _get_player(self):
        """Get Player object from coordinator data (always up-to-date via pywiim)."""
        if self.coordinator.data:
            return self.coordinator.data.get("player")
        return None

    @property
    def available(self) -> bool:
        """Return True only when master with slaves."""
        if not self.speaker.available or not self.coordinator.last_update_success:
            return False
        # Only available when master with slaves (derive from pywiim Player.group)
        player = self._get_player()
        if not player:
            return False
        if player.role != "master":
            return False
        return bool(self._get_group_members())

    def _get_group_members(self) -> list[Speaker]:
        """Get list of slave speakers in the group using pywiim Player.group."""
        player = self._get_player()
        if not player:
            return []
        speakers: list[Speaker] = []
        added_ids: set[str] = set()

        def _append_speaker(sp: Speaker | None) -> None:
            if not sp:
                return
            if sp.uuid in added_ids:
                return
            speakers.append(sp)
            added_ids.add(sp.uuid)

        # Prefer pywiim group object when populated
        group = getattr(player, "group", None)
        if group:
            member_objs = getattr(group, "members", None) or getattr(group, "slaves", None) or []
            for member in member_objs:
                member_uuid = getattr(member, "uuid", None) or getattr(member, "mac", None)
                if member_uuid:
                    _append_speaker(find_speaker_by_uuid(self.hass, str(member_uuid)))

        # Fallback to coordinator group_info (populated directly from device APIs)
        group_info = (self.coordinator.data or {}).get("group_info") if self.coordinator.data else None
        if group_info and group_info.get("role") == "master":
            for host in group_info.get("slave_hosts", []) or []:
                _append_speaker(find_speaker_by_ip(self.hass, host))

        return speakers

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features supported by group coordinator."""
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
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
            | MediaPlayerEntityFeature.PLAY_MEDIA
            | MediaPlayerEntityFeature.MEDIA_ANNOUNCE
            # NOTE: GROUPING feature is intentionally excluded for virtual group players
        )

        # Only include shuffle/repeat if pywiim says they're supported
        if self._shuffle_supported():
            features |= MediaPlayerEntityFeature.SHUFFLE_SET
        if self._repeat_supported():
            features |= MediaPlayerEntityFeature.REPEAT_SET

        return features

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the current state."""
        if not self.available:
            return MediaPlayerState.IDLE

        # Read play_state directly from Player object (always up-to-date via pywiim)
        player = self._get_player()
        if not player:
            return MediaPlayerState.IDLE

        play_state = player.play_state
        if not play_state:
            return MediaPlayerState.IDLE

        play_state_str = str(play_state).lower()
        if play_state_str in ("play", "playing", "load"):
            return MediaPlayerState.PLAYING
        elif play_state_str == "pause":
            return MediaPlayerState.PAUSED
        else:
            return MediaPlayerState.IDLE

    @property
    def volume_level(self) -> float | None:
        """Return group volume level from pywiim group object.

        Uses player.group.volume_level which returns the MAXIMUM volume of any device.
        """
        if not self.available:
            return None
        player = self._get_player()
        if not player:
            return None
        group = getattr(player, "group", None)
        if not group:
            return None
        # Use pywiim's group.volume_level property (returns MAX of all devices)
        return getattr(group, "volume_level", None)

    @property
    def is_volume_muted(self) -> bool | None:
        """Return group mute state from pywiim group object.

        Uses player.group.is_muted which returns True only if ALL devices are muted.
        """
        if not self.available:
            return None
        player = self._get_player()
        if not player:
            return None
        group = getattr(player, "group", None)
        if not group:
            return None
        # Use pywiim's group.is_muted property (True only if ALL devices are muted)
        return getattr(group, "is_muted", None)

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level for all group members using pywiim group.set_volume_all()."""
        if not self.available:
            return

        player = self._get_player()
        if not player:
            return
        group = getattr(player, "group", None)
        if not group:
            return

        try:
            # Use pywiim's group.set_volume_all() which sets volume on all members proportionally
            await group.set_volume_all(volume)
        except WiiMError as err:
            if _is_connection_error(err):
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
        """Mute/unmute all group members using pywiim group.mute_all()."""
        if not self.available:
            return

        player = self._get_player()
        if not player:
            return
        group = getattr(player, "group", None)
        if not group:
            return

        try:
            # Use pywiim's group.mute_all() which sets mute on all members
            await group.mute_all(mute)
        except WiiMError as err:
            if _is_connection_error(err):
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
        """Start playback on master (slaves follow automatically)."""
        if not self.available:
            return

        try:
            await self.coordinator.player.play()
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to play: {err}") from err

    async def async_media_pause(self) -> None:
        """Pause playback on master (slaves follow automatically)."""
        if not self.available:
            return

        try:
            await self.coordinator.player.pause()
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to pause: {err}") from err

    async def async_media_stop(self) -> None:
        """Stop playback on master (slaves follow automatically)."""
        if not self.available:
            return

        try:
            await self.coordinator.player.stop()
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to stop: {err}") from err

    async def async_media_next_track(self) -> None:
        """Skip to next track on master (slaves follow automatically)."""
        if not self.available:
            return

        try:
            await self.coordinator.player.next_track()
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to skip track: {err}") from err

    async def async_media_previous_track(self) -> None:
        """Skip to previous track on master (slaves follow automatically)."""
        if not self.available:
            return

        try:
            await self.coordinator.player.previous_track()
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to go to previous track: {err}") from err

    async def async_play_media(self, _media_type: str, media_id: str, **_kwargs: Any) -> None:
        """Play media on master (slaves follow automatically)."""
        if not self.available:
            return

        try:
            await self.coordinator.player.play_url(media_id)
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to play media: {err}") from err

    # ===== SHUFFLE & REPEAT =====

    def _shuffle_supported(self) -> bool:
        """Check if shuffle is supported - query from pywiim Player."""
        if not self.available:
            return False
        player = self._get_player()
        if not player:
            return False
        # Use pywiim's shuffle_supported property (per integration guide)
        return bool(getattr(player, "shuffle_supported", True))

    @property
    def shuffle(self) -> bool | None:
        """Return True if shuffle is enabled."""
        if not self.available:
            return None
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
        if not self.available:
            return
        try:
            await self.coordinator.player.set_shuffle(shuffle)
            # pywiim updates Player state immediately and pushes event via on_state_changed callback
            # The callback triggers async_update_listeners() which notifies all entities automatically
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to set shuffle: {err}") from err

    def _repeat_supported(self) -> bool:
        """Check if repeat is supported - query from pywiim Player."""
        if not self.available:
            return False
        player = self._get_player()
        if not player:
            return False
        # Use pywiim's repeat_supported property (per integration guide)
        return bool(getattr(player, "repeat_supported", True))

    @property
    def repeat(self) -> RepeatMode | None:
        """Return current repeat mode."""
        if not self.available:
            return None
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
        if not self.available:
            return
        try:
            await self.coordinator.player.set_repeat(repeat.value)
            # pywiim updates Player state immediately and pushes event via on_state_changed callback
            # The callback triggers async_update_listeners() which notifies all entities automatically
        except AttributeError as err:
            # Fallback if set_repeat not yet available in pywiim Player
            raise HomeAssistantError(
                f"Repeat mode setting not yet supported. Please update pywiim library: {err}"
            ) from err
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to set repeat: {err}") from err

    # Media properties delegate to master
    @property
    def media_title(self) -> str | None:
        """Return media title from master."""
        if not self.available:
            return None
        player = self._get_player()
        return player.media_title if player else None

    @property
    def media_artist(self) -> str | None:
        """Return media artist from master."""
        if not self.available:
            return None
        player = self._get_player()
        return player.media_artist if player else None

    @property
    def media_album_name(self) -> str | None:
        """Return media album from master."""
        if not self.available:
            return None
        player = self._get_player()
        return player.media_album if player else None

    @property
    def media_duration(self) -> int | None:
        """Return media duration from master."""
        if not self.available:
            return None
        player = self._get_player()
        return player.media_duration if player else None

    @property
    def media_position(self) -> int | None:
        """Return media position from master."""
        if not self.available:
            return None
        player = self._get_player()
        return player.media_position if player else None

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media from master."""
        # Group player only shows cover art when available (in group mode)
        if not self.available:
            return None
        player = self._get_player()
        return player.media_image_url if player else None

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
        _LOGGER.debug("async_get_media_image() called for group player %s", self.name)

        # Group player only shows cover art when available (in group mode)
        if not self.available:
            _LOGGER.debug("Group player not available, skipping cover art")
            return None, None

        player = self._get_player()
        if not player:
            _LOGGER.debug("No player object available for group cover art fetch")
            return None, None

        try:
            if not hasattr(player, "fetch_cover_art"):
                _LOGGER.warning("Player object does not have fetch_cover_art method")
                return None, None

            _LOGGER.debug("Calling player.fetch_cover_art() for group player %s", self.name)
            result = await player.fetch_cover_art()
            if result:
                _LOGGER.debug("Group cover art fetched successfully: %d bytes, type=%s", len(result[0]), result[1])
                return result  # (image_bytes, content_type)
            else:
                _LOGGER.debug("fetch_cover_art() returned None for group player")
        except Exception as e:
            _LOGGER.error("Error fetching group cover art: %s", e, exc_info=True)

        return None, None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = {
            "group_leader": self.speaker.name,
            "group_role": "coordinator",
            "is_group_coordinator": True,
            "music_assistant_excluded": True,
            "integration_purpose": "home_assistant_multiroom_only",
        }

        if self.available:
            group_members = self._get_group_members()
            attrs["group_size"] = len(group_members) + 1  # +1 for master
            attrs["group_status"] = "active"

            # Build list of entity IDs for group members
            entity_registry = er.async_get(self.hass)
            entity_ids = []

            # Include master - get the individual media player entity ID
            master_entity_id = entity_registry.async_get_entity_id("media_player", DOMAIN, self.speaker.uuid)
            if master_entity_id:
                entity_ids.append(master_entity_id)

            # Include slaves
            for slave_speaker in group_members:
                entity_id = entity_registry.async_get_entity_id("media_player", DOMAIN, slave_speaker.uuid)
                if entity_id:
                    entity_ids.append(entity_id)

            attrs["group_members"] = entity_ids
        else:
            attrs["group_size"] = 0
            attrs["group_status"] = "inactive"
            attrs["group_members"] = []

        return attrs

    # Prevent join/unjoin on virtual group player
    async def async_join_players(self, group_members: list[str]) -> None:
        """Prevent joining - virtual group players cannot join other players."""
        raise HomeAssistantError(
            "Virtual group player cannot join other players. Use the individual speaker entity instead."
        )

    async def async_unjoin_player(self) -> None:
        """Prevent unjoining - virtual group players cannot be unjoined."""
        raise HomeAssistantError("Virtual group player cannot be unjoined. Use the individual speaker entity instead.")
