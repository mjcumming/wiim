"""WiiM Group Media Player Entity.

Provides a virtual master entity for controlling multiroom groups.
Uses cached state and UUID-based identification for high performance.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .device_registry import get_device_registry

_LOGGER = logging.getLogger(__name__)


def create_master_device_uuid(master_uuid: str) -> str:
    """Create a stable UUID for group master entities."""
    # Simple implementation - just use the master UUID with a prefix
    return f"group_{master_uuid.lower()}"


class WiiMGroupMediaPlayer(MediaPlayerEntity):
    """Virtual master media player for WiiM multiroom groups.

    This entity represents the entire group and allows users to control
    all speakers in the group simultaneously. Uses efficient caching
    and the new UUID scheme for optimal performance.
    """

    def __init__(self, hass: HomeAssistant, coordinator, master_uuid: str) -> None:
        """Initialize the group media player."""
        self.hass = hass
        self.coordinator = coordinator
        self._master_uuid = master_uuid

        # Create stable unique_id and entity_id based on UUID scheme
        group_uuid = create_master_device_uuid(master_uuid)
        self._attr_unique_id = f"wiim_group_{group_uuid}"
        self._entity_id = f"media_player.wiim_group_{master_uuid.lower()}"

        # Get master device info for naming
        status = coordinator.data.get("status", {}) if coordinator.data else {}
        device_name = status.get("device_name") or status.get("DeviceName") or "WiiM Group"

        # Group entity gets " (Group Master)" suffix for clarity
        self._attr_name = f"{device_name} (Group Master)"

        # Use same device as the physical master to group entities together
        device_mac = status.get("MAC")
        device_identifiers = set()
        if device_mac:
            device_identifiers.add((DOMAIN, device_mac.lower().replace(":", "")))
        device_identifiers.add((DOMAIN, coordinator.client.host))

        self._attr_device_info = DeviceInfo(
            identifiers=device_identifiers,
            name=device_name,
            manufacturer="WiiM",
            model=status.get("project", "WiiM Speaker"),
            sw_version=status.get("firmware", "Unknown"),
        )

        # Supported features for group control (removed GROUPING - group masters can't join other groups)
        self._attr_supported_features = (
            MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.VOLUME_SET
        )

        _LOGGER.debug("[WiiMGroup] Initialized group master entity: %s", self._attr_name)

    @property
    def entity_id(self) -> str:
        """Return the entity ID."""
        return self._entity_id

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the group (based on master device)."""
        if not self.coordinator.data:
            return MediaPlayerState.OFF

        status = self.coordinator.data.get("status", {})
        play_status = status.get("play_status", "stop")
        power = status.get("power", False)

        if not power:
            return MediaPlayerState.OFF
        elif play_status == "play":
            return MediaPlayerState.PLAYING
        elif play_status == "pause":
            return MediaPlayerState.PAUSED
        else:
            return MediaPlayerState.IDLE

    @property
    def volume_level(self) -> float | None:
        """Return volume level of the master device."""
        if not self.coordinator.data:
            return None
        status = self.coordinator.data.get("status", {})
        return status.get("volume_level")

    @property
    def is_volume_muted(self) -> bool:
        """Return if volume is muted."""
        if not self.coordinator.data:
            return False
        status = self.coordinator.data.get("status", {})
        return status.get("mute", False)

    @property
    def media_title(self) -> str | None:
        """Return the current media title."""
        if not self.coordinator.data:
            return None
        status = self.coordinator.data.get("status", {})
        return status.get("title")

    @property
    def media_artist(self) -> str | None:
        """Return the current media artist."""
        if not self.coordinator.data:
            return None
        status = self.coordinator.data.get("status", {})
        return status.get("artist")

    @property
    def media_album_name(self) -> str | None:
        """Return the current media album."""
        if not self.coordinator.data:
            return None
        status = self.coordinator.data.get("status", {})
        return status.get("album")

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture URL."""
        if not self.coordinator.data:
            return None
        status = self.coordinator.data.get("status", {})
        return status.get("entity_picture")

    @property
    def group_members(self) -> list[str]:
        """Return list of group member entity IDs."""
        # Use device registry to get group members
        try:
            registry = get_device_registry(self.hass)
            return registry.get_group_members_for_device(self.coordinator.client.host)
        except Exception as err:
            _LOGGER.warning("[WiiMGroup] %s: Failed to get group members: %s", self._attr_name, err)
            return []

    @property
    def group_leader(self) -> str | None:
        """Return the group leader entity ID."""
        # Use device registry to get group leader
        try:
            registry = get_device_registry(self.hass)
            return registry.get_group_leader_for_device(self.coordinator.client.host)
        except Exception as err:
            _LOGGER.warning("[WiiMGroup] %s: Failed to get group leader: %s", self._attr_name, err)
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = {
            "group_type": "wiim_master",
            "master_uuid": self._master_uuid,
            "member_count": len(self.group_members),
            "group_members": self.group_members,
            "is_virtual_entity": True,
            "joinable": False,  # Virtual entities can't be joined to other groups
        }

        if self.coordinator.data:
            multiroom = self.coordinator.data.get("multiroom", {})
            attrs["slave_count"] = multiroom.get("slaves", 0)

        return attrs

    # Media control methods (delegate to master coordinator)
    async def async_play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        """Play media on the group."""
        await self.coordinator.client.play_url(media_id)

    async def async_media_play(self) -> None:
        """Send play command."""
        await self.coordinator.client.play()

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self.coordinator.client.pause()

    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self.coordinator.client.stop()

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self.coordinator.client.next()

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self.coordinator.client.previous()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level for the group."""
        await self.coordinator.client.set_volume(int(volume * 100))

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the group."""
        await self.coordinator.client.set_mute(mute)

    # Group management methods
    async def async_join_players(self, group_members: list[str]) -> None:
        """Add players to this group."""
        # Find coordinators for the entity IDs to join
        for entity_id in group_members:
            if entity_id == self.entity_id:
                continue  # Skip self

            # Extract IP from entity ID and find coordinator
            if "wiim_" in entity_id:
                ip_part = entity_id.split("wiim_", 1)[1].replace("_", ".")
                target_coord = self.coordinator.device_registry.get_device_by_ip(ip_part)
                if target_coord:
                    try:
                        await target_coord.join_wiim_group(self.coordinator.client.host)
                        _LOGGER.debug("[WiiMGroup] %s joined group via %s", entity_id, ip_part)
                    except Exception as err:
                        _LOGGER.error("[WiiMGroup] Failed to join %s to group: %s", entity_id, err)

    async def async_unjoin_player(self) -> None:
        """Remove this group (dissolve it)."""
        try:
            await self.coordinator.delete_wiim_group()
            _LOGGER.debug("[WiiMGroup] Group dissolved")
        except Exception as err:
            _LOGGER.error("[WiiMGroup] Failed to dissolve group: %s", err)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator updates."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(self.coordinator.async_add_listener(self._handle_coordinator_update))

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        # Clean up any listeners here if needed
        pass


def should_create_group_master(coordinator) -> bool:
    """Determine if we should create a group master entity."""
    # Only create for actual masters with slaves
    if not coordinator.data:
        return False

    role = coordinator.get_current_role()
    return role == "master"


def get_group_master_uuid(coordinator) -> str | None:
    """Get the UUID for the group master entity."""
    if not coordinator.data:
        return None

    status = coordinator.data.get("status", {})
    return status.get("uuid")
