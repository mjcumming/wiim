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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pywiim.exceptions import WiiMError

from .const import DOMAIN
from .data import Speaker, find_speaker_by_uuid
from .entity import WiimEntity

_LOGGER = logging.getLogger(__name__)


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

    @property
    def available(self) -> bool:
        """Return True only when master with slaves."""
        if not self.speaker.available or not self.coordinator.last_update_success:
            return False
        # Only available when master with slaves (derive from pywiim Player.group)
        if not self.coordinator.data:
            return False
        player = self.coordinator.data.get("player")
        if not player or not player.group:
            return False
        return (player.role == "master") and bool(self._get_group_members())

    def _get_group_members(self) -> list[Speaker]:
        """Get list of slave speakers in the group using pywiim Player.group."""
        if not self.coordinator.data:
            return []
        player = self.coordinator.data.get("player")
        group = getattr(player, "group", None) if player else None
        if not group:
            return []
        member_objs = getattr(group, "members", None) or getattr(group, "slaves", None) or []
        speakers: list[Speaker] = []
        for member in member_objs:
            member_uuid = getattr(member, "uuid", None) or getattr(member, "mac", None)
            if member_uuid:
                sp = find_speaker_by_uuid(self.hass, str(member_uuid))
                if sp:
                    speakers.append(sp)
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

        return (
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

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the current state."""
        if not self.available:
            return MediaPlayerState.IDLE

        # Use master's state
        if self.coordinator.data:
            play_state = self.coordinator.data.get("play_state")
            if not play_state:
                return MediaPlayerState.IDLE

            play_state_str = str(play_state).lower()
            if play_state_str in ("play", "playing", "load"):
                return MediaPlayerState.PLAYING
            elif play_state_str == "pause":
                return MediaPlayerState.PAUSED
            else:
                return MediaPlayerState.IDLE

        return MediaPlayerState.IDLE

    @property
    def volume_level(self) -> float | None:
        """Return master volume level."""
        if not self.available or not self.coordinator.data:
            return None
        return self.coordinator.data.get("volume_level")

    @property
    def is_volume_muted(self) -> bool | None:
        """Return master mute state."""
        if not self.available or not self.coordinator.data:
            return None
        return self.coordinator.data.get("is_muted")

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level for all group members."""
        if not self.available:
            return

        if not self.available:
            return
        try:
            await self.coordinator.player.set_volume(volume)
            await self.coordinator.async_force_multiroom_refresh()
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to set group volume: {err}") from err

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute/unmute all group members."""
        if not self.available:
            return

        if not self.available:
            return
        try:
            await self.coordinator.player.set_mute(mute)
            await self.coordinator.async_force_multiroom_refresh()
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to set group mute: {err}") from err

    async def async_media_play(self) -> None:
        """Start playback on master (slaves follow automatically)."""
        if not self.available:
            return

        try:
            await self.coordinator.player.play()
            await self.coordinator.async_force_multiroom_refresh()
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to play: {err}") from err

    async def async_media_pause(self) -> None:
        """Pause playback on master (slaves follow automatically)."""
        if not self.available:
            return

        try:
            await self.coordinator.player.pause()
            await self.coordinator.async_force_multiroom_refresh()
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to pause: {err}") from err

    async def async_media_stop(self) -> None:
        """Stop playback on master (slaves follow automatically)."""
        if not self.available:
            return

        try:
            await self.coordinator.player.stop()
            await self.coordinator.async_force_multiroom_refresh()
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to stop: {err}") from err

    async def async_media_next_track(self) -> None:
        """Skip to next track on master (slaves follow automatically)."""
        if not self.available:
            return

        try:
            await self.coordinator.player.next_track()
            await self.coordinator.async_force_multiroom_refresh()
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to skip track: {err}") from err

    async def async_media_previous_track(self) -> None:
        """Skip to previous track on master (slaves follow automatically)."""
        if not self.available:
            return

        try:
            await self.coordinator.player.previous_track()
            await self.coordinator.async_force_multiroom_refresh()
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to go to previous track: {err}") from err

    async def async_play_media(self, _media_type: str, media_id: str, **_kwargs: Any) -> None:
        """Play media on master (slaves follow automatically)."""
        if not self.available:
            return

        try:
            await self.coordinator.player.play_url(media_id)
            await self.coordinator.async_force_multiroom_refresh()
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to play media: {err}") from err

    # Media properties delegate to master
    @property
    def media_title(self) -> str | None:
        """Return media title from master."""
        if not self.available:
            return None
        if self.coordinator.data:
            return self.coordinator.data.get("media_title")
        return None

    @property
    def media_artist(self) -> str | None:
        """Return media artist from master."""
        if not self.available:
            return None
        if self.coordinator.data:
            return self.coordinator.data.get("media_artist")
        return None

    @property
    def media_album_name(self) -> str | None:
        """Return media album from master."""
        if not self.available:
            return None
        if self.coordinator.data:
            return self.coordinator.data.get("media_album")
        return None

    @property
    def media_duration(self) -> int | None:
        """Return media duration from master."""
        if not self.available:
            return None
        if self.coordinator.data:
            return self.coordinator.data.get("media_duration")
        return None

    @property
    def media_position(self) -> int | None:
        """Return media position from master."""
        if not self.available:
            return None
        if self.coordinator.data:
            return self.coordinator.data.get("media_position")
        return None

    @property
    def media_image_url(self) -> str | None:
        """Return media image URL from master."""
        if not self.available:
            return None
        if self.coordinator.data:
            return self.coordinator.data.get("media_image_url")
        return None

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
