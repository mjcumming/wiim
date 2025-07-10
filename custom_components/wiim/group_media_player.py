"""WiiM group media player entity.

Provides unified control for WiiM multiroom groups following the Sonos pattern.
A persistent entity that becomes available when a speaker acts as group master.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .data import Speaker
from .entity import WiimEntity

_LOGGER = logging.getLogger(__name__)


class WiiMGroupMediaPlayer(WiimEntity, MediaPlayerEntity):
    """Representation of a WiiM speaker group coordinator.

    This entity follows the Sonos pattern - it's always created but only becomes
    available when the speaker acts as a group master with active slaves.
    Provides unified control for volume, mute, and playback across all group members.
    """

    def __init__(self, speaker: Speaker) -> None:
        """Initialize the group media player."""
        # Don't call WiimEntity.__init__ to avoid duplicate coordinator
        Entity.__init__(self)
        self.speaker = speaker
        self.coordinator = speaker.coordinator  # Access coordinator through speaker
        self.coordinator_context = None  # Required by CoordinatorEntity
        self._attr_unique_id = f"{speaker.uuid}_group_coordinator"
        self._attr_should_poll = False  # Updates via speaker coordinator

        # Create virtual device for the group
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{speaker.uuid}_group")},
            name=f"{speaker.name} Speaker Group",
            model="Multiroom Group",
            manufacturer="WiiM",
            via_device=(DOMAIN, speaker.uuid),  # Links to physical device
        )

        # Cache for group composition to detect changes
        self._last_group_members: set[str] = set()
        self._last_available: bool | None = None

    # ===== ENTITY PROPERTIES =====

    @property
    def available(self) -> bool:
        """Return True if this speaker is a group coordinator with active slaves."""
        # Available when: speaker is available AND is master AND has slaves
        return self.speaker.available and self.speaker.role == "master" and len(self.speaker.group_members) > 0

    @property
    def name(self) -> str:
        """Return the dynamic name of the group based on composition."""
        if not self.available:
            return f"{self.speaker.name} Group"

        # Dynamic naming based on group size
        member_count = len(self.speaker.group_members)
        if member_count == 1:
            # "Living Room + Kitchen"
            other_speaker = self.speaker.group_members[0]
            return f"{self.speaker.name} + {other_speaker.name}"
        elif member_count <= 3:
            # "Living Room + 2 speakers"
            return f"{self.speaker.name} + {member_count} speakers"
        else:
            # "Living Room group (4 speakers)"
            return f"{self.speaker.name} group ({member_count + 1} speakers)"

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Return the supported features mirroring the coordinator."""
        # Groups support all features of the coordinator EXCEPT grouping
        # Virtual group players should not be able to join/unjoin other players
        if self.available and hasattr(self.speaker, "coordinator"):
            # Mirror the features from the physical media player but exclude GROUPING
            features = (
                MediaPlayerEntityFeature.VOLUME_SET
                | MediaPlayerEntityFeature.VOLUME_MUTE
                | MediaPlayerEntityFeature.VOLUME_STEP
                | MediaPlayerEntityFeature.PLAY
                | MediaPlayerEntityFeature.PAUSE
                | MediaPlayerEntityFeature.STOP
                | MediaPlayerEntityFeature.NEXT_TRACK
                | MediaPlayerEntityFeature.PREVIOUS_TRACK
                # NOTE: GROUPING feature is intentionally excluded
                # Virtual group players should not participate in join/unjoin operations
            )
            return features
        return MediaPlayerEntityFeature(0)

    # ===== PLAYBACK STATE (mirrors coordinator) =====

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the coordinator."""
        if not self.available:
            return None  # Device offline - let HA show as unavailable
        return self.speaker.get_playback_state()

    @property
    def media_content_type(self) -> MediaType | None:
        """Content type of current playing media."""
        if self.available:
            return MediaType.MUSIC
        return None

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        return self.speaker.get_media_title() if self.available else None

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media."""
        return self.speaker.get_media_artist() if self.available else None

    @property
    def media_album_name(self) -> str | None:
        """Album name of current playing media."""
        return self.speaker.get_media_album() if self.available else None

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        return self.speaker.get_media_duration() if self.available else None

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        return self.speaker.get_media_position() if self.available else None

    @property
    def media_position_updated_at(self) -> float | None:
        """Last time media position was updated."""
        return self.speaker.get_media_position_updated_at() if self.available else None

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        if self.available:
            return self.speaker.get_media_image_url()
        return None

    @property
    def media_image_remotely_accessible(self) -> bool:
        """If the image url is remotely accessible."""
        # WiiM devices serve images locally - HA must proxy them
        return False

    # ===== VOLUME CONTROL (group-wide) =====

    @property
    def volume_level(self) -> float | None:
        """Volume level of the group (0..1) - shows maximum volume."""
        if not self.available:
            return None

        # Group volume reflects the maximum speaker in the group
        # This ensures moving any member's slider updates this entity
        volumes: list[float] = []

        # Check coordinator volume
        coordinator_vol = self.speaker.get_volume_level()
        if coordinator_vol is not None:
            volumes.append(coordinator_vol)

        # Check member volumes
        for member in self.speaker.group_members:
            member_vol = member.get_volume_level()
            if member_vol is not None:
                volumes.append(member_vol)

        return max(volumes) if volumes else None

    @property
    def is_volume_muted(self) -> bool | None:
        """Boolean if volume is currently muted."""
        if not self.available:
            return None

        # Group is muted only if ALL members are muted
        mute_states: list[bool] = []

        # Check coordinator mute state
        coordinator_mute = self.speaker.is_volume_muted()
        if coordinator_mute is not None:
            mute_states.append(coordinator_mute)

        # Check member mute states
        for member in self.speaker.group_members:
            member_mute = member.is_volume_muted()
            if member_mute is not None:
                mute_states.append(member_mute)

        # If any unknown (None), return None; otherwise all must be muted
        if len(mute_states) == 0:
            return None
        return all(mute_states)

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level for all group members."""
        if not self.available:
            _LOGGER.warning("Cannot set group volume - group not active")
            return

        _LOGGER.debug("Setting group volume to %.2f for %s", volume, self.speaker.name)

        # Collect all volume change tasks
        tasks = []

        # Set coordinator volume
        tasks.append(self._set_speaker_volume(self.speaker, volume, "coordinator"))

        # Set member volumes
        for member in self.speaker.group_members:
            tasks.append(self._set_speaker_volume(member, volume, "member"))

        # Execute all volume changes simultaneously
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log any failures
        successful = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                speaker_name = self.speaker.name if i == 0 else self.speaker.group_members[i - 1].name
                _LOGGER.warning("Failed to set volume for %s: %s", speaker_name, result)
            else:
                successful += 1

        _LOGGER.debug("Group volume set: %d/%d speakers successful", successful, len(results))

        # Request immediate refresh for fast UI updates
        await self.coordinator.async_request_refresh()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute/unmute all group members."""
        if not self.available:
            _LOGGER.warning("Cannot set group mute - group not active")
            return

        _LOGGER.debug("Setting group mute to %s for %s", mute, self.speaker.name)

        # Collect all mute change tasks
        tasks = []

        # Set coordinator mute
        tasks.append(self._set_speaker_mute(self.speaker, mute, "coordinator"))

        # Set member mutes
        for member in self.speaker.group_members:
            tasks.append(self._set_speaker_mute(member, mute, "member"))

        # Execute all mute changes simultaneously
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log any failures
        successful = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                speaker_name = self.speaker.name if i == 0 else self.speaker.group_members[i - 1].name
                _LOGGER.warning("Failed to set mute for %s: %s", speaker_name, result)
            else:
                successful += 1

        _LOGGER.debug("Group mute set: %d/%d speakers successful", successful, len(results))

        # Request immediate refresh for fast UI updates
        await self.coordinator.async_request_refresh()

    # ===== PLAYBACK CONTROL (via coordinator) =====

    async def async_media_play(self) -> None:
        """Send play command to coordinator."""
        if self.available:
            await self.speaker.coordinator.client.play()
            await self.coordinator.async_request_refresh()

    async def async_media_pause(self) -> None:
        """Send pause command to coordinator."""
        if self.available:
            await self.speaker.coordinator.client.pause()
            await self.coordinator.async_request_refresh()

    async def async_media_stop(self) -> None:
        """Send stop command to coordinator."""
        if self.available:
            await self.speaker.coordinator.client.stop()
            await self.coordinator.async_request_refresh()

    async def async_media_next_track(self) -> None:
        """Send next track command to coordinator."""
        if self.available:
            await self.speaker.coordinator.client.next_track()
            await self.coordinator.async_request_refresh()

    async def async_media_previous_track(self) -> None:
        """Send previous track command to coordinator."""
        if self.available:
            await self.speaker.coordinator.client.previous_track()
            await self.coordinator.async_request_refresh()

    # ===== GROUP MANAGEMENT =====

    async def async_unjoin(self) -> None:
        """Dissolve this group by unjoining all members."""
        if self.available:
            _LOGGER.info("Dissolving group led by %s", self.speaker.name)
            # TODO: Implement group dissolution logic
            # This would typically involve calling unjoin on all group members
            pass

    async def async_join_players(self, group_members: list[str]) -> None:
        """Prevent virtual group players from joining other players."""
        from homeassistant.exceptions import HomeAssistantError

        _LOGGER.warning("Cannot join group - %s is a virtual group player", self.name)
        raise HomeAssistantError(
            f"Virtual group player '{self.name}' cannot join other players. "
            "Use individual speaker entities for group operations."
        )

    async def async_unjoin_player(self) -> None:
        """Prevent virtual group players from being unjoined."""
        from homeassistant.exceptions import HomeAssistantError

        _LOGGER.warning("Cannot unjoin - %s is a virtual group player", self.name)
        raise HomeAssistantError(
            f"Virtual group player '{self.name}' cannot be unjoined. "
            "Use individual speaker entities for group operations."
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes with group member info."""
        if not self.available:
            return {"group_members": [], "group_coordinator": None}

        attrs = {
            "group_members": [],
            "coordinator": self.speaker.name,
            "coordinator_entity_id": self._get_speaker_entity_id(self.speaker),
            "group_size": len(self.speaker.group_members) + 1,  # +1 for coordinator
        }

        # Add coordinator info first
        attrs["group_members"].append(
            {
                "name": self.speaker.name,
                "entity_id": self._get_speaker_entity_id(self.speaker),
                "volume_level": self.speaker.get_volume_level(),
                "is_volume_muted": self.speaker.is_volume_muted(),
                "role": "coordinator",
            }
        )

        # Add member info
        for member in self.speaker.group_members:
            attrs["group_members"].append(
                {
                    "name": member.name,
                    "entity_id": self._get_speaker_entity_id(member),
                    "volume_level": member.get_volume_level(),
                    "is_volume_muted": member.is_volume_muted(),
                    "role": "member",
                }
            )

        return attrs

    # ===== HELPER METHODS =====

    def _get_speaker_entity_id(self, speaker: Speaker) -> str | None:
        """Get the entity ID for a speaker using entity registry lookup."""
        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(self.hass)
        entity_id = ent_reg.async_get_entity_id("media_player", DOMAIN, speaker.uuid)
        return entity_id

    async def _set_speaker_volume(self, speaker: Speaker, volume: float, role: str) -> None:
        """Set volume for a specific speaker with error handling."""
        try:
            await speaker.coordinator.client.set_volume(volume)
            _LOGGER.debug("Set volume %.2f for %s (%s)", volume, speaker.name, role)
        except Exception as err:
            _LOGGER.debug("Failed to set volume for %s (%s): %s", speaker.name, role, err)
            raise  # Re-raise for gather() to handle

    async def _set_speaker_mute(self, speaker: Speaker, mute: bool, role: str) -> None:
        """Set mute for a specific speaker with error handling."""
        try:
            await speaker.coordinator.client.set_mute(mute)
            _LOGGER.debug("Set mute %s for %s (%s)", mute, speaker.name, role)
        except Exception as err:
            _LOGGER.debug("Failed to set mute for %s (%s): %s", speaker.name, role, err)
            raise  # Re-raise for gather() to handle

    @callback
    def async_write_ha_state(self) -> None:
        """Write the state to the state machine and detect availability changes."""
        # Track availability changes for logging
        current_available = self.available
        if hasattr(self, "_last_available") and self._last_available != current_available:
            if current_available:
                _LOGGER.info(
                    "Group coordinator %s became available with %d members", self.name, len(self.speaker.group_members)
                )
            else:
                _LOGGER.info("Group coordinator %s became unavailable", self.speaker.name)
        self._last_available = current_available

        # Detect group composition changes
        current_members = {m.uuid for m in self.speaker.group_members}
        if current_members != self._last_group_members:
            self._last_group_members = current_members.copy()
            if current_available:  # Only log when active
                member_names = [m.name for m in self.speaker.group_members]
                _LOGGER.info(
                    "Group composition changed for %s: coordinator + %s", self.speaker.name, ", ".join(member_names)
                )

        super().async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update for group state changes."""
        # Trigger state write to check for availability/composition changes
        self.async_write_ha_state()
