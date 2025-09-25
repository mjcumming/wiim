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

    # Group coordinators are visible by default
    entity_registry_visible_default = True

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
            identifiers={(DOMAIN, f"{speaker.uuid}_group_coordinator")},
            name=f"{speaker.name} Speaker Group",
            model="Multiroom Group",
            manufacturer="WiiM",
            via_device=(DOMAIN, speaker.uuid),  # Links to physical device
        )

        # Cache for group composition to detect changes
        self._last_group_members: set[str] = set()
        self._last_available: bool | None = None

        # Set initial name based on current state
        self._update_name()

    # ===== ENTITY PROPERTIES =====

    def _update_name(self) -> None:
        """Update the entity name based on current state."""
        # Always show "Group Master" for group coordinator entities
        master_name = self.speaker.name.replace(" Speakers", "").replace(" Speaker", "")
        new_name = f"{master_name} Group Master"

        # Update the attribute name
        self._attr_name = new_name

        # Update the entity registry name if it has changed
        if hasattr(self, "_last_registry_name") and self._last_registry_name != new_name:
            self._last_registry_name = new_name
            # Schedule entity registry update
            if self.hass and self.hass.is_running:
                self.hass.async_create_task(self._async_update_registry_name(new_name))
        elif not hasattr(self, "_last_registry_name"):
            self._last_registry_name = new_name

    async def _async_update_registry_name(self, new_name: str) -> None:
        """Update the entity registry name."""
        try:
            from homeassistant.helpers import entity_registry as er

            registry = er.async_get(self.hass)
            if registry:
                registry.async_update_entity(self.entity_id, name=new_name)
                _LOGGER.debug(
                    "Updated entity registry name for %s to '%s'",
                    self.entity_id,
                    new_name,
                )
        except Exception as e:
            _LOGGER.warning(
                "Failed to update entity registry name for %s: %s",
                self.entity_id,
                e,
            )

    @property
    def available(self) -> bool:
        """Return True if this speaker is a group coordinator with active slaves."""
        # Available when: speaker is available AND is master AND has slaves
        return self.speaker.available and self.speaker.role == "master" and len(self.speaker.group_members) > 0

    @property
    def name(self) -> str:
        """Return the name of the group coordinator."""
        # Always return the current _attr_name to ensure consistency
        return self._attr_name

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Return the supported features mirroring the coordinator."""
        # Groups support all features of the coordinator EXCEPT grouping
        # Virtual group players should not be able to join/unjoin other players

        # Always return features without GROUPING, regardless of availability
        # This ensures group coordinators never appear in join/unjoin menus
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

        # Explicitly ensure GROUPING is never included (defensive programming)
        features = features & ~MediaPlayerEntityFeature.GROUPING

        # Log the features to help debug any issues
        _LOGGER.debug(
            "Group coordinator %s supported features: %s (GROUPING: %s, Available: %s)",
            self.name,
            features,
            bool(features & MediaPlayerEntityFeature.GROUPING),
            self.available,
        )

        return features

    # ===== PLAYBACK STATE (mirrors coordinator) =====

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the coordinator."""
        # Check if underlying device is offline first
        if not self.speaker.available:
            return None  # Device offline - let HA show as unavailable

        # If device is online but group is inactive, show idle
        if not self.available:
            return MediaPlayerState.IDLE  # Group inactive - show idle

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
        # Always return a valid timestamp to prevent Music Assistant issues
        import time

        if self.available:
            return self.speaker.get_media_position_updated_at()
        return time.time()

    @property
    def elapsed_time_last_updated(self) -> str | None:
        """ISO format timestamp when the elapsed time was last updated.

        This attribute is required by Music Assistant's hass_players provider.
        Returns an ISO format datetime string that can be parsed by fromisoformat().
        """
        import time
        from datetime import datetime

        if self.available:
            timestamp = self.speaker.get_media_position_updated_at()
        else:
            timestamp = time.time()

        # Convert timestamp to ISO format string
        from datetime import timezone

        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)  # noqa: UP017
        return dt.isoformat()

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
        """Return entity specific state attributes."""
        attrs = {
            "group_members": self.get_group_member_entity_ids(),
            "group_leader": self.speaker.name,
            "group_role": "coordinator",
            "is_group_coordinator": True,
            # Explicitly mark as not suitable for Music Assistant
            "music_assistant_excluded": True,
            "integration_purpose": "home_assistant_multiroom_only",
        }

        # Add group composition info
        if self.available:
            member_count = len(self.speaker.group_members)
            attrs["group_size"] = member_count + 1  # +1 for coordinator
            attrs["group_status"] = "active"
        else:
            attrs["group_status"] = "inactive"

        return attrs

    # ===== HELPER METHODS =====

    def _get_speaker_entity_id(self, speaker: Speaker) -> str | None:
        """Get the entity ID for a speaker."""
        try:
            return f"media_player.{speaker.name.lower().replace(' ', '_')}"
        except Exception:
            return None

    def get_group_member_entity_ids(self) -> list[str]:
        """Get list of entity IDs for group members."""
        entity_ids = []

        # Add coordinator entity ID
        coordinator_id = self._get_speaker_entity_id(self.speaker)
        if coordinator_id:
            entity_ids.append(coordinator_id)

        # Add member entity IDs
        for member in self.speaker.group_members:
            member_id = self._get_speaker_entity_id(member)
            if member_id:
                entity_ids.append(member_id)

        return entity_ids

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
                    "Group coordinator %s became available with %d members",
                    self.name,
                    len(self.speaker.group_members),
                )
            else:
                _LOGGER.info("Group coordinator %s became unavailable", self.speaker.name)
        self._last_available = current_available

        # Detect group composition changes and force name update
        # Handle both Speaker objects and string names in group_members
        current_members = set()
        member_names = []
        for member in self.speaker.group_members:
            if hasattr(member, "uuid"):
                current_members.add(member.uuid)
                member_names.append(member.name)
            else:
                # String name - use the string as identifier
                current_members.add(str(member))
                member_names.append(str(member))

        # Check if we need to update the name
        if current_members != self._last_group_members or current_available != self._last_available:
            self._last_group_members = current_members.copy()
            self._last_available = current_available

            # Update the name based on current state
            self._update_name()

            if current_available:  # Only log when active
                _LOGGER.info(
                    "Group composition changed for %s: coordinator + %s (name: %s)",
                    self.speaker.name,
                    ", ".join(member_names),
                    self._attr_name,
                )

        super().async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update for group state changes."""
        # Trigger state write to check for availability/composition changes
        self.async_write_ha_state()
