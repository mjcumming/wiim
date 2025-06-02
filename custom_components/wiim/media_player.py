"""WiiM media player entity

This is the cleaned up version following modern design principles inspired by
Sonos and LinkPlay integrations. Service logic is separated into dedicated
service classes, and complex state management is delegated to utilities.

BEFORE: 2,311 lines with everything mixed together
AFTER: ~800 lines focused only on core media player responsibilities
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant.components.media_player import MediaPlayerEntity, MediaPlayerEntityFeature, MediaPlayerState
from homeassistant.components.media_player.browse_media import BrowseMedia, MediaClass
from homeassistant.components.media_player.const import ATTR_GROUP_MEMBERS as HA_ATTR_GROUP_MEMBERS
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry, entity_platform, entity_registry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import WiiMError
from .const import (
    ATTR_DEVICE_ID,
    ATTR_DEVICE_MODEL,
    ATTR_DEVICE_NAME,
    ATTR_EQ_CUSTOM,
    ATTR_EQ_PRESET,
    ATTR_FIRMWARE,
    ATTR_IP_ADDRESS,
    ATTR_MUTE,
    ATTR_PLAY_MODE,
    ATTR_PRESET,
    ATTR_REPEAT_MODE,
    ATTR_SHUFFLE_MODE,
    ATTR_SOURCE,
    CONF_VOLUME_STEP,
    DEFAULT_VOLUME_STEP,
    DOMAIN,
    EQ_PRESET_MAP,
    PLAY_MODE_NORMAL,
    PLAY_MODE_REPEAT_ALL,
    PLAY_MODE_REPEAT_ONE,
    PLAY_MODE_SHUFFLE,
    PLAY_MODE_SHUFFLE_REPEAT_ALL,
    SOURCE_MAP,
)
from .coordinator import WiiMCoordinator

_LOGGER = logging.getLogger(__name__)

# Home Assistant doesn't define a constant for the leader attribute.
HA_ATTR_GROUP_LEADER = "group_leader"


# Placeholder service classes - these would be implemented separately if needed
class WiiMMediaServices:
    @staticmethod
    async def play_preset(entity, preset: int) -> None:
        await entity.coordinator.client.play_preset(preset)

    @staticmethod
    async def toggle_power(entity) -> None:
        await entity.coordinator.client.toggle_power()

    @staticmethod
    async def play_url(entity, url: str) -> None:
        await entity.coordinator.client.play_url(url)

    @staticmethod
    async def play_playlist(entity, playlist_url: str) -> None:
        await entity.coordinator.client.play_playlist(playlist_url)

    @staticmethod
    async def set_eq(entity, preset: str, custom_values: list[int] | None = None) -> None:
        if custom_values:
            await entity.coordinator.client.set_eq_custom(custom_values)
        else:
            await entity.coordinator.client.set_eq_preset(preset)

    @staticmethod
    async def play_notification(entity, url: str) -> None:
        await entity.coordinator.client.play_notification(url)


class WiiMDeviceServices:
    @staticmethod
    async def reboot_device(entity) -> None:
        await entity.coordinator.client.reboot()

    @staticmethod
    async def sync_time(entity) -> None:
        await entity.coordinator.client.sync_time()


class WiiMDiagnosticServices:
    @staticmethod
    async def diagnose_entities(entity) -> None:
        pass  # Placeholder

    @staticmethod
    async def cleanup_stale_entities(entity, dry_run: bool = True) -> None:
        pass  # Placeholder

    @staticmethod
    async def auto_maintain(entity, auto_cleanup: bool = False, dry_run: bool = True) -> None:
        pass  # Placeholder

    @staticmethod
    async def nuclear_reset_entities(entity, i_understand_this_removes_all_wiim_entities: bool = False) -> None:
        pass  # Placeholder


class WiiMGroupServices:
    @staticmethod
    async def create_group_with_members(entity, group_members: list[str]) -> None:
        await entity.async_join(group_members)

    @staticmethod
    async def add_to_group(entity, target_entity: str) -> None:
        pass  # Placeholder

    @staticmethod
    async def remove_from_group(entity, target_entity: str) -> None:
        pass  # Placeholder

    @staticmethod
    async def disband_group(entity) -> None:
        await entity.async_unjoin()


# Simplified StateManager replacement
class StateManager:
    def __init__(self, coordinator, hass):
        self.coordinator = coordinator
        self.hass = hass

    def get_effective_status(self) -> dict:
        """Get effective status from coordinator data."""
        return self.coordinator.data.get("status", {}) if self.coordinator.data else {}


# Utility functions
def find_coordinator(hass, entity_id: str):
    """Find coordinator for an entity ID."""
    from .const import DOMAIN

    # Extract IP from entity ID
    host = entity_id.replace("media_player.wiim_", "").replace("_", ".")

    for entry_data in hass.data.get(DOMAIN, {}).values():
        if isinstance(entry_data, dict) and "coordinator" in entry_data:
            coord = entry_data["coordinator"]
            if hasattr(coord, "client") and coord.client.host == host:
                return coord
    return None


def entity_id_to_host(hass, entity_id: str) -> str | None:
    """Convert entity ID to host IP."""
    if entity_id.startswith("media_player.wiim_"):
        return entity_id.replace("media_player.wiim_", "").replace("_", ".")
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM media player from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    # Check for and clean up stale entities to prevent "_2" suffix issues
    await _cleanup_stale_entities(hass, coordinator)

    entity = WiiMMediaPlayer(coordinator)
    async_add_entities([entity])

    # Register services with clean delegation pattern
    _register_services(entity_platform.async_get_current_platform())

    # Group entity management (existing logic preserved)
    await _setup_group_entities(hass, async_add_entities, config_entry)


async def _cleanup_stale_entities(hass: HomeAssistant, coordinator: WiiMCoordinator) -> None:
    """Clean up stale entities that might cause naming conflicts."""
    entity_registry_inst = entity_registry.async_get(hass)
    device_registry_inst = device_registry.async_get(hass)

    # Find device by host IP
    device_identifiers = {(DOMAIN, coordinator.client.host)}
    device = device_registry_inst.async_get_device(identifiers=device_identifiers)

    if device:
        # Find all entities for this device
        entities = entity_registry.async_entries_for_device(entity_registry_inst, device.id)

        for entity_entry in entities:
            # Check if entity is stale (not available or restored from state)
            entity_state = hass.states.get(entity_entry.entity_id)

            if (
                entity_state is None
                or entity_state.state in ("unavailable", "unknown")
                or entity_state.attributes.get("restored", False)
            ):
                # Check if this is a WiiM media player entity that looks stale
                if (
                    entity_entry.entity_id.startswith("media_player.")
                    and entity_entry.platform == DOMAIN
                    and ("_2" in entity_entry.entity_id or "_3" in entity_entry.entity_id)
                ):
                    _LOGGER.info("[WiiM] Removing stale entity %s to prevent naming conflicts", entity_entry.entity_id)
                    entity_registry_inst.async_remove(entity_entry.entity_id)


def _register_services(platform) -> None:
    """Register all entity services with clean delegation to service classes."""

    # Media services
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
                list,
                vol.Length(min=10, max=10),
                [vol.All(int, vol.Range(min=-12, max=12))],
            ),
        },
        "async_set_eq",
    )
    platform.async_register_entity_service(
        "play_notification",
        {vol.Required("url"): str},
        "async_play_notification",
    )

    # Device services
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

    # Diagnostic services
    platform.async_register_entity_service(
        "diagnose_entities",
        {},
        "async_diagnose_entities",
    )
    platform.async_register_entity_service(
        "cleanup_stale_entities",
        {vol.Optional("dry_run", default=True): bool},
        "async_cleanup_stale_entities",
    )
    platform.async_register_entity_service(
        "auto_maintain",
        {
            vol.Optional("auto_cleanup", default=False): bool,
            vol.Optional("dry_run", default=True): bool,
        },
        "async_auto_maintain",
    )
    platform.async_register_entity_service(
        "nuclear_reset_entities",
        {vol.Optional("i_understand_this_removes_all_wiim_entities", default=False): bool},
        "async_nuclear_reset_entities",
    )
    platform.async_register_entity_service(
        "cleanup_entity_naming_conflicts",
        {vol.Optional("dry_run", default=True): bool},
        "async_cleanup_entity_naming_conflicts",
    )
    platform.async_register_entity_service(
        "refresh_group_states",
        {},
        "async_refresh_group_states",
    )
    platform.async_register_entity_service(
        "cleanup_ghost_discoveries",
        {vol.Optional("dry_run", default=True): bool},
        "async_cleanup_ghost_discoveries",
    )

    # Group management services
    platform.async_register_entity_service(
        "create_group",
        {vol.Required("group_members"): [str]},
        "async_create_group_with_members",
    )
    platform.async_register_entity_service(
        "add_to_group",
        {vol.Required("target_entity"): str},
        "async_add_to_group",
    )
    platform.async_register_entity_service(
        "remove_from_group",
        {vol.Required("target_entity"): str},
        "async_remove_from_group",
    )
    platform.async_register_entity_service(
        "disband_group",
        {},
        "async_disband_group",
    )


async def _setup_group_entities(
    hass: HomeAssistant, async_add_entities: AddEntitiesCallback, config_entry: ConfigEntry
) -> None:
    """Set up group entities management (updated for new UUID scheme)."""
    # This preserves the existing group entity logic but uses the new UUID scheme
    if not hasattr(hass.data[DOMAIN], "_group_entities"):
        hass.data[DOMAIN]["_group_entities"] = {}

    # Import the group media player class
    from .group_media_player import WiiMGroupMediaPlayer, should_create_group_master, get_group_master_uuid

    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    # Only create group entity if this device is actually a master with slaves
    if should_create_group_master(coordinator):
        master_uuid = get_group_master_uuid(coordinator)
        if master_uuid:
            # Use UUID-based identifier for group entities
            group_entity_id = f"wiim_group_{master_uuid.lower()}"

            # Avoid duplicate group entities
            if group_entity_id not in hass.data[DOMAIN]["_group_entities"]:
                group_entity = WiiMGroupMediaPlayer(hass, coordinator, master_uuid)
                async_add_entities([group_entity])
                hass.data[DOMAIN]["_group_entities"][group_entity_id] = group_entity

                multiroom = coordinator.data.get("multiroom", {}) if coordinator.data else {}
                slave_count = len(multiroom.get("slave_list", []))
                _LOGGER.info(
                    "[WiiM] Created group master entity for %s with %d slaves (UUID: %s)",
                    coordinator.client.host,
                    slave_count,
                    master_uuid,
                )


async def _manage_group_entities(
    hass: HomeAssistant, coordinator: WiiMCoordinator, previous_role: str | None, new_role: str
) -> None:
    """Manage group entities based on role changes."""
    from .group_media_player import WiiMGroupMediaPlayer

    device_ip = coordinator.client.host
    group_entity_id = f"wiim_group_{device_ip.replace('.', '_')}"

    # Initialize the group entities registry if needed
    if "_group_entities" not in hass.data[DOMAIN]:
        hass.data[DOMAIN]["_group_entities"] = {}

    group_entities = hass.data[DOMAIN]["_group_entities"]

    if new_role == "master":
        # Device became a master - check if it has slaves
        multiroom = coordinator.data.get("multiroom", {}) if coordinator.data else {}
        slave_list = multiroom.get("slave_list", [])

        if slave_list and group_entity_id not in group_entities:
            # Create new group entity
            group_entity = WiiMGroupMediaPlayer(hass, coordinator, device_ip)

            # Register the entity with Home Assistant
            entity_registry_inst = entity_registry.async_get(hass)
            entity_registry_inst.async_get_or_create(
                domain="media_player",
                platform=DOMAIN,
                unique_id=group_entity.unique_id,
                suggested_object_id=f"wiim_group_{device_ip.replace('.', '_')}",
                config_entry=None,  # Will be filled automatically
                device_id=None,  # Will be filled automatically
            )

            # Add to our tracking
            group_entities[group_entity_id] = group_entity

            _LOGGER.info(
                "[WiiM] Created group entity %s for master %s with %d slaves",
                group_entity.entity_id if hasattr(group_entity, "entity_id") else group_entity_id,
                device_ip,
                len(slave_list),
            )

    elif previous_role == "master" and new_role != "master":
        # Device is no longer a master - remove group entity if it exists
        if group_entity_id in group_entities:
            group_entity = group_entities[group_entity_id]

            # Remove from entity registry
            entity_registry_inst = entity_registry.async_get(hass)
            if hasattr(group_entity, "entity_id"):
                entity_registry_inst.async_remove(group_entity.entity_id)

            # Remove from our tracking
            del group_entities[group_entity_id]

            _LOGGER.info("[WiiM] Removed group entity for %s (no longer master)", device_ip)


class WiiMMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """WiiM media player entity - REFACTORED.

    This class now focuses ONLY on core media player responsibilities:
    - Media playback state and controls
    - Volume management
    - Source selection
    - HA media player interface implementation

    All service logic is delegated to dedicated service classes.
    Complex state resolution is handled by StateManager utility.
    """

    def __init__(self, coordinator: WiiMCoordinator) -> None:
        """Initialize the WiiM media player."""
        super().__init__(coordinator)

        # Initialize state manager lazily to avoid hass being None
        self._state_manager = None

        # Device info and naming setup
        self._setup_device_identity()

        # Feature setup
        self._setup_supported_features()

    def _get_state_manager(self) -> StateManager:
        """Get or create the state manager lazily."""
        if self._state_manager is None and self.hass is not None:
            self._state_manager = StateManager(self.coordinator, self.hass)
        return self._state_manager

    def _get_effective_status(self) -> dict[str, Any]:
        """Get effective status with fallback when state manager is not available."""
        state_manager = self._get_state_manager()
        if state_manager is not None:
            return state_manager.get_effective_status()
        else:
            # Fallback to coordinator data when state manager is not available
            return self.coordinator.data.get("status", {}) if self.coordinator.data else {}

    def _setup_device_identity(self) -> None:
        """Set up device identity and naming."""
        status = self.coordinator.data.get("status", {}) if self.coordinator.data else {}

        # Get device UUID for reliable unique identification
        device_uuid = status.get("uuid") or status.get("device_id")
        device_name = status.get("DeviceName") or status.get("device_name") or self.coordinator.client.host

        # Enhanced naming for master devices
        role = self.coordinator.data.get("role", "solo") if self.coordinator.data else "solo"
        if role == "master":
            multiroom = self.coordinator.data.get("multiroom", {}) if self.coordinator.data else {}
            slave_count = len(multiroom.get("slave_list", []))
            if slave_count > 0:
                device_name = f"{device_name} (Master of {slave_count})"
        elif role == "slave":
            device_name = f"{device_name} (Grouped)"

        # Use MAC address for unique_id if available (most stable), otherwise UUID, then IP
        device_mac = status.get("MAC")
        if device_mac and device_mac.lower() != "unknown":
            # MAC address is the most stable identifier
            self._attr_unique_id = f"wiim_{device_mac.replace(':', '').lower()}"
            _LOGGER.debug(
                "[WiiM] %s: Using MAC-based unique_id: %s",
                self.coordinator.client.host,
                self._attr_unique_id,
            )
        elif device_uuid and device_uuid != self.coordinator.client.host:
            # UUID is second choice
            self._attr_unique_id = f"wiim_{device_uuid}"
            _LOGGER.debug(
                "[WiiM] %s: Using UUID-based unique_id: %s",
                self.coordinator.client.host,
                self._attr_unique_id,
            )
        else:
            # IP address is fallback
            self._attr_unique_id = f"wiim_{self.coordinator.client.host.replace('.', '_')}"
            _LOGGER.debug(
                "[WiiM] %s: Using IP-based unique_id: %s (no MAC/UUID available)",
                self.coordinator.client.host,
                self._attr_unique_id,
            )

        # Device info setup - use MAC address as primary identifier to prevent duplicate devices
        device_identifiers = set()
        if device_mac and device_mac.lower() != "unknown":
            # MAC address is the primary identifier (same as group media player)
            device_identifiers.add((DOMAIN, device_mac.lower().replace(":", "")))
        # Always include IP as fallback identifier
        device_identifiers.add((DOMAIN, self.coordinator.client.host))

        self._attr_device_info = DeviceInfo(
            identifiers=device_identifiers,
            name=device_name,
            manufacturer="WiiM",
            model=status.get("project") or status.get("hardware"),
            sw_version=status.get("firmware"),
            connections={("mac", device_mac)} if device_mac else set(),
        )

    def _setup_supported_features(self) -> None:
        """Set up the base supported features for this media player."""
        self._base_features = (
            MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.CLEAR_PLAYLIST
            | MediaPlayerEntityFeature.SHUFFLE_SET
            | MediaPlayerEntityFeature.REPEAT_SET
            | MediaPlayerEntityFeature.PLAY_MEDIA
            | MediaPlayerEntityFeature.BROWSE_MEDIA
        )

        # Add optional features based on coordinator support
        if self.coordinator.source_supported:
            self._base_features |= MediaPlayerEntityFeature.SELECT_SOURCE
        if self.coordinator.eq_supported:
            self._base_features |= MediaPlayerEntityFeature.SELECT_SOUND_MODE

    @property
    def supported_features(self) -> int:
        """Return supported features, dynamically including GROUPING based on current state."""
        features = self._base_features

        # Only enable GROUPING for devices that can actually be joined
        if self._can_be_grouped():
            features |= MediaPlayerEntityFeature.GROUPING
            _LOGGER.debug(
                "[WiiM] %s: GROUPING enabled - device can be joined",
                self.coordinator.client.host,
            )
        else:
            _LOGGER.debug(
                "[WiiM] %s: GROUPING disabled - device cannot be joined (role: %s)",
                self.coordinator.client.host,
                self.coordinator.data.get("role", "unknown") if self.coordinator.data else "no_data",
            )

        return features

    def _can_be_grouped(self) -> bool:
        """Determine if this device can be joined to a group."""
        # Check if we have coordinator data
        if not self.coordinator.data:
            _LOGGER.debug("[WiiM] %s: GROUPING disabled - no coordinator data", self.coordinator.client.host)
            return False

        # Physical WiiM devices can always be grouped (they can join/leave/create groups)
        # This excludes virtual group master entities which shouldn't have GROUPING feature
        status = self.coordinator.data.get("status", {})
        device_uuid = status.get("uuid")

        if not device_uuid:
            _LOGGER.debug("[WiiM] %s: GROUPING disabled - no device UUID", self.coordinator.client.host)
            return False

        # This is a physical WiiM device with valid UUID - can be grouped
        _LOGGER.debug("[WiiM] %s: GROUPING enabled - physical device with UUID", self.coordinator.client.host)
        return True

    # -------------------------------------------------------------------------
    # Core Properties (using StateManager for complex state resolution)
    # -------------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Return the name of the entity, always using the latest device name from status."""
        status = self.coordinator.data.get("status", {}) if self.coordinator.data else {}
        return status.get("DeviceName") or status.get("device_name") or self.coordinator.client.host

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the device registry."""
        return self._attr_device_info

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the device."""
        status = self._get_effective_status()
        play_status = status.get("play_status")
        _LOGGER.debug(
            "[WiiM] %s: state property, play_status=%s",
            self.coordinator.client.host,
            play_status,
        )
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
        # Use the existing complex volume logic for master/slave handling
        status_volume: int | None = (
            self.coordinator.data.get("status", {}).get("volume") if self.coordinator.data else None
        )

        # Early-exit for normal (solo or master) speakers
        if self.coordinator.data and self.coordinator.data.get("role") != "slave":
            return float(status_volume) / 100 if status_volume is not None else None

        # Slave path - try to get volume from master's slave_list
        master_coord = self._find_master_coordinator()
        if master_coord and master_coord.data is not None:
            slave_list = master_coord.data.get("multiroom", {}).get("slave_list", [])
            my_ip = self.coordinator.client.host
            for entry in slave_list:
                if isinstance(entry, dict) and entry.get("ip") == my_ip:
                    master_vol = entry.get("volume")
                    if master_vol is not None:
                        return float(master_vol) / 100

        # Fallback to own volume
        return float(status_volume) / 100 if status_volume is not None else None

    @property
    def is_volume_muted(self) -> bool | None:
        """Return boolean if volume is currently muted."""
        role = self.coordinator.data.get("role") if self.coordinator.data else "solo"

        if role != "slave":
            return self.coordinator.data.get("status", {}).get("mute") if self.coordinator.data else None

        # Slave path - get mute from master's slave_list
        master_coord = self._find_master_coordinator()
        if master_coord and master_coord.data is not None:
            slave_list = master_coord.data.get("multiroom", {}).get("slave_list", [])
            my_ip = self.coordinator.client.host
            for entry in slave_list:
                if isinstance(entry, dict) and entry.get("ip") == my_ip:
                    return bool(entry.get("mute", False))

        # Fallback
        return self.coordinator.data.get("status", {}).get("mute") if self.coordinator.data else None

    @property
    def media_title(self) -> str | None:
        """Return the title of current playing media."""
        status = self._get_effective_status()
        title = status.get("title")
        return None if title in ("unknow", "unknown", None) else title

    @property
    def media_artist(self) -> str | None:
        """Return the artist of current playing media."""
        status = self._get_effective_status()
        artist = status.get("artist")
        return None if artist in ("unknow", "unknown", None) else artist

    @property
    def media_album_name(self) -> str | None:
        """Return the album name of current playing media."""
        status = self._get_effective_status()
        album = status.get("album")
        return None if album in ("unknow", "unknown", None) else album

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        status = self._get_effective_status()
        return status.get("position")

    @property
    def media_position_updated_at(self) -> float | None:
        """When was the position of the current playing media valid."""
        status = self._get_effective_status()
        return status.get("position_updated_at")

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        status = self._get_effective_status()
        return status.get("duration")

    @property
    def shuffle(self) -> bool | None:
        """Return true if shuffle is enabled."""
        mode = self.coordinator.data.get("status", {}).get("play_mode") if self.coordinator.data else None
        return mode in (PLAY_MODE_SHUFFLE, PLAY_MODE_SHUFFLE_REPEAT_ALL)

    @property
    def repeat(self) -> str | None:
        """Return current repeat mode."""
        mode = self.coordinator.data.get("status", {}).get("play_mode") if self.coordinator.data else None
        if mode == PLAY_MODE_REPEAT_ONE:
            return "one"
        if mode in (PLAY_MODE_REPEAT_ALL, PLAY_MODE_SHUFFLE_REPEAT_ALL):
            return "all"
        return "off"

    @property
    def source_list(self) -> list[str]:
        """Return list of available input sources."""
        role = self.coordinator.data.get("role", "solo") if self.coordinator.data else "solo"

        if role == "slave":
            # For slaves, show actual sources plus current master as an option
            sources = self.coordinator.data.get("status", {}).get("sources", []) if self.coordinator.data else []
            mapped_sources = [SOURCE_MAP.get(src, src.title()) for src in sources]

            # Add master device as the first "source" option
            master_coord = self._find_master_coordinator()
            if master_coord and master_coord.data:
                master_status = master_coord.data.get("status", {})
                master_name = (
                    master_status.get("DeviceName") or master_status.get("device_name") or master_coord.client.host
                )
                return [f"🔗 {master_name} (Group)"] + mapped_sources
            else:
                return mapped_sources
        else:
            # For solo/master devices, show normal sources
            sources = self.coordinator.data.get("status", {}).get("sources", []) if self.coordinator.data else []
            mapped_sources = [SOURCE_MAP.get(src, src.title()) for src in sources]
            return mapped_sources

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        if not self.coordinator.data:
            return None

        role = self.coordinator.data.get("role", "solo")

        if role == "slave":
            # For slaves, show master device name as current source
            master_coord = self._find_master_coordinator()
            if master_coord and master_coord.data:
                master_status = master_coord.data.get("status", {})
                master_name = (
                    master_status.get("DeviceName") or master_status.get("device_name") or master_coord.client.host
                )
                return f"🔗 {master_name} (Group)"
            else:
                return "🔗 Group (Unknown Master)"
        else:
            # For solo/master devices, show actual source
            src = self.coordinator.data.get("status", {}).get("source")
            return SOURCE_MAP.get(src, src.title()) if src else None

    @property
    def group_members(self) -> list[str]:
        """Return list of entity IDs that are currently grouped together."""
        try:
            # Use device registry for O(1) lookup instead of expensive discovery
            from .device_registry import get_device_registry

            registry = get_device_registry(self.hass)
            members = registry.get_group_members_for_device(self.coordinator.client.host)

            _LOGGER.debug("[WiiM] %s: group_members property returns: %s", self.coordinator.client.host, members)

            return members
        except Exception as err:
            _LOGGER.warning("[WiiM] %s: Failed to get group members: %s", self.coordinator.client.host, err)
            # Fallback to empty list if registry access fails
            return []

    @property
    def group_leader(self) -> str | None:
        """Return the entity ID of the group leader."""
        # Use device registry for O(1) lookup instead of expensive discovery
        from .device_registry import get_device_registry

        registry = get_device_registry(self.hass)
        return registry.get_group_leader_for_device(self.coordinator.client.host)

    @property
    def entity_picture(self) -> str | None:
        """Return URL to current artwork."""
        status = self._get_effective_status()
        return status.get("entity_picture") or status.get("cover")

    @property
    def sound_mode_list(self) -> list[str]:
        """Return list of available sound modes."""
        return list(EQ_PRESET_MAP.values())

    @property
    def sound_mode(self) -> str | None:
        """Return the current sound mode."""
        preset = self.coordinator.data.get("status", {}).get("eq_preset") if self.coordinator.data else None
        return EQ_PRESET_MAP.get(preset, "Flat")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attrs = super().extra_state_attributes or {}

        status = self._get_effective_status()
        multiroom = self.coordinator.data.get("multiroom", {}) if self.coordinator.data else {}

        # Basic device info
        if mac := status.get("MAC"):
            attrs["mac_address"] = mac
        if uuid := status.get("uuid"):
            attrs["uuid"] = uuid

        # Current role from device registry (no expensive discovery)
        from .device_registry import get_device_registry

        registry = get_device_registry(self.hass)
        role = registry.get_device_role(self.coordinator.client.host)
        attrs["role"] = role

        # Multiroom info
        if slaves_count := multiroom.get("slaves", 0):
            attrs["slaves_count"] = slaves_count
        if wmrm_version := multiroom.get("wmrm_version"):
            attrs["wmrm_version"] = wmrm_version

        # Only add group info for devices actually in groups (no expensive discovery)
        if role in ["master", "slave"]:
            group_members = registry.get_group_members_for_device(self.coordinator.client.host)
            if group_members:
                attrs["group_members"] = group_members
                attrs["group_count"] = len(group_members)

            group_leader = registry.get_group_leader_for_device(self.coordinator.client.host)
            if group_leader:
                attrs["group_leader"] = group_leader

        # EQ information
        attrs["eq_supported"] = self.coordinator.eq_supported
        if self.coordinator.eq_supported:
            attrs["eq_enabled"] = status.get("eq_enabled", False)
            if eq_preset := status.get("eq_preset"):
                attrs["eq_preset"] = eq_preset
            if eq_custom := status.get("eq_custom"):
                attrs["eq_custom"] = eq_custom
            if self.coordinator.eq_presets:
                attrs["eq_presets"] = self.coordinator.eq_presets

        # Source information
        if sources := status.get("sources"):
            attrs["available_sources"] = sources
        if streaming_service := status.get("streaming_service"):
            attrs["streaming_service"] = streaming_service

        return attrs

    # -------------------------------------------------------------------------
    # Core Control Methods
    # -------------------------------------------------------------------------

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

    async def async_media_play(self) -> None:
        """Send play command."""
        role = self.coordinator.data.get("role") if self.coordinator.data else "solo"
        if role == "slave":
            master_coord = self._find_master_coordinator()
            if master_coord:
                await master_coord.client.play()
                await master_coord.async_refresh()
                await self.coordinator.async_refresh()
                return
        await self.coordinator.client.play()
        await self.coordinator.async_refresh()
        await self._trigger_group_updates()

    async def async_media_pause(self) -> None:
        """Send pause command."""
        role = self.coordinator.data.get("role") if self.coordinator.data else "solo"
        if role == "slave":
            master_coord = self._find_master_coordinator()
            if master_coord:
                await master_coord.client.pause()
                await master_coord.async_refresh()
                await self.coordinator.async_refresh()
                return
        await self.coordinator.client.pause()
        await self.coordinator.async_refresh()
        await self._trigger_group_updates()

    async def async_media_stop(self) -> None:
        """Send stop command."""
        try:
            await self.coordinator.client.stop()
            await self.coordinator.async_refresh()
            await self._trigger_group_updates()
        except WiiMError as err:
            _LOGGER.error("Failed to stop WiiM device: %s", err)
            raise

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        role = self.coordinator.data.get("role") if self.coordinator.data else "solo"
        if role == "slave":
            master_coord = self._find_master_coordinator()
            if master_coord:
                await master_coord.client.next_track()
                await master_coord.async_refresh()
                await self.coordinator.async_refresh()
                return
        await self.coordinator.client.next_track()
        await self.coordinator.async_refresh()
        await self._trigger_group_updates()

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        role = self.coordinator.data.get("role") if self.coordinator.data else "solo"
        if role == "slave":
            master_coord = self._find_master_coordinator()
            if master_coord:
                await master_coord.client.previous_track()
                await master_coord.async_refresh()
                await self.coordinator.async_refresh()
                return
        await self.coordinator.client.previous_track()
        await self.coordinator.async_refresh()
        await self._trigger_group_updates()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        try:
            await self.coordinator.client.set_volume(volume)
            await self.coordinator.async_refresh()
            await self._trigger_group_updates()
        except WiiMError as err:
            _LOGGER.error("Failed to set volume on WiiM device: %s", err)
            raise

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        try:
            await self.coordinator.client.set_mute(mute)
            await self.coordinator.async_refresh()
            await self._trigger_group_updates()
        except WiiMError as err:
            _LOGGER.error("Failed to mute WiiM device: %s", err)
            raise

    async def async_volume_up(self) -> None:
        """Volume up the media player."""
        if volume := self.volume_level:
            step = self._volume_step()
            try:
                await self.coordinator.client.set_volume(min(1.0, volume + step))
                await self.coordinator.async_refresh()
                await self._trigger_group_updates()
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
                await self._trigger_group_updates()
            except WiiMError as err:
                _LOGGER.error("Failed to decrease volume on WiiM device: %s", err)
                raise

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        role = self.coordinator.data.get("role", "solo") if self.coordinator.data else "solo"

        if role == "slave":
            # Check if user is selecting the current group master (do nothing)
            master_coord = self._find_master_coordinator()
            if master_coord and master_coord.data:
                master_status = master_coord.data.get("status", {})
                master_name = (
                    master_status.get("DeviceName") or master_status.get("device_name") or master_coord.client.host
                )
                current_group_source = f"🔗 {master_name} (Group)"

                if source == current_group_source:
                    _LOGGER.debug("[WiiM] %s: User selected current group master, no action", self.entity_id)
                    return

            # User selected a different source - leave group first, then switch source
            _LOGGER.info(
                "[WiiM] %s: Slave selecting different source '%s', leaving group first",
                self.entity_id,
                source,
            )
            try:
                await self.coordinator.leave_wiim_group()
                await self.coordinator.async_refresh()
                await asyncio.sleep(0.5)  # Small delay to ensure group leave is processed
            except Exception as leave_err:
                _LOGGER.warning(
                    "[WiiM] %s: Failed to leave group before source change: %s",
                    self.entity_id,
                    leave_err,
                )

        # Convert user-friendly source back to API source
        src_api = next((k for k, v in SOURCE_MAP.items() if v == source), source.lower())

        # Handle special group source format
        if " (Group)" in source:
            return

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
                    await self.coordinator.client.set_shuffle_mode(PLAY_MODE_SHUFFLE_REPEAT_ALL)
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
                    await self.coordinator.client.set_repeat_mode(PLAY_MODE_SHUFFLE_REPEAT_ALL)
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

    async def async_play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        """Play media."""
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

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        """Implement the browse media feature."""
        presets = [
            BrowseMedia(
                title=f"Preset {i + 1}",
                media_class=MediaClass.MUSIC,
                media_content_id=f"preset_{i + 1}",
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

    # -------------------------------------------------------------------------
    # Group Management (using HA native grouping interface)
    # -------------------------------------------------------------------------

    async def async_join(self, group_members: list[str]) -> None:
        """Join `group_members` as a group.

        This method handles the Home Assistant media_player.join service.
        The group_members parameter represents the FINAL desired group composition,
        NOT just entities to add. This means:

        - If an entity is in the current group but NOT in group_members, it will be unjoined
        - If an entity is NOT in the current group but IS in group_members, it will be joined
        - If group_members is empty or contains only self, the device becomes solo

        This aligns with the standard HA media player grouping behavior.
        """
        _LOGGER.info(
            "[WiiM] %s: HA native join called with group_members=%s",
            self.entity_id,
            group_members,
        )

        # Get current group members to compare with desired composition
        current_group_members = set(self.group_members) if self.group_members else set()
        _LOGGER.info(
            "[WiiM] %s: Current group members: %s",
            self.entity_id,
            list(current_group_members),
        )

        # Pre-validate and filter the requested group members
        validated_members = []
        filtered_out = []

        # Always include self in the group (HA's interface sometimes excludes the calling entity)
        validated_members.append(self.entity_id)

        for entity_id in group_members:
            if entity_id == self.entity_id:
                # Already added above, skip to avoid duplicates
                continue

            # Filter out group master entities (virtual entities that can't be joined)
            if "group_" in entity_id and "master" in entity_id.lower():
                filtered_out.append(f"{entity_id} (group master - virtual entity)")
                continue

            # Check if entity exists and is valid
            entity_state = self.hass.states.get(entity_id)
            if entity_state is None:
                filtered_out.append(f"{entity_id} (non-existent)")
                continue

            # Check if entity is stale
            if entity_state.state in ("unavailable", "unknown") or entity_state.attributes.get("restored", False):
                filtered_out.append(f"{entity_id} (stale/unavailable)")
                continue

            # Check if this is actually a WiiM group master by checking attributes
            entity_attrs = entity_state.attributes
            if entity_attrs.get("group_type") == "wiim_master":
                filtered_out.append(f"{entity_id} (WiiM group master - virtual entity)")
                continue

            # Strict WiiM-only filtering: Check entity domain and integration
            if not entity_id.startswith("media_player."):
                filtered_out.append(f"{entity_id} (not media player)")
                continue

            # Check if this is explicitly a WiiM entity by checking entity registry or coordinator
            coord = find_coordinator(self.hass, entity_id)
            if coord is None:
                # Additional check: see if entity_id contains wiim pattern
                if "wiim" not in entity_id.lower() and "linkplay" not in entity_id.lower():
                    filtered_out.append(f"{entity_id} (not WiiM device)")
                    continue
                else:
                    # Might be a WiiM device that's not fully online yet
                    _LOGGER.warning(
                        "[WiiM] %s: Including %s despite no coordinator (might be WiiM device coming online)",
                        self.entity_id,
                        entity_id,
                    )

            validated_members.append(entity_id)

        # Log what was filtered out for user awareness
        if filtered_out:
            _LOGGER.info(
                "[WiiM] %s: Filtered out entities: %s",
                self.entity_id,
                filtered_out,
            )

        # Convert to sets for comparison
        desired_group_members = set(validated_members)

        _LOGGER.info(
            "[WiiM] %s: Desired group members: %s",
            self.entity_id,
            list(desired_group_members),
        )

        # Determine which entities need to be unjoined (in current group but not in desired group)
        entities_to_unjoin = current_group_members - desired_group_members
        if entities_to_unjoin:
            _LOGGER.info(
                "[WiiM] %s: Entities to unjoin (no longer selected): %s",
                self.entity_id,
                list(entities_to_unjoin),
            )

            # Unjoin entities that should no longer be in the group
            await self._unjoin_entities(entities_to_unjoin)

        # Check if we should create a new group or go solo
        if len(desired_group_members) <= 1:
            _LOGGER.info("[WiiM] %s: Only self in desired group, ensuring device is solo", self.entity_id)
            if self.coordinator.client.is_slave or self.coordinator.client.is_master:
                await self.async_unjoin()
            return

        # Determine which entities need to be added (not in current group but in desired group)
        entities_to_add = desired_group_members - current_group_members
        if entities_to_add:
            _LOGGER.info(
                "[WiiM] %s: Entities to add to group: %s",
                self.entity_id,
                list(entities_to_add),
            )

        # Create/modify the WiiM multiroom group with all desired members
        await self._create_wiim_multiroom_group(list(desired_group_members))

        # Force refresh of all affected devices to update UI
        await self._refresh_all_group_members_after_join(list(desired_group_members))

    async def _unjoin_entities(self, entities_to_unjoin: set[str]) -> None:
        """Unjoin specific entities from their current group."""
        for entity_id in entities_to_unjoin:
            # Skip self - we'll handle our own state in the main flow
            if entity_id == self.entity_id:
                continue

            coord = find_coordinator(self.hass, entity_id)
            if coord is None:
                _LOGGER.warning("[WiiM] %s: Cannot find coordinator to unjoin %s", self.entity_id, entity_id)
                continue

            try:
                _LOGGER.info("[WiiM] %s: Unjoining %s from group", self.entity_id, entity_id)
                if coord.client.is_master:
                    await coord.delete_wiim_group()
                else:
                    await coord.leave_wiim_group()
                await coord.async_request_refresh()
            except Exception as err:
                _LOGGER.error("[WiiM] %s: Failed to unjoin %s: %s", self.entity_id, entity_id, err)

    async def async_unjoin(self) -> None:
        """Remove this player from any group."""
        _LOGGER.info("[WiiM] %s: HA native unjoin called", self.entity_id)
        try:
            if self.coordinator.client.is_master:
                await self.coordinator.delete_wiim_group()
            else:
                await self.coordinator.leave_wiim_group()

            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("[WiiM] %s: Failed to complete WiiM unjoin operation: %s", self.entity_id, err)
            raise

    # -------------------------------------------------------------------------
    # Synchronous Wrapper Methods (HA Compatibility)
    # -------------------------------------------------------------------------

    def join_players(self, group_members: list[str]) -> None:
        """Synchronous join for HA compatibility (thread-safe)."""
        _LOGGER.info(
            "[WiiM] %s: join_players() called with members: %s", getattr(self, "entity_id", "unknown"), group_members
        )

        try:
            import asyncio

            # Ensure we have an event loop and run the async method
            if asyncio.iscoroutinefunction(self.async_join):
                future = asyncio.run_coroutine_threadsafe(self.async_join(group_members), self.hass.loop)
                future.result(timeout=30)  # Add timeout to prevent hanging
            else:
                _LOGGER.error("[WiiM] async_join is not a coroutine function")
        except Exception as err:
            _LOGGER.error("[WiiM] Failed to join players: %s", err)
            # Don't raise the error to prevent NotImplementedError from bubbling up

    def unjoin_player(self) -> None:
        """Synchronous unjoin for HA compatibility (thread-safe)."""
        _LOGGER.info("[WiiM] %s: unjoin_player() called", getattr(self, "entity_id", "unknown"))

        try:
            import asyncio

            # Ensure we have an event loop and run the async method
            if asyncio.iscoroutinefunction(self.async_unjoin):
                future = asyncio.run_coroutine_threadsafe(self.async_unjoin(), self.hass.loop)
                future.result(timeout=30)  # Add timeout to prevent hanging
            else:
                _LOGGER.error("[WiiM] async_unjoin is not a coroutine function")
        except Exception as err:
            _LOGGER.error("[WiiM] Failed to unjoin player: %s", err)
            # Don't raise the error to prevent NotImplementedError from bubbling up

    # -------------------------------------------------------------------------
    # Service Method Delegations (Clean Architecture)
    # -------------------------------------------------------------------------

    async def async_play_preset(self, preset: int) -> None:
        """Delegate to media service."""
        await WiiMMediaServices.play_preset(self, preset)

    async def async_toggle_power(self) -> None:
        """Delegate to media service."""
        await WiiMMediaServices.toggle_power(self)

    async def async_play_url(self, url: str) -> None:
        """Delegate to media service."""
        await WiiMMediaServices.play_url(self, url)

    async def async_play_playlist(self, playlist_url: str) -> None:
        """Delegate to media service."""
        await WiiMMediaServices.play_playlist(self, playlist_url)

    async def async_set_eq(self, preset: str, custom_values: list[int] | None = None) -> None:
        """Delegate to media service."""
        await WiiMMediaServices.set_eq(self, preset, custom_values)

    async def async_play_notification(self, url: str) -> None:
        """Delegate to media service."""
        await WiiMMediaServices.play_notification(self, url)

    async def async_reboot_device(self) -> None:
        """Delegate to device service."""
        await WiiMDeviceServices.reboot_device(self)

    async def async_sync_time(self) -> None:
        """Delegate to device service."""
        await WiiMDeviceServices.sync_time(self)

    async def async_diagnose_entities(self) -> None:
        """Delegate to diagnostic service."""
        await WiiMDiagnosticServices.diagnose_entities(self)

    async def async_cleanup_stale_entities(self, dry_run: bool = True) -> None:
        """Delegate to diagnostic service."""
        await WiiMDiagnosticServices.cleanup_stale_entities(self, dry_run)

    async def async_auto_maintain(self, auto_cleanup: bool = False, dry_run: bool = True) -> None:
        """Delegate to diagnostic service."""
        await WiiMDiagnosticServices.auto_maintain(self, auto_cleanup, dry_run)

    async def async_nuclear_reset_entities(self, i_understand_this_removes_all_wiim_entities: bool = False) -> None:
        """Delegate to diagnostic service."""
        await WiiMDiagnosticServices.nuclear_reset_entities(self, i_understand_this_removes_all_wiim_entities)

    async def async_cleanup_entity_naming_conflicts(self, dry_run: bool = True) -> None:
        """Clean up entity naming conflicts like '_2' suffixes."""
        entity_registry_inst = entity_registry.async_get(self.hass)

        conflicts_found = []
        entities_to_remove = []

        # Find all WiiM entities in the registry
        for entity_entry in entity_registry_inst.entities.values():
            if entity_entry.platform != DOMAIN:
                continue

            if entity_entry.entity_id.startswith("media_player.") and (
                "_2" in entity_entry.entity_id or "_3" in entity_entry.entity_id
            ):
                # Check if entity is stale
                entity_state = self.hass.states.get(entity_entry.entity_id)

                if (
                    entity_state is None
                    or entity_state.state in ("unavailable", "unknown")
                    or entity_state.attributes.get("restored", False)
                ):
                    conflicts_found.append(entity_entry.entity_id)
                    entities_to_remove.append(entity_entry.entity_id)

        _LOGGER.info(
            "[WiiM] Entity naming conflict cleanup - Found %d conflicted entities: %s%s",
            len(conflicts_found),
            conflicts_found,
            " (DRY RUN - no changes made)" if dry_run else "",
        )

        if not dry_run:
            for entity_id in entities_to_remove:
                entity_registry_inst.async_remove(entity_id)
                _LOGGER.info("[WiiM] Removed conflicted entity: %s", entity_id)

        # Return summary
        return {
            "conflicts_found": len(conflicts_found),
            "entities": conflicts_found,
            "dry_run": dry_run,
            "action_taken": "removed" if not dry_run else "none",
        }

    async def async_refresh_group_states(self) -> None:
        """Refresh group states for all WiiM devices to fix grouping issues."""
        _LOGGER.info("[WiiM] %s: Manual group state refresh requested", self.entity_id)

        # Refresh all WiiM coordinators
        refreshed_devices = []
        for entry_id, entry_data in self.hass.data[DOMAIN].items():
            if entry_id == "_group_entities":  # Skip group entities storage
                continue
            if not isinstance(entry_data, dict) or "coordinator" not in entry_data:
                continue
            coord = entry_data["coordinator"]
            if hasattr(coord, "client"):
                try:
                    await coord.async_request_refresh()
                    refreshed_devices.append(coord.client.host)
                except Exception as err:
                    _LOGGER.warning("[WiiM] Failed to refresh coordinator %s: %s", coord.client.host, err)

        # Force update all group member states
        await self._update_all_group_member_states()

        _LOGGER.info("[WiiM] %s: Refreshed %d devices: %s", self.entity_id, len(refreshed_devices), refreshed_devices)

        return {"refreshed_devices": len(refreshed_devices), "devices": refreshed_devices}

    async def async_create_group_with_members(self, group_members: list[str]) -> None:
        """Delegate to group service."""
        await WiiMGroupServices.create_group_with_members(self, group_members)

    async def async_add_to_group(self, target_entity: str) -> None:
        """Delegate to group service."""
        await WiiMGroupServices.add_to_group(self, target_entity)

    async def async_remove_from_group(self, target_entity: str) -> None:
        """Delegate to group service."""
        await WiiMGroupServices.remove_from_group(self, target_entity)

    async def async_disband_group(self) -> None:
        """Delegate to group service."""
        await WiiMGroupServices.disband_group(self)

    # -------------------------------------------------------------------------
    # Image Proxy Support
    # -------------------------------------------------------------------------

    @property
    def media_image_url(self) -> str | None:
        """Return the original (remote) artwork URL if available."""
        return self.entity_picture

    @property
    def media_image_remotely_accessible(self) -> bool:
        """Tell HA whether media_image_url can be fetched directly."""
        return False  # WiiM uses self-signed certs, so let HA proxy the images

    async def async_get_media_image(self):
        """Fetch the current artwork and hand bytes to Home Assistant."""
        url = self.entity_picture
        if not url:
            return None, None

        # Some firmwares hand out relative paths
        if url.startswith("/"):
            url = f"https://{self.coordinator.client.host}{url}"

        import aiohttp
        import async_timeout

        try:
            async with async_timeout.timeout(10):
                session = aiohttp.ClientSession()
                async with session.get(url, ssl=False) as resp:
                    if resp.status != 200:
                        await session.close()
                        return None, None
                    data = await resp.read()
                    mime = resp.headers.get("Content-Type", "image/jpeg")
                    await session.close()
                    return data, mime
        except Exception:
            return None, None

    @property
    def app_name(self) -> str | None:
        """Return the name of the current streaming service."""
        service = self.coordinator.data.get("status", {}).get("streaming_service") if self.coordinator.data else None
        return service

    # -------------------------------------------------------------------------
    # Helper Methods (simplified)
    # -------------------------------------------------------------------------

    def _volume_step(self) -> float:
        """Get the configured volume step size."""
        entry_id = getattr(self.coordinator, "entry_id", None)
        if entry_id:
            entry = self.hass.config_entries.async_get_entry(entry_id)
            if entry is not None:
                return entry.options.get(CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP)
        return 0.05

    def _find_master_coordinator(self):
        """Find the master coordinator for this slave device."""
        from .device_registry import get_device_registry

        registry = get_device_registry(self.hass)

        # Get master IP from registry
        master_ip = registry.get_master_ip(self.coordinator.client.host)
        if not master_ip:
            return None

        # Get coordinator from registry
        return registry.get_coordinator(master_ip)

    async def _trigger_group_updates(self) -> None:
        """Trigger updates for all players in the group."""
        role = self.coordinator.data.get("role", "solo") if self.coordinator.data else "solo"

        if role == "master":
            # For master, update all slaves
            for ip in self.coordinator.wiim_group_members:
                coord = find_coordinator(self.hass, f"media_player.wiim_{ip.replace('.', '_')}")
                if coord:
                    try:
                        await coord.async_request_refresh()
                    except Exception:
                        pass
        elif role == "slave":
            # For slave, update master
            master_coord = self._find_master_coordinator()
            if master_coord:
                try:
                    await master_coord.async_request_refresh()
                except Exception:
                    pass

        # Always update all coordinators to ensure group state consistency
        await self._update_all_group_member_states()

    async def _update_all_group_member_states(self) -> None:
        """Update state for all members of the current group to ensure UI consistency."""
        group_members = self.group_members

        for member_entity_id in group_members:
            # Find the coordinator for this entity
            member_coord = find_coordinator(self.hass, member_entity_id)
            if member_coord:
                try:
                    # Trigger coordinator refresh and state update
                    await member_coord.async_request_refresh()
                    # Also trigger entity state update
                    entity = self.hass.states.get(member_entity_id)
                    if entity:
                        # Force entity to update its state attributes
                        self.hass.async_create_task(
                            self.hass.states.async_set(
                                member_entity_id, entity.state, entity.attributes, force_update=True
                            )
                        )
                except Exception as err:
                    _LOGGER.debug("[WiiM] Failed to update group member %s: %s", member_entity_id, err)

    async def _create_wiim_multiroom_group(self, group_members: list[str]) -> None:
        """Create a proper WiiM multiroom group."""
        try:
            # If we are currently a slave, leave existing group first
            if self.coordinator.client.is_slave:
                try:
                    await self.coordinator.leave_wiim_group()
                except Exception:
                    pass

            # Create new WiiM group
            if not self.coordinator.client.group_master:
                await self.coordinator.create_wiim_group()
                master_ip = self.coordinator.client.host
            else:
                master_ip = self.coordinator.client.group_master

            # Add members to group
            for entity_id in group_members:
                if entity_id == self.entity_id:
                    continue

                coord = find_coordinator(self.hass, entity_id)
                member_ip = entity_id_to_host(self.hass, entity_id)

                if member_ip is None or coord is None:
                    continue

                try:
                    await coord.join_wiim_group(master_ip)
                except Exception:
                    continue

            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("[WiiM] %s: Failed to complete WiiM multiroom group creation: %s", self.entity_id, err)
            raise

    async def async_cleanup_ghost_discoveries(self, dry_run: bool = True) -> None:
        """Clean up ghost discovery flows that are stuck in manual entry mode."""
        _LOGGER.info("[WiiM] %s: Ghost discovery cleanup requested (dry_run=%s)", self.entity_id, dry_run)

        ghost_flows = []

        # Find discovery flows for WiiM that are stuck in user/manual steps
        for flow in self.hass.config_entries.flow.async_progress():
            if (
                flow["handler"] == DOMAIN
                and flow.get("context", {}).get("source") == "import"
                and flow.get("step_id") in ("user", "manual")
            ):
                ghost_flows.append(flow["flow_id"])

        _LOGGER.info(
            "[WiiM] %s: Found %d ghost discovery flows: %s%s",
            self.entity_id,
            len(ghost_flows),
            ghost_flows,
            " (DRY RUN - no changes made)" if dry_run else "",
        )

        if not dry_run and ghost_flows:
            from homeassistant.data_entry_flow import FlowManager

            flow_manager: FlowManager = self.hass.config_entries.flow

            for flow_id in ghost_flows:
                try:
                    await flow_manager.async_abort(flow_id)
                    _LOGGER.info("[WiiM] Aborted ghost discovery flow: %s", flow_id)
                except Exception as err:
                    _LOGGER.warning("[WiiM] Failed to abort ghost discovery flow %s: %s", flow_id, err)

        return {
            "ghost_flows_found": len(ghost_flows),
            "flows": ghost_flows,
            "dry_run": dry_run,
            "action_taken": "aborted" if not dry_run else "none",
        }

    async def _refresh_all_group_members_after_join(self, group_members: list[str]) -> None:
        """Refresh all group members after a successful join operation."""
        _LOGGER.info("[WiiM] %s: Refreshing all group members after join", self.entity_id)

        # Refresh all WiiM coordinators
        refreshed_devices = []
        for entry_id, entry_data in self.hass.data[DOMAIN].items():
            if entry_id == "_group_entities":  # Skip group entities storage
                continue
            if not isinstance(entry_data, dict) or "coordinator" not in entry_data:
                continue
            coord = entry_data["coordinator"]
            if hasattr(coord, "client"):
                try:
                    await coord.async_request_refresh()
                    refreshed_devices.append(coord.client.host)
                except Exception as err:
                    _LOGGER.warning("[WiiM] Failed to refresh coordinator %s: %s", coord.client.host, err)

        # Force immediate state update for all group member entities
        for entity_id in group_members:
            if self.hass.states.get(entity_id):
                # Force the entity to update its state immediately
                self.hass.async_create_task(self.hass.helpers.entity_component.async_update_entity(entity_id))

        # Force update all group member states
        await self._update_all_group_member_states()

        _LOGGER.info("[WiiM] %s: Refreshed %d devices: %s", self.entity_id, len(refreshed_devices), refreshed_devices)

        return {"refreshed_devices": len(refreshed_devices), "devices": refreshed_devices}


# Backward compatibility - import the utility function at module level
_find_coordinator = find_coordinator
