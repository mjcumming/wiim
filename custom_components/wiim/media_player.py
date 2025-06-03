"""WiiM media player platform."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .data import Speaker
from .entity import WiimEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM media player from a config entry."""
    speaker: Speaker = hass.data[DOMAIN][config_entry.entry_id]["speaker"]
    entity = WiiMMediaPlayer(speaker)
    async_add_entities([entity])
    _LOGGER.info("Media player entity created for %s", speaker.name)


class WiiMMediaPlayer(WiimEntity, MediaPlayerEntity):
    """WiiM media player - thin wrapper around Speaker."""

    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.SEEK
        | MediaPlayerEntityFeature.GROUPING
    )

    def __init__(self, speaker: Speaker) -> None:
        """Initialize the media player."""
        super().__init__(speaker)
        self._attr_unique_id = speaker.uuid
        self._attr_name = speaker.name

    # State properties (delegate to speaker)
    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the device."""
        return self.speaker.get_playback_state()

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        return self.speaker.get_volume_level()

    @property
    def is_volume_muted(self) -> bool | None:
        """Boolean if volume is currently muted."""
        if not self.speaker.coordinator.data:
            return None
        status = self.speaker.coordinator.data.get("status", {})
        return status.get("mute") == "1"

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        if not self.speaker.coordinator.data:
            return None
        status = self.speaker.coordinator.data.get("status", {})
        return status.get("title") or status.get("Title")

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media."""
        if not self.speaker.coordinator.data:
            return None
        status = self.speaker.coordinator.data.get("status", {})
        return status.get("artist") or status.get("Artist")

    @property
    def media_album_name(self) -> str | None:
        """Album name of current playing media."""
        if not self.speaker.coordinator.data:
            return None
        status = self.speaker.coordinator.data.get("status", {})
        return status.get("album") or status.get("Album")

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        if not self.speaker.coordinator.data:
            return None
        status = self.speaker.coordinator.data.get("status", {})
        duration = status.get("duration")
        return int(duration) if duration is not None else None

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        if not self.speaker.coordinator.data:
            return None
        status = self.speaker.coordinator.data.get("status", {})
        position = status.get("position")
        return int(position) if position is not None else None

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        if not self.speaker.coordinator.data:
            return None
        status = self.speaker.coordinator.data.get("status", {})
        return status.get("entity_picture")

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        if not self.speaker.coordinator.data:
            return None
        status = self.speaker.coordinator.data.get("status", {})
        return status.get("source")

    @property
    def source_list(self) -> list[str] | None:
        """List of available input sources."""
        if not self.speaker.coordinator.data:
            return None
        status = self.speaker.coordinator.data.get("status", {})
        return status.get("sources", [])

    @property
    def group_members(self) -> list[str]:
        """Return the list of group members."""
        return self.speaker.get_group_member_entity_ids()

    # Control methods (delegate to speaker coordinator)
    async def async_play(self) -> None:
        """Send play command."""
        await self.speaker.coordinator.client.play()
        await self._request_refresh_and_record_command("play")

    async def async_pause(self) -> None:
        """Send pause command."""
        await self.speaker.coordinator.client.pause()
        await self._request_refresh_and_record_command("pause")

    async def async_stop(self) -> None:
        """Send stop command."""
        await self.speaker.coordinator.client.stop()
        await self._request_refresh_and_record_command("stop")

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        vol_int = int(volume * 100)
        await self.speaker.coordinator.client.set_volume(vol_int)
        await self._request_refresh_and_record_command("volume")

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        await self.speaker.coordinator.client.set_mute(mute)
        await self._request_refresh_and_record_command("mute")

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self.speaker.coordinator.client.next_track()
        await self._request_refresh_and_record_command("next")

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self.speaker.coordinator.client.previous_track()
        await self._request_refresh_and_record_command("previous")

    async def async_media_seek(self, position: float) -> None:
        """Seek to position in seconds."""
        seek_position = int(position)
        await self.speaker.coordinator.client.seek(seek_position)
        await self._request_refresh_and_record_command("seek")

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        await self.speaker.coordinator.client.set_source(source)
        await self._request_refresh_and_record_command("source")

    async def async_join(self, group_members: list[str]) -> None:
        """Join speakers into a group."""
        _LOGGER.info(
            "Group join requested for %s with members: %s",
            self.speaker.name,
            group_members,
        )

        # Delegate to speaker (will be implemented in Phase 5)
        speakers = self.speaker.resolve_entity_ids_to_speakers(group_members)
        await self.speaker.async_join_group(speakers)

    async def async_unjoin(self) -> None:
        """Remove this speaker from its group."""
        _LOGGER.info("Group unjoin requested for %s", self.speaker.name)

        # Delegate to speaker (will be implemented in Phase 5)
        await self.speaker.async_leave_group()

    # Helper methods
    async def _request_refresh_and_record_command(self, command_type: str) -> None:
        """Request coordinator refresh and record user command for smart polling."""
        # Record user command for smart polling
        self.speaker.coordinator.record_user_command(command_type)

        # Request immediate refresh
        await self.speaker.coordinator.async_request_refresh()

    # Extra state attributes for debugging/monitoring
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if not self.speaker.coordinator.data:
            return {}

        attrs = {
            "speaker_uuid": self.speaker.uuid,
            "speaker_role": self.speaker.role,
            "coordinator_ip": self.speaker.coordinator.client.host,
        }

        # Add smart polling info if available
        smart_polling = self.speaker.coordinator.data.get("smart_polling", {})
        if smart_polling:
            attrs.update(
                {
                    "activity_level": smart_polling.get("activity_level"),
                    "polling_interval": smart_polling.get("polling_interval"),
                }
            )

        # Add group info
        if self.speaker.role != "solo":
            attrs["group_members_count"] = len(self.speaker.group_members)

        return attrs
