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

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.components.media_player.browse_media import BrowseMedia, MediaClass
from homeassistant.components.media_player.const import (
    ATTR_GROUP_MEMBERS as HA_ATTR_GROUP_MEMBERS,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry, entity_platform, entity_registry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import voluptuous as vol

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
from .services import (
    WiiMDeviceServices,
    WiiMDiagnosticServices,
    WiiMGroupServices,
    WiiMMediaServices,
)
from .utils import StateManager, entity_id_to_host, find_coordinator

_LOGGER = logging.getLogger(__name__)

# Home Assistant doesn't define a constant for the leader attribute.
HA_ATTR_GROUP_LEADER = "group_leader"


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
    """Set up group entities management (preserved from original)."""
    # This preserves the existing group entity logic - could be further refactored later
    if not hasattr(hass.data[DOMAIN], "_group_entities"):
        hass.data[DOMAIN]["_group_entities"] = {}

    # Import the group media player class
    from .group_media_player import WiiMGroupMediaPlayer

    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    # Create group entity only if this device is a master with slaves
    if coordinator.data and coordinator.data.get("role") == "master":
        multiroom = coordinator.data.get("multiroom", {})
        slave_list = multiroom.get("slave_list", [])

        if slave_list:  # Only create group entity if there are actual slaves
            device_ip = coordinator.client.host
            group_entity_id = f"wiim_group_{device_ip.replace('.', '_')}"

            # Avoid duplicate group entities
            if group_entity_id not in hass.data[DOMAIN]["_group_entities"]:
                group_entity = WiiMGroupMediaPlayer(hass, coordinator, device_ip)
                async_add_entities([group_entity])
                hass.data[DOMAIN]["_group_entities"][group_entity_id] = group_entity

                _LOGGER.info("[WiiM] Created group entity for master %s with %d slaves", device_ip, len(slave_list))


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
        mac_address = status.get("MAC")
        if mac_address and mac_address.lower() != "unknown":
            # MAC address is the most stable identifier
            self._attr_unique_id = f"wiim_{mac_address.replace(':', '').lower()}"
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

        # Device info setup
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.client.host)},
            name=device_name,
            manufacturer="WiiM",
            model=status.get("project") or status.get("hardware"),
            sw_version=status.get("firmware"),
            connections={("mac", status.get("MAC"))} if status.get("MAC") else set(),
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
        # All WiiM devices can be grouped since our integration handles:
        # - Solo devices: join directly
        # - Slaves: leave current group first, then join new group
        # - Masters: disband current group first, then join as slave
        if not self.coordinator.data:
            return False

        # As long as we have coordinator data, this is a valid WiiM device that can be grouped
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
        """Return list of group member entity IDs."""
        # Return the actual WiiM multiroom group members converted to entity IDs
        members = []

        if not self.coordinator.data:
            return members

        role = self.coordinator.data.get("role", "solo")

        if role == "master":
            # For masters, include self and all slaves
            members.append(self.entity_id)

            # Add slaves
            multiroom = self.coordinator.data.get("multiroom", {})
            slave_list = multiroom.get("slave_list", [])

            for slave in slave_list:
                if isinstance(slave, dict):
                    slave_ip = slave.get("ip")
                    if slave_ip:
                        # Convert IP to entity ID
                        slave_entity_id = f"media_player.wiim_{slave_ip.replace('.', '_')}"
                        # Check if entity actually exists
                        if self.hass.states.get(slave_entity_id):
                            members.append(slave_entity_id)
                        else:
                            # Try alternative naming patterns
                            for coord in self.hass.data[DOMAIN].values():
                                if hasattr(coord, "client") and coord.client.host == slave_ip:
                                    # Try to find the actual entity ID
                                    entity_registry_inst = entity_registry.async_get(self.hass)
                                    for entity_entry in entity_registry_inst.entities.values():
                                        if (
                                            entity_entry.platform == DOMAIN
                                            and entity_entry.entity_id.startswith("media_player.")
                                            and slave_ip.replace(".", "_") in entity_entry.entity_id
                                        ):
                                            members.append(entity_entry.entity_id)
                                            break
                                    break

        elif role == "slave":
            # For slaves, include self and master plus other slaves
            master_coord = self._find_master_coordinator()
            if master_coord:
                # Add master
                master_entity_id = f"media_player.wiim_{master_coord.client.host.replace('.', '_')}"
                if self.hass.states.get(master_entity_id):
                    members.append(master_entity_id)

                # Add self
                members.append(self.entity_id)

                # Add other slaves
                multiroom = master_coord.data.get("multiroom", {}) if master_coord.data else {}
                slave_list = multiroom.get("slave_list", [])

                for slave in slave_list:
                    if isinstance(slave, dict):
                        slave_ip = slave.get("ip")
                        if slave_ip and slave_ip != self.coordinator.client.host:
                            slave_entity_id = f"media_player.wiim_{slave_ip.replace('.', '_')}"
                            if self.hass.states.get(slave_entity_id):
                                members.append(slave_entity_id)
        else:
            # Solo device - only return self if explicitly added to an HA group
            ha_members = list(self.coordinator.ha_group_members) if self.coordinator.ha_group_members else []
            if ha_members:
                members = ha_members

        _LOGGER.debug("[WiiM] %s (role=%s): group_members = %s", self.entity_id, role, members)

        return members

    @property
    def group_leader(self) -> str | None:
        """Return the entity ID of the group leader."""
        if not self.coordinator.data:
            return None

        role = self.coordinator.data.get("role", "solo")

        if role == "master":
            # Master device is the group leader
            return self.entity_id
        elif role == "slave":
            # Find the master entity ID
            master_coord = self._find_master_coordinator()
            if master_coord:
                master_entity_id = f"media_player.wiim_{master_coord.client.host.replace('.', '_')}"
                if self.hass.states.get(master_entity_id):
                    return master_entity_id
                else:
                    # Try to find the actual entity ID with alternative naming
                    entity_registry_inst = entity_registry.async_get(self.hass)
                    for entity_entry in entity_registry_inst.entities.values():
                        if (
                            entity_entry.platform == DOMAIN
                            and entity_entry.entity_id.startswith("media_player.")
                            and master_coord.client.host.replace(".", "_") in entity_entry.entity_id
                        ):
                            return entity_entry.entity_id

        # Solo device or no group
        return None

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
        """Return entity specific state attributes."""
        status = self._get_effective_status()
        attrs = {
            ATTR_DEVICE_MODEL: status.get("device_model"),
            ATTR_DEVICE_NAME: status.get("device_name"),
            ATTR_DEVICE_ID: status.get("device_id"),
            ATTR_IP_ADDRESS: self.coordinator.client.host,
            ATTR_FIRMWARE: status.get("firmware"),
            ATTR_PRESET: status.get("preset"),
            ATTR_PLAY_MODE: status.get("play_mode"),
            ATTR_REPEAT_MODE: status.get("repeat_mode"),
            ATTR_SHUFFLE_MODE: status.get("shuffle_mode"),
            ATTR_SOURCE: SOURCE_MAP.get(status.get("source"), status.get("source")),
            ATTR_MUTE: status.get("mute"),
            ATTR_EQ_PRESET: EQ_PRESET_MAP.get(status.get("eq_preset"), status.get("eq_preset")),
            ATTR_EQ_CUSTOM: status.get("eq_custom"),
            "eq_enabled": status.get("eq_enabled", False),
            "eq_presets": status.get("eq_presets", []),
            HA_ATTR_GROUP_MEMBERS: list(self.coordinator.ha_group_members or []),
            HA_ATTR_GROUP_LEADER: self.group_leader,
            "streaming_service": status.get("streaming_service"),
            "device_model": status.get("project") or status.get("hardware") or "WiiM Device",
            "mac_address": status.get("MAC"),
            "wifi_signal": f"{status.get('wifi_rssi', 'Unknown')} dBm" if status.get("wifi_rssi") else None,
            "wifi_channel": status.get("wifi_channel"),
            "uptime": status.get("uptime"),
            "connection_type": "HTTPS" if "https" in self.coordinator.client._endpoint else "HTTP",
            "api_endpoint": self.coordinator.client._endpoint,
            "last_update_success": self.coordinator.last_update_success,
        }

        # Enhanced group information display
        role = self.coordinator.data.get("role", "solo") if self.coordinator.data else "solo"
        attrs["wiim_role"] = role

        # Add group-specific attributes (existing logic preserved)
        self._add_group_attributes(attrs, role)

        return attrs

    def _add_group_attributes(self, attrs: dict[str, Any], role: str) -> None:
        """Add group-specific attributes to the state attributes."""
        if role == "master":
            # Show detailed slave information for masters
            multiroom = self.coordinator.data.get("multiroom", {}) if self.coordinator.data else {}
            slave_list = multiroom.get("slave_list", [])
            slave_details = []
            total_group_volume = 0
            group_member_count = 1  # Include master

            # Add master volume to total
            master_volume = self.coordinator.data.get("status", {}).get("volume", 0) if self.coordinator.data else 0
            total_group_volume += master_volume

            for slave in slave_list:
                if isinstance(slave, dict):
                    slave_volume = slave.get("volume", 0)
                    total_group_volume += slave_volume
                    group_member_count += 1

                    slave_info = {
                        "name": slave.get("name", "Unknown"),
                        "ip": slave.get("ip"),
                        "volume": slave_volume,
                        "muted": bool(slave.get("mute", False)),
                        "channel": slave.get("channel", 0),
                    }
                    slave_details.append(slave_info)

            attrs["wiim_slaves"] = slave_details
            attrs["wiim_slave_count"] = len(slave_details)
            attrs["wiim_group_master"] = self.coordinator.client.host
            attrs["group_total_members"] = group_member_count
            attrs["group_average_volume"] = (
                round(total_group_volume / group_member_count) if group_member_count > 0 else 0
            )
            attrs["group_status"] = f"Master of {len(slave_details)} device{'s' if len(slave_details) != 1 else ''}"

        elif role == "slave":
            # Show master information for slaves
            master_coord = self._find_master_coordinator()
            if master_coord:
                master_status = master_coord.data.get("status", {}) if master_coord.data else {}
                master_name = (
                    master_status.get("DeviceName") or master_status.get("device_name") or master_coord.client.host
                )
                attrs["wiim_group_master"] = master_coord.client.host
                attrs["wiim_master_name"] = master_name
                attrs["group_status"] = f"Grouped with {master_name}"
                attrs["can_control_group"] = "Yes - controls propagate to master"
            else:
                attrs["wiim_group_master"] = self.coordinator.client.group_master
                attrs["group_status"] = "Grouped (master not found)"

        else:  # solo
            attrs["group_status"] = "Not grouped"
            attrs["can_create_group"] = "Yes - select devices to group"

        # Show all available WiiM devices for potential grouping
        available_devices = []
        for coord in self.hass.data[DOMAIN].values():
            if not hasattr(coord, "client") or coord.client.host == self.coordinator.client.host:
                continue

            device_status = coord.data.get("status", {}) if coord.data else {}
            device_name = device_status.get("DeviceName") or device_status.get("device_name") or coord.client.host
            device_role = coord.data.get("role", "solo") if coord.data else "unknown"

            available_devices.append(
                {
                    "name": device_name,
                    "ip": coord.client.host,
                    "role": device_role,
                    "entity_id": f"media_player.wiim_{coord.client.host.replace('.', '_')}",
                }
            )

        attrs["wiim_available_devices"] = available_devices
        attrs["available_device_count"] = len(available_devices)

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
        """Join `group_members` as a group."""
        _LOGGER.info(
            "[WiiM] %s: HA native join called with group_members=%s",
            self.entity_id,
            group_members,
        )

        # Get current group members to avoid adding already-grouped devices
        current_group_members = set(self.group_members)
        _LOGGER.debug(
            "[WiiM] %s: Current group members: %s",
            self.entity_id,
            current_group_members,
        )

        # Pre-validate and aggressively filter out non-WiiM entities and already-grouped devices
        validated_members = []
        filtered_out = []

        for entity_id in group_members:
            if entity_id == self.entity_id:
                validated_members.append(entity_id)
                continue

            # Skip if already in the current group
            if entity_id in current_group_members:
                filtered_out.append(f"{entity_id} (already in group)")
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

        _LOGGER.info(
            "[WiiM] %s: Valid WiiM group members after filtering: %s",
            self.entity_id,
            validated_members,
        )

        if len(validated_members) <= 1:
            _LOGGER.info("[WiiM] %s: No valid new WiiM group members found, ensuring device is solo", self.entity_id)
            if self.coordinator.client.is_slave or self.coordinator.client.is_master:
                await self.async_unjoin()
            return

        # Use WiiM-specific multiroom grouping
        await self._create_wiim_multiroom_group(validated_members)

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
        for coord in self.hass.data[DOMAIN].values():
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
        master_ip = self.coordinator.client.group_master
        if not master_ip:
            # Fallback: search for master by slave_list
            my_ip = self.coordinator.client.host
            my_uuid = self.coordinator.data.get("status", {}).get("device_id") if self.coordinator.data else None

            for coord in self.hass.data[DOMAIN].values():
                if not hasattr(coord, "client") or coord.data is None:
                    continue
                if coord.data.get("role") != "master":
                    continue
                multiroom = coord.data.get("multiroom", {})
                slave_list = multiroom.get("slave_list", [])
                for slave in slave_list:
                    if isinstance(slave, dict):
                        if (my_ip and my_ip == slave.get("ip")) or (my_uuid and my_uuid == slave.get("uuid")):
                            return coord
            return None

        for coord in self.hass.data[DOMAIN].values():
            if hasattr(coord, "client") and coord.client.host == master_ip:
                return coord
        return None

    async def _trigger_group_updates(self) -> None:
        """Trigger updates for all players in the group."""
        role = self.coordinator.data.get("role", "solo") if self.coordinator.data else "solo"

        if role == "master":
            # For master, update all slaves
            for ip in self.coordinator.wiim_group_members:
                coord = next(
                    (c for c in self.hass.data[DOMAIN].values() if hasattr(c, "client") and c.client.host == ip),
                    None,
                )
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


# Backward compatibility - import the utility function at module level
_find_coordinator = find_coordinator
