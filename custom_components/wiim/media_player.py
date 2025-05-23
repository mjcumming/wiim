"""WiiM media player entity."""

from __future__ import annotations

import logging
from typing import Any
import asyncio

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers import entity_platform
import voluptuous as vol
from homeassistant.components.media_player.const import (
    ATTR_GROUP_MEMBERS as HA_ATTR_GROUP_MEMBERS,
)
from homeassistant.components.media_player.browse_media import BrowseMedia, MediaClass

from .api import WiiMError
from .const import (
    ATTR_DEVICE_ID,
    ATTR_DEVICE_MODEL,
    ATTR_DEVICE_NAME,
    ATTR_EQ_CUSTOM,
    ATTR_EQ_PRESET,
    ATTR_FIRMWARE,
    ATTR_MUTE,
    ATTR_PLAY_MODE,
    ATTR_PRESET,
    ATTR_REPEAT_MODE,
    ATTR_SHUFFLE_MODE,
    ATTR_SOURCE,
    DOMAIN,
    PLAY_MODE_NORMAL,
    PLAY_MODE_REPEAT_ALL,
    PLAY_MODE_REPEAT_ONE,
    PLAY_MODE_SHUFFLE,
    PLAY_MODE_SHUFFLE_REPEAT_ALL,
    CONF_VOLUME_STEP,
    DEFAULT_VOLUME_STEP,
    EQ_PRESET_CUSTOM,
    EQ_PRESET_MAP,
    SOURCE_MAP,
    ATTR_IP_ADDRESS,
)
from .coordinator import WiiMCoordinator
from .group_media_player import WiiMGroupMediaPlayer

_LOGGER = logging.getLogger(__name__)

# Home Assistant doesn't define a constant for the leader attribute.
HA_ATTR_GROUP_LEADER = "group_leader"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM media player from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entity = WiiMMediaPlayer(coordinator)

    async_add_entities([entity])

    # Register custom entity services
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "play_preset",
        {vol.Required("preset"): vol.All(int, vol.Range(min=1, max=6))},
        "async_play_preset",
    )
    platform.async_register_entity_service(
        "toggle_power",
        {},
        "async_toggle_power",
    )
    platform.async_register_entity_service(
        "play_url",
        {vol.Required("url"): str},
        "async_play_url",
    )
    platform.async_register_entity_service(
        "play_playlist",
        {vol.Required("playlist_url"): str},
        "async_play_playlist",
    )
    platform.async_register_entity_service(
        "set_eq",
        {
            vol.Required("preset"): vol.In(list(EQ_PRESET_MAP.keys())),
            vol.Optional("custom_values"): vol.All(
                list, vol.Length(min=10, max=10), [vol.All(int, vol.Range(min=-12, max=12))]
            ),
        },
        "async_set_eq",
    )
    platform.async_register_entity_service(
        "play_notification",
        {vol.Required("url"): str},
        "async_play_notification",
    )

    # Diagnostic helpers
    platform.async_register_entity_service(
        "reboot_device",
        {},
        "async_reboot_device",
    )
    platform.async_register_entity_service(
        "sync_time",
        {},
        "async_sync_time",
    )

    # --- Group entity management ---
    if not hasattr(hass.data[DOMAIN], "_group_entities"):
        hass.data[DOMAIN]["_group_entities"] = {}

    async def update_group_entities():
        """Create or remove group entities based on coordinator group registry."""
        group_entities = hass.data[DOMAIN]["_group_entities"]
        all_masters = set()
        # Find all current group masters
        for coord in hass.data[DOMAIN].values():
            if not hasattr(coord, "groups"):
                continue
            for master_ip in coord.groups.keys():
                all_masters.add(master_ip)
                if master_ip not in group_entities:
                    group_entity = WiiMGroupMediaPlayer(hass, coord, master_ip)
                    async_add_entities([group_entity])
                    group_entities[master_ip] = group_entity
        # Remove group entities for groups that no longer exist
        for master_ip in list(group_entities.keys()):
            if master_ip not in all_masters:
                group_entity = group_entities.pop(master_ip)
                await group_entity.async_remove()

    # Listen for coordinator updates to refresh group entities
    async def _on_coordinator_update():
        await update_group_entities()
    # Register the listener properly for async
    def _listener():
        hass.async_create_task(_on_coordinator_update())
    coordinator.async_add_listener(_listener)
    await update_group_entities()


class WiiMMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Representation of a WiiM media player entity in Home Assistant.

    This class implements the Home Assistant MediaPlayerEntity interface for WiiM devices,
    providing a comprehensive set of media playback controls and device management features.

    Key Features:
    - Full media playback control (play, pause, stop, next/previous track)
    - Volume control with configurable step size
    - Source selection and management
    - Multiroom group support
    - Device diagnostics and maintenance
    - Real-time status updates via coordinator

    State Management:
    - Tracks device power state, playback status, and media information
    - Maintains volume and mute state
    - Monitors device connectivity and group membership
    - Provides detailed device attributes and diagnostics

    Group Support:
    - Can act as master or slave in multiroom groups
    - Supports group creation, joining, and leaving
    - Maintains group synchronization
    - Provides per-device volume control within groups

    Error Handling:
    - Graceful handling of device communication errors
    - Automatic reconnection attempts
    - Detailed error logging for troubleshooting
    """

    def __init__(self, coordinator: WiiMCoordinator) -> None:
        """Initialize the WiiM media player."""
        super().__init__(coordinator)
        status = coordinator.data.get("status", {})
        self._attr_unique_id = coordinator.client.host
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.host)},
            name=status.get("DeviceName") or status.get("device_name") or coordinator.client.host,
            manufacturer="WiiM",
            model=status.get("hardware") or status.get("project"),
            sw_version=status.get("firmware"),
            connections={("mac", status.get("MAC"))} if status.get("MAC") else set(),
        )
        base_features = (
            MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.PLAY_MEDIA
            | MediaPlayerEntityFeature.BROWSE_MEDIA
            | MediaPlayerEntityFeature.GROUPING
        )

        # Add optional selectors only if the coordinator reports support
        if coordinator.source_supported:
            base_features |= MediaPlayerEntityFeature.SELECT_SOURCE
        if coordinator.eq_supported:
            base_features |= MediaPlayerEntityFeature.SELECT_SOUND_MODE

        self._attr_supported_features = base_features
        _LOGGER.debug(
            "WiiM %s: supported_features bitmask = %s (type: %s, enum: %s)",
            coordinator.client.host,
            self._attr_supported_features,
            type(self._attr_supported_features),
            MediaPlayerEntityFeature,
        )

    @property
    def name(self) -> str:
        """Return the name of the entity, always using the latest device name from status."""
        status = self.coordinator.data.get("status", {})
        return status.get("DeviceName") or status.get("device_name") or self.coordinator.client.host

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the device."""
        status = self._effective_status() or {}
        play_status = status.get("play_status")
        _LOGGER.debug("[WiiM] %s: state property, play_status=%s", self.coordinator.client.host, play_status)
        if play_status == "play":
            return MediaPlayerState.PLAYING
        if play_status == "pause":
            return MediaPlayerState.PAUSED
        if play_status == "stop":
            return MediaPlayerState.IDLE
        return MediaPlayerState.IDLE

    @property
    def volume_level(self) -> float | None:
        """Return the volume level of the media player (0..1)."""
        # Prefer *live* data from the device itself.  Unfortunately, LinkPlay
        # slaves often report incorrect or stale volume information while they
        # are part of a group (frequently returning ``0``).  When we detect
        # that this speaker currently acts as a **slave** we therefore fall
        # back to the volume that the *master* advertises for us in its
        # ``multiroom:slave_list`` payload.

        status_volume: int | None = self.coordinator.data.get("status", {}).get("volume")

        # Early-exit for normal (solo or master) speakers – their own status
        # is considered authoritative.
        if self.coordinator.data.get("role") != "slave":
            return float(status_volume) / 100 if status_volume is not None else None

        # --- Slave path ----------------------------------------------------
        # Try to obtain the *current* volume the master keeps for this slave.
        master_coord = self._find_master_coordinator()
        if master_coord and master_coord.data is not None:
            slave_list = master_coord.data.get("multiroom", {}).get("slave_list", [])
            my_ip = self.coordinator.client.host
            for entry in slave_list:
                if isinstance(entry, dict) and entry.get("ip") == my_ip:
                    master_vol = entry.get("volume")
                    if master_vol is not None:
                        return float(master_vol) / 100

        # Fallback to whatever the slave reported itself (may be 0 which is
        # better than showing *unknown* in the UI).
        return float(status_volume) / 100 if status_volume is not None else None

    @property
    def is_volume_muted(self) -> bool | None:
        """Return boolean if volume is currently muted."""
        role = self.coordinator.data.get("role")
        # For *solo* and *master* devices the local status is authoritative.
        if role != "slave":
            return self.coordinator.data.get("status", {}).get("mute")

        # --- Slave path ----------------------------------------------------
        master_coord = self._find_master_coordinator()
        if master_coord and master_coord.data is not None:
            slave_list = master_coord.data.get("multiroom", {}).get("slave_list", [])
            my_ip = self.coordinator.client.host
            for entry in slave_list:
                if isinstance(entry, dict) and entry.get("ip") == my_ip:
                    return bool(entry.get("mute", False))

        # Fallback – may be *None* if the key is missing which Home-Assistant
        # will interpret as *unknown*.
        return self.coordinator.data.get("status", {}).get("mute")

    def _effective_status(self):
        role = self.coordinator.data.get("role")
        _LOGGER.debug("[WiiM] %s: role=%s", self.coordinator.client.host, role)
        if role == "slave":
            master_id = self.coordinator.client.group_master
            multiroom = self.coordinator.data.get("multiroom", {})
            my_ip = self.coordinator.client.host
            my_uuid = self.coordinator.data.get("status", {}).get("device_id")
            _LOGGER.debug("[WiiM] Slave %s: group_master=%s, multiroom=%s, my_ip=%s, my_uuid=%s", self.coordinator.client.host, master_id, multiroom, my_ip, my_uuid)
            # If group_master is set, try to match by IP or UUID
            if master_id:
                for coord in self.hass.data[DOMAIN].values():
                    if not hasattr(coord, "client"):
                        continue
                    host = coord.client.host
                    uuid = coord.data.get("status", {}).get("device_id")
                    _LOGGER.debug("[WiiM] Slave %s: checking coord host=%s, uuid=%s against master_id=%s", self.coordinator.client.host, host, uuid, master_id)
                    if host == master_id or uuid == master_id:
                        status = coord.data.get("status", {})
                        _LOGGER.debug("[WiiM] Slave %s: mirroring master's status by id: %s", self.coordinator.client.host, status)
                        return status
            # If group_master is None, search all coordinators for a master whose slave_list includes this device
            _LOGGER.debug("[WiiM] Slave %s: searching for master by slave_list (my_ip=%s, my_uuid=%s)", self.coordinator.client.host, my_ip, my_uuid)
            for coord in self.hass.data[DOMAIN].values():
                if not hasattr(coord, "client"):
                    continue
                # Check if this coordinator is a master
                if coord.data.get("role") != "master":
                    continue
                # Check master's multiroom info for this slave
                master_multiroom = coord.data.get("multiroom", {})
                slave_list = master_multiroom.get("slave_list", [])
                _LOGGER.debug("[WiiM] Slave %s: checking master %s slave_list=%s", self.coordinator.client.host, coord.client.host, slave_list)
                for slave in slave_list:
                    if isinstance(slave, dict):
                        slave_ip = slave.get("ip")
                        slave_uuid = slave.get("uuid")
                        _LOGGER.debug("[WiiM] Slave %s: comparing to slave_ip=%s, slave_uuid=%s", self.coordinator.client.host, slave_ip, slave_uuid)
                        if (my_ip and my_ip == slave_ip) or (my_uuid and my_uuid == slave_uuid):
                            _LOGGER.debug("[WiiM] Slave %s: found master %s by slave_list", self.coordinator.client.host, coord.client.host)
                            return coord.data.get("status", {})
            # Could not locate the master in current coordinators – try to
            # automatically start a config-flow for it if we know its IP.
            _LOGGER.debug("[WiiM] Slave %s: could not find master to mirror (master not yet set up)", self.coordinator.client.host)

            # If the device advertised the master IP/UUID, attempt an import.
            potential_master = master_id or multiroom.get("master_ip") or multiroom.get("master")
            if potential_master and isinstance(potential_master, str) and "." in potential_master:
                master_ip = potential_master
                # Check if we already have a coordinator for that IP
                if not any(
                    hasattr(c, "client") and c.client.host == master_ip
                    for c in self.hass.data.get(DOMAIN, {}).values()
                ):
                    _LOGGER.debug("[WiiM] Slave %s: launching import flow for unknown master %s", self.coordinator.client.host, master_ip)
                    # Schedule without awaiting – running inside property getter
                    self.hass.async_create_task(
                        self.hass.config_entries.flow.async_init(
                            DOMAIN,
                            context={"source": "import"},
                            data={"host": master_ip},
                        )
                    )
            return {}
        # Not a slave: return own status
        status = self.coordinator.data.get("status", {})
        _LOGGER.debug("[WiiM] %s: returning own status: %s", self.coordinator.client.host, status)
        return status

    @property
    def media_title(self) -> str | None:
        """Return the title of current playing media."""
        status = self._effective_status() or {}
        title = status.get("title")
        _LOGGER.debug("[WiiM] %s: media_title=%s", self.coordinator.client.host, title)
        return None if title in ("unknow", "unknown", None) else title

    @property
    def media_artist(self) -> str | None:
        """Return the artist of current playing media."""
        status = self._effective_status() or {}
        artist = status.get("artist")
        _LOGGER.debug("[WiiM] %s: media_artist=%s", self.coordinator.client.host, artist)
        return None if artist in ("unknow", "unknown", None) else artist

    @property
    def media_album_name(self) -> str | None:
        """Return the album name of current playing media."""
        status = self._effective_status() or {}
        album = status.get("album")
        _LOGGER.debug("[WiiM] %s: media_album_name=%s", self.coordinator.client.host, album)
        return None if album in ("unknow", "unknown", None) else album

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        status = self._effective_status() or {}
        pos = status.get("position")
        _LOGGER.debug("[WiiM] %s: media_position=%s", self.coordinator.client.host, pos)
        return pos

    @property
    def media_position_updated_at(self) -> float | None:
        """When was the position of the current playing media valid."""
        status = self._effective_status() or {}
        updated = status.get("position_updated_at")
        _LOGGER.debug("[WiiM] %s: media_position_updated_at=%s", self.coordinator.client.host, updated)
        return updated

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        status = self._effective_status() or {}
        dur = status.get("duration")
        _LOGGER.debug("[WiiM] %s: media_duration=%s", self.coordinator.client.host, dur)
        return dur

    @property
    def shuffle(self) -> bool | None:
        """Return true if shuffle is enabled."""
        mode = self.coordinator.data.get("status", {}).get("play_mode")
        return mode in (PLAY_MODE_SHUFFLE, PLAY_MODE_SHUFFLE_REPEAT_ALL)

    @property
    def repeat(self) -> str | None:
        """Return current repeat mode."""
        mode = self.coordinator.data.get("status", {}).get("play_mode")
        if mode == PLAY_MODE_REPEAT_ONE:
            return "one"
        if mode in (PLAY_MODE_REPEAT_ALL, PLAY_MODE_SHUFFLE_REPEAT_ALL):
            return "all"
        return "off"

    @property
    def source_list(self) -> list[str]:
        sources = self.coordinator.data.get("status", {}).get("sources", [])
        _LOGGER.debug("[WiiM] %s source_list raw sources: %s", self.entity_id, sources)
        mapped_sources = [SOURCE_MAP.get(src, src.title()) for src in sources]
        _LOGGER.debug("[WiiM] %s source_list mapped sources: %s", self.entity_id, mapped_sources)
        return mapped_sources

    @property
    def source(self) -> str | None:
        src = self.coordinator.data.get("status", {}).get("source")
        return SOURCE_MAP.get(src, src.title()) if src else None

    @property
    def group_members(self) -> list[str]:
        """Return list of group member entity IDs."""
        members = list(self.coordinator.ha_group_members)
        _LOGGER.debug("[WiiM] %s group_members: %s", self.entity_id, members)
        return members

    @property
    def group_leader(self) -> str | None:
        """Return the entity ID of the group leader."""
        leader = self.entity_id if self.coordinator.is_ha_group_leader else None
        _LOGGER.debug("[WiiM] %s group_leader: %s", self.entity_id, leader)
        return leader

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        status = self._effective_status() or {}
        attrs = {
            # Artwork path consumed by frontend via entity_picture
            "entity_picture": status.get("entity_picture") or status.get("cover"),
            ATTR_DEVICE_MODEL: status.get("device_model"),
            ATTR_DEVICE_NAME: status.get("device_name"),
            ATTR_DEVICE_ID: status.get("device_id"),
            ATTR_IP_ADDRESS: self.coordinator.client.host,
            ATTR_FIRMWARE: status.get("firmware"),
            ATTR_PRESET: status.get("preset"),
            ATTR_PLAY_MODE: status.get("play_mode"),
            ATTR_REPEAT_MODE: status.get("repeat_mode"),
            ATTR_SHUFFLE_MODE: status.get("shuffle_mode"),
            # Human-friendly source label (AirPlay, Bluetooth…).  Fall back to
            # the raw string if we do not know the mapping yet.
            ATTR_SOURCE: SOURCE_MAP.get(status.get("source"), status.get("source")),
            ATTR_MUTE: status.get("mute"),
            ATTR_EQ_PRESET: EQ_PRESET_MAP.get(status.get("eq_preset"), status.get("eq_preset")),
            ATTR_EQ_CUSTOM: status.get("eq_custom"),
            "eq_enabled": status.get("eq_enabled", False),
            "eq_presets": status.get("eq_presets", []),
            # Use HA-core constant names so the frontend recognises the
            # grouping capability and displays the chain-link button.
            HA_ATTR_GROUP_MEMBERS: list(self.coordinator.ha_group_members or []),
            HA_ATTR_GROUP_LEADER: self.group_leader,
            "streaming_service": status.get("streaming_service"),
        }
        _LOGGER.debug("[WiiM] %s extra_state_attributes: %s", self.entity_id, attrs)
        return attrs

    @property
    def entity_picture(self) -> str | None:
        """Return URL to current artwork."""
        status = self._effective_status() or {}
        pic = status.get("entity_picture") or status.get("cover")
        _LOGGER.debug("[WiiM] %s: entity_picture=%s", self.coordinator.client.host, pic)
        return pic

    @property
    def sound_mode_list(self) -> list[str]:
        return list(EQ_PRESET_MAP.values())

    @property
    def sound_mode(self) -> str | None:
        preset = self.coordinator.data.get("status", {}).get("eq_preset")
        return EQ_PRESET_MAP.get(preset, "Flat")

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        try:
            await self.coordinator.client.set_power(True)
            await self.coordinator.async_refresh()
        except WiiMError as err:
            _LOGGER.error("Failed to turn on WiiM device: %s", err)
            raise

    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        try:
            await self.coordinator.client.set_power(False)
            await self.coordinator.async_refresh()
        except WiiMError as err:
            _LOGGER.error("Failed to turn off WiiM device: %s", err)
            raise

    def _find_master_coordinator(self):
        _LOGGER.debug("[WiiM] %s: _find_master_coordinator() called", self.entity_id)
        master_ip = self.coordinator.client.group_master
        _LOGGER.debug("[WiiM] %s: Reported master_ip=%s", self.entity_id, master_ip)
        if not master_ip:
            # Fallback: search for master by slave_list
            my_ip = self.coordinator.client.host
            my_uuid = self.coordinator.data.get("status", {}).get("device_id")
            _LOGGER.debug("[WiiM] %s: Searching for master via slave_list (my_ip=%s, my_uuid=%s)", self.entity_id, my_ip, my_uuid)
            for coord in self.hass.data[DOMAIN].values():
                if not hasattr(coord, "client") or coord.data is None:
                    continue
                if coord.data.get("role") != "master":
                    continue
                multiroom = coord.data.get("multiroom", {})
                slave_list = multiroom.get("slave_list", [])
                _LOGGER.debug("[WiiM] %s: Evaluating potential master %s with slave_list=%s", self.entity_id, coord.client.host, slave_list)
                for slave in slave_list:
                    if isinstance(slave, dict):
                        if (my_ip and my_ip == slave.get("ip")) or (my_uuid and my_uuid == slave.get("uuid")):
                            _LOGGER.debug("[WiiM] %s: Matched master %s via slave_list", self.entity_id, coord.client.host)
                            return coord
            _LOGGER.debug("[WiiM] %s: No master coordinator found via slave_list", self.entity_id)
            return None
        _LOGGER.debug("[WiiM] %s: Master_ip present, searching coordinators", self.entity_id)
        for coord in self.hass.data[DOMAIN].values():
            if not hasattr(coord, "client"):
                continue
            if coord.client.host == master_ip:
                _LOGGER.debug("[WiiM] %s: Found master coordinator object for %s", self.entity_id, master_ip)
                return coord
        _LOGGER.debug("[WiiM] %s: No coordinator object found for master_ip=%s", self.entity_id, master_ip)
        return None

    async def async_media_play(self) -> None:
        """Send play command."""
        role = self.coordinator.data.get("role")
        if role == "slave":
            master_coord = self._find_master_coordinator()
            if master_coord:
                await master_coord.client.play()
                await master_coord.async_refresh()
                await self.coordinator.async_refresh()
                return
        await self.coordinator.client.play()
        await self.coordinator.async_refresh()

    async def async_media_pause(self) -> None:
        """Send pause command."""
        role = self.coordinator.data.get("role")
        if role == "slave":
            master_coord = self._find_master_coordinator()
            if master_coord:
                await master_coord.client.pause()
                await master_coord.async_refresh()
                await self.coordinator.async_refresh()
                return
        await self.coordinator.client.pause()
        await self.coordinator.async_refresh()

    async def async_media_stop(self) -> None:
        """Send stop command."""
        try:
            await self.coordinator.client.stop()
            await self.coordinator.async_refresh()
        except WiiMError as err:
            _LOGGER.error("Failed to stop WiiM device: %s", err)
            raise

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        role = self.coordinator.data.get("role")
        if role == "slave":
            master_coord = self._find_master_coordinator()
            if master_coord:
                await master_coord.client.next_track()
                await master_coord.async_refresh()
                await self.coordinator.async_refresh()
                return
        await self.coordinator.client.next_track()
        await self.coordinator.async_refresh()

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        role = self.coordinator.data.get("role")
        if role == "slave":
            master_coord = self._find_master_coordinator()
            if master_coord:
                await master_coord.client.previous_track()
                await master_coord.async_refresh()
                await self.coordinator.async_refresh()
                return
        await self.coordinator.client.previous_track()
        await self.coordinator.async_refresh()

    def _volume_step(self) -> float:
        entry_id = getattr(self.coordinator, 'entry_id', None)
        if entry_id:
            entry = self.hass.config_entries.async_get_entry(entry_id)
            if entry is not None:
                return entry.options.get(CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP)
        return 0.05

    async def async_volume_up(self) -> None:
        """Volume up the media player."""
        if volume := self.volume_level:
            step = self._volume_step()
            try:
                await self.coordinator.client.set_volume(min(1.0, volume + step))
                await self.coordinator.async_refresh()
            except WiiMError as err:
                _LOGGER.error("Failed to increase volume on WiiM device: %s", err)
                raise

    async def async_volume_down(self) -> None:
        """Volume down the media player."""
        if volume := self.volume_level:
            step = self._volume_step()
            try:
                await self.coordinator.client.set_volume(max(0.0, volume - step))
                await self.coordinator.async_refresh()
            except WiiMError as err:
                _LOGGER.error("Failed to decrease volume on WiiM device: %s", err)
                raise

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        try:
            await self.coordinator.client.set_volume(volume)
            await self.coordinator.async_refresh()
        except WiiMError as err:
            _LOGGER.error("Failed to set volume on WiiM device: %s", err)
            raise

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        try:
            await self.coordinator.client.set_mute(mute)
            await self.coordinator.async_refresh()
        except WiiMError as err:
            _LOGGER.error("Failed to mute WiiM device: %s", err)
            raise

    async def async_select_source(self, source: str) -> None:
        src_api = next((k for k, v in SOURCE_MAP.items() if v == source), source.lower())
        await self.coordinator.client.set_source(src_api)
        await self.coordinator.async_refresh()

    async def async_clear_playlist(self) -> None:
        """Clear players playlist."""
        try:
            await self.coordinator.client.clear_playlist()
            await self.coordinator.async_refresh()
        except WiiMError as err:
            _LOGGER.error("Failed to clear playlist on WiiM device: %s", err)
            raise

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffle mode."""
        try:
            if shuffle:
                if self.repeat == "all":
                    await self.coordinator.client.set_shuffle_mode(
                        PLAY_MODE_SHUFFLE_REPEAT_ALL
                    )
                else:
                    await self.coordinator.client.set_shuffle_mode(PLAY_MODE_SHUFFLE)
            else:
                if self.repeat == "all":
                    await self.coordinator.client.set_shuffle_mode(PLAY_MODE_REPEAT_ALL)
                else:
                    await self.coordinator.client.set_shuffle_mode(PLAY_MODE_NORMAL)
            await self.coordinator.async_refresh()
        except WiiMError as err:
            _LOGGER.error("Failed to set shuffle mode on WiiM device: %s", err)
            raise

    async def async_set_repeat(self, repeat: str) -> None:
        """Set repeat mode."""
        try:
            if repeat == "all":
                if self.shuffle:
                    await self.coordinator.client.set_repeat_mode(
                        PLAY_MODE_SHUFFLE_REPEAT_ALL
                    )
                else:
                    await self.coordinator.client.set_repeat_mode(PLAY_MODE_REPEAT_ALL)
            elif repeat == "one":
                await self.coordinator.client.set_repeat_mode(PLAY_MODE_REPEAT_ONE)
            elif self.shuffle:
                await self.coordinator.client.set_repeat_mode(PLAY_MODE_SHUFFLE)
            else:
                await self.coordinator.client.set_repeat_mode(PLAY_MODE_NORMAL)
            await self.coordinator.async_refresh()
        except WiiMError as err:
            _LOGGER.error("Failed to set repeat mode on WiiM device: %s", err)
            raise

    async def async_play_preset(self, preset: int) -> None:
        """Handle the play_preset service call."""
        try:
            await self.coordinator.client.play_preset(preset)
            await self.coordinator.async_refresh()
        except WiiMError as err:
            _LOGGER.error("Failed to play preset on WiiM device: %s", err)
            raise

    async def async_toggle_power(self) -> None:
        """Handle the toggle_power service call."""
        try:
            await self.coordinator.client.toggle_power()
            await self.coordinator.async_refresh()
        except WiiMError as err:
            _LOGGER.error("Failed to toggle power on WiiM device: %s", err)
            raise

    def _entity_id_to_host(self, entity_id: str) -> str:
        """Map HA entity_id to device IP address (host)."""
        _LOGGER.debug("[WiiM] %s: _entity_id_to_host() called with entity_id=%s", self.entity_id, entity_id)

        # First try: Direct IP-based mapping (legacy scheme)
        for coord in self.hass.data[DOMAIN].values():
            if not hasattr(coord, "client"):
                continue
            expected = f"media_player.wiim_{coord.client.host.replace('.', '_')}"
            if expected == entity_id:
                _LOGGER.debug("[WiiM] _entity_id_to_host: Direct match found for host=%s", coord.client.host)
                return coord.client.host

        # Second try: Entity registry lookup
        try:
            from homeassistant.helpers import entity_registry as er
            ent_reg = er.async_get(self.hass)
            ent_entry = ent_reg.async_get(entity_id)

            if ent_entry and ent_entry.unique_id:
                unique = ent_entry.unique_id
                _LOGGER.debug("[WiiM] _entity_id_to_host: Registry lookup found unique_id=%s", unique)

                # Try to match by unique_id (which should be the host IP)
                for coord in self.hass.data[DOMAIN].values():
                    if hasattr(coord, "client") and coord.client.host == unique:
                        _LOGGER.debug("[WiiM] _entity_id_to_host: Match found via unique_id for host=%s", coord.client.host)
                        return coord.client.host

                # Try to match by device name
                device_name = ent_entry.name or ent_entry.original_name
                if device_name:
                    for coord in self.hass.data[DOMAIN].values():
                        if not hasattr(coord, "client"):
                            continue
                        status = coord.data.get("status", {})
                        device_name_from_status = status.get("DeviceName") or status.get("device_name")
                        if device_name_from_status and device_name_from_status.lower() == device_name.lower():
                            _LOGGER.debug("[WiiM] _entity_id_to_host: Match found via device name for host=%s", coord.client.host)
                            return coord.client.host
        except Exception as reg_err:
            _LOGGER.debug("[WiiM] _entity_id_to_host: Entity registry lookup failed: %s", reg_err)

        # Third try: Look for any coordinator with matching entity_id in its data
        for coord in self.hass.data[DOMAIN].values():
            if not hasattr(coord, "client"):
                continue
            if hasattr(coord, "entity_id") and coord.entity_id == entity_id:
                _LOGGER.debug("[WiiM] _entity_id_to_host: Match found via coordinator entity_id for host=%s", coord.client.host)
                return coord.client.host

        _LOGGER.warning("[WiiM] _entity_id_to_host: No match found for entity_id=%s", entity_id)
        raise ValueError(f"Unknown entity_id: {entity_id}")

    async def async_join(self, group_members: list[str]) -> None:
        """Join `group_members` as a group."""
        _LOGGER.info("[WiiM] %s: Starting join operation with group_members=%s", self.entity_id, group_members)
        try:
            # ------------------------------------------------------------------
            # 1) Ensure *this* device is ready to become/act as master
            # ------------------------------------------------------------------

            # If we are currently a slave but about to act as master, leave current group first
            if self.coordinator.client.is_slave:
                _LOGGER.info("[WiiM] %s: Currently a SLAVE, leaving existing group before creating new one", self.entity_id)
                try:
                    await self.coordinator.leave_wiim_group()
                except Exception as leave_err:
                    _LOGGER.warning("[WiiM] %s: Failed to leave existing group (may already be solo): %s", self.entity_id, leave_err)

            # Ensure there is a master group created (either existing or create new)
            if not self.coordinator.client.group_master:
                _LOGGER.info("[WiiM] %s: Creating new group as master", self.entity_id)
                await self.coordinator.create_wiim_group()
                master_ip = self.coordinator.client.host
                _LOGGER.info("[WiiM] %s: Successfully created group as master (%s)", self.entity_id, master_ip)
            else:
                master_ip = self.coordinator.client.group_master
                _LOGGER.info("[WiiM] %s: Using existing group master %s", self.entity_id, master_ip)

            for entity_id in group_members:
                if entity_id == self.entity_id:
                    _LOGGER.debug("[WiiM] %s: Skipping self in group members", self.entity_id)
                    continue
                coord = _find_coordinator(self.hass, entity_id)
                if coord is not None:
                    member_ip = self._entity_id_to_host(entity_id)
                    _LOGGER.info("[WiiM] %s: Instructing %s to join master %s", self.entity_id, member_ip, master_ip)
                    try:
                        await coord.join_wiim_group(master_ip)
                        _LOGGER.info("[WiiM] %s: Successfully joined %s to group", self.entity_id, member_ip)
                    except Exception as join_err:
                        _LOGGER.error("[WiiM] %s: Failed to join %s to group: %s", self.entity_id, member_ip, join_err)
                        raise
                else:
                    _LOGGER.warning("[WiiM] %s: Could not find coordinator for %s – skipping", self.entity_id, entity_id)
                    continue

            # ------------------------------------------------------------------
            # 2) Remove slaves that are currently in the group but not in the
            #    desired `group_members` list (automatic pruning)
            # ------------------------------------------------------------------
            desired_hosts = {self._entity_id_to_host(eid) for eid in group_members if eid != self.entity_id and _find_coordinator(self.hass, eid) is not None}
            current_slaves = set(self.coordinator.wiim_group_members)
            _LOGGER.debug("[WiiM] %s: desired_hosts=%s, current_slaves=%s", self.entity_id, desired_hosts, current_slaves)

            extraneous_slaves = current_slaves - desired_hosts
            for slave_ip in extraneous_slaves:
                _LOGGER.info("[WiiM] %s: Removing extraneous slave %s from group", self.entity_id, slave_ip)
                slave_coord = next(
                    (c for c in self.hass.data[DOMAIN].values() if hasattr(c, "client") and c.client.host == slave_ip),
                    None,
                )
                if slave_coord is not None:
                    try:
                        await slave_coord.leave_wiim_group()
                    except Exception as kick_err:
                        _LOGGER.warning("[WiiM] %s: Failed to remove slave %s: %s", self.entity_id, slave_ip, kick_err)

            _LOGGER.info("[WiiM] %s: Triggering coordinator refresh after join operation", self.entity_id)
            await self.coordinator.async_request_refresh()
            _LOGGER.info("[WiiM] %s: Join operation completed successfully", self.entity_id)
        except Exception as err:
            _LOGGER.error("[WiiM] %s: Failed to complete join operation: %s", self.entity_id, err)
            raise

    async def async_unjoin(self) -> None:
        """Remove this player from any group."""
        _LOGGER.info("[WiiM] %s: Starting unjoin operation", self.entity_id)
        try:
            if self.coordinator.client.is_master:
                _LOGGER.info("[WiiM] %s: Disbanding group as master", self.entity_id)
                await self.coordinator.delete_wiim_group()
                _LOGGER.info("[WiiM] %s: Successfully disbanded group", self.entity_id)
            else:
                _LOGGER.info("[WiiM] %s: Leaving group as member", self.entity_id)
                await self.coordinator.leave_wiim_group()
                _LOGGER.info("[WiiM] %s: Successfully left group", self.entity_id)

            _LOGGER.info("[WiiM] %s: Triggering coordinator refresh after unjoin operation", self.entity_id)
            await self.coordinator.async_request_refresh()
            _LOGGER.info("[WiiM] %s: Unjoin operation completed successfully", self.entity_id)
        except Exception as err:
            _LOGGER.error("[WiiM] %s: Failed to complete unjoin operation: %s", self.entity_id, err)
            raise

    # ------------------------------------------------------------------
    # Diagnostic helpers exposed as entity services
    # ------------------------------------------------------------------

    async def async_reboot_device(self) -> None:
        """Reboot the speaker via entity service."""
        try:
            await self.coordinator.client.reboot()
        except WiiMError as err:
            _LOGGER.error("Failed to reboot WiiM device: %s", err)
            raise

    async def async_sync_time(self) -> None:
        """Synchronise the speaker clock to Home Assistant time."""
        try:
            await self.coordinator.client.sync_time()
        except WiiMError as err:
            _LOGGER.error("Failed to sync time on WiiM device: %s", err)
            raise

    def join_players(self, group_members: list[str]) -> None:
        """Synchronous join for HA compatibility (thread-safe)."""
        future = asyncio.run_coroutine_threadsafe(self.async_join(group_members), self.hass.loop)
        future.result()

    def unjoin_player(self) -> None:
        """Synchronous unjoin for HA compatibility (thread-safe)."""
        future = asyncio.run_coroutine_threadsafe(self.async_unjoin(), self.hass.loop)
        future.result()

    async def async_play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        if media_type == "preset" and media_id.startswith("preset_"):
            preset_num = int(media_id.split("_")[1])
            await self.coordinator.client.play_preset(preset_num)
            await self.coordinator.async_refresh()
        else:
            if media_type == "url":
                await self.coordinator.client.play_url(media_id)
            elif media_type == "playlist":
                await self.coordinator.client.play_playlist(media_id)
            else:
                raise ValueError(f"Unsupported media type: {media_type}")

    async def async_play_url(self, url: str) -> None:
        """Play a URL."""
        await self.coordinator.client.play_url(url)
        await self.coordinator.async_refresh()

    async def async_play_playlist(self, playlist_url: str) -> None:
        """Play an M3U playlist."""
        await self.coordinator.client.play_playlist(playlist_url)
        await self.coordinator.async_refresh()

    async def async_set_eq(self, preset: str, custom_values: list[int] | None = None) -> None:
        """Set EQ preset or custom values."""
        if preset == EQ_PRESET_CUSTOM and custom_values is None:
            raise ValueError("Custom values required for custom EQ preset")

        # Enable EQ if it's not already enabled
        if not self.coordinator.eq_enabled:
            await self.coordinator.client.set_eq_enabled(True)
            await asyncio.sleep(0.1)  # Small delay to ensure EQ is enabled

        if preset == EQ_PRESET_CUSTOM:
            await self.coordinator.client.set_eq_custom(custom_values)
        else:
            await self.coordinator.client.set_eq_preset(preset)
        await self.coordinator.async_refresh()

    async def async_set_eq_enabled(self, enabled: bool) -> None:
        """Enable or disable EQ."""
        await self.coordinator.client.set_eq_enabled(enabled)
        await self.coordinator.async_refresh()

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode (EQ preset)."""
        # Enable EQ if it's not already enabled
        if not self.coordinator.eq_enabled:
            await self.coordinator.client.set_eq_enabled(True)
            await asyncio.sleep(0.1)  # Small delay to ensure EQ is enabled

        preset = next((k for k, v in EQ_PRESET_MAP.items() if v == sound_mode), None)
        if preset:
            await self.coordinator.client.set_eq_preset(preset)
            await self.coordinator.async_refresh()

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        presets = [
            BrowseMedia(
                title=f"Preset {i+1}",
                media_class=MediaClass.MUSIC,
                media_content_id=f"preset_{i+1}",
                media_content_type="preset",
                can_play=True,
                can_expand=False,
                thumbnail=None,
            )
            for i in range(6)
        ]
        return BrowseMedia(
            title="Presets",
            media_class=MediaClass.DIRECTORY,
            media_content_id="presets",
            media_content_type="directory",
            can_play=False,
            can_expand=True,
            children=presets,
        )

    async def async_play_notification(self, url: str) -> None:
        await self.coordinator.client.play_notification(url)
        await self.coordinator.async_refresh()

    # ------------------------------------------------------------------
    # Media-image helper properties – these let Home Assistant *proxy* the
    # artwork so browsers do not block mixed-content (HTTPS ↔ HTTP) or cert
    # errors from the speaker's self-signed TLS certificate.  When we expose
    # :py:meth:`async_get_media_image` HA automatically generates a
    # `/api/media_player_proxy/<entity_id>` URL which it injects into the
    # Lovelace frontend.
    # ------------------------------------------------------------------

    @property
    def media_image_url(self) -> str | None:  # noqa: D401 – HA property name
        """Return the original (remote) artwork URL if available."""
        return self.entity_picture

    @property
    def media_image_remotely_accessible(self) -> bool:  # noqa: D401 – HA field
        """Tell HA whether *media_image_url* can be fetched directly.

        WiiM speakers expose artwork over the device's own HTTPS endpoint
        secured by a per-device, *self-signed* certificate.  Most browsers
        reject those which would leave the cover art blank.  We therefore
        return **False** so Home Assistant proxies the image through its
        `/api/media_player_proxy/…` endpoint.
        """
        return False

    async def async_get_media_image(self):  # type: ignore[override]
        """Fetch the current artwork and hand bytes to Home Assistant.

        When this coroutine returns ``(bytes, mime_type)`` HA stores the
        payload in its cache and serves it via `/api/media_player_proxy/…`.
        If fetching fails we return ``(None, None)`` so the frontend leaves
        the previous image in place.
        """

        url = self.entity_picture
        if not url:
            _LOGGER.debug("[WiiM] %s: async_get_media_image – no URL", self.entity_id)
            return None, None

        # Some firmwares hand out *relative* paths (e.g. `/albumart/0.jpg`).
        # Prefix with the speaker's base URL so the request resolves.
        if url.startswith("/"):
            url = f"https://{self.coordinator.client.host}{url}"

        import aiohttp
        import async_timeout

        try:
            async with async_timeout.timeout(10):
                session = aiohttp.ClientSession()
                async with session.get(url, ssl=False) as resp:  # WiiM certs are self-signed
                    if resp.status != 200:
                        _LOGGER.debug("[WiiM] %s: Artwork fetch failed – HTTP %s", self.entity_id, resp.status)
                        await session.close()
                        return None, None
                    data = await resp.read()
                    mime = resp.headers.get("Content-Type", "image/jpeg")
                    await session.close()
                    return data, mime
        except Exception as err:  # noqa: BLE001 – we simply log & fall back
            _LOGGER.debug("[WiiM] %s: async_get_media_image error: %s", self.entity_id, err)
            return None, None

    # --------------------- App / Service name ---------------------------

    @property
    def app_name(self) -> str | None:  # noqa: D401 – HA property name
        """Return the name of the current streaming service (Spotify, Tidal…)."""
        service = self.coordinator.data.get("status", {}).get("streaming_service")
        return service


def _find_coordinator(hass: HomeAssistant, entity_id: str) -> WiiMCoordinator | None:
    """Return coordinator for the given entity ID."""
    _LOGGER.debug("[WiiM] _find_coordinator: Looking up coordinator for entity_id=%s", entity_id)

    # First try: Direct entity ID to host mapping
    for coord in hass.data[DOMAIN].values():
        if not hasattr(coord, "client"):
            continue
        expected = f"media_player.wiim_{coord.client.host.replace('.', '_')}"
        if expected == entity_id:
            _LOGGER.debug("[WiiM] _find_coordinator: Direct match found for host=%s", coord.client.host)
            return coord

    # Second try: Entity registry lookup
    try:
        from homeassistant.helpers import entity_registry as er
        ent_reg = er.async_get(hass)
        ent_entry = ent_reg.async_get(entity_id)

        if ent_entry and ent_entry.unique_id:
            unique = ent_entry.unique_id
            _LOGGER.debug("[WiiM] _find_coordinator: Registry lookup found unique_id=%s", unique)

            # Try to match by unique_id (which should be the host IP)
            for coord in hass.data[DOMAIN].values():
                if hasattr(coord, "client") and coord.client.host == unique:
                    _LOGGER.debug("[WiiM] _find_coordinator: Match found via unique_id for host=%s", coord.client.host)
                    return coord

            # Try to match by device name
            device_name = ent_entry.name or ent_entry.original_name
            if device_name:
                for coord in hass.data[DOMAIN].values():
                    if not hasattr(coord, "client"):
                        continue
                    status = coord.data.get("status", {})
                    device_name_from_status = status.get("DeviceName") or status.get("device_name")
                    if device_name_from_status and device_name_from_status.lower() == device_name.lower():
                        _LOGGER.debug("[WiiM] _find_coordinator: Match found via device name for host=%s", coord.client.host)
                        return coord
    except Exception as reg_err:
        _LOGGER.debug("[WiiM] _find_coordinator: Entity registry lookup failed: %s", reg_err)

    # Third try: Look for any coordinator with matching entity_id in its data
    for coord in hass.data[DOMAIN].values():
        if not hasattr(coord, "client"):
            continue
        if hasattr(coord, "entity_id") and coord.entity_id == entity_id:
            _LOGGER.debug("[WiiM] _find_coordinator: Match found via coordinator entity_id for host=%s", coord.client.host)
            return coord

    _LOGGER.warning("[WiiM] _find_coordinator: No coordinator found for entity_id=%s", entity_id)
    return None
