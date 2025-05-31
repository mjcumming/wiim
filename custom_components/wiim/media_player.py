"""WiiM media player entity."""

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
from homeassistant.helpers import entity_platform
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
    EQ_PRESET_CUSTOM,
    EQ_PRESET_MAP,
    PLAY_MODE_NORMAL,
    PLAY_MODE_REPEAT_ALL,
    PLAY_MODE_REPEAT_ONE,
    PLAY_MODE_SHUFFLE,
    PLAY_MODE_SHUFFLE_REPEAT_ALL,
    SOURCE_MAP,
)
from .coordinator import WiiMCoordinator
from .group_media_player import WiiMGroupMediaPlayer

_LOGGER = logging.getLogger(__name__)

# Home Assistant doesn't define a constant for the leader attribute.
HA_ATTR_GROUP_LEADER = "group_leader"


async def _cleanup_conflicting_entities(hass: HomeAssistant, coordinator: WiiMCoordinator) -> None:
    """Clean up any conflicting entities that might cause _2 suffix issues."""
    try:
        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)

        # Generate expected entity ID for this coordinator
        status = coordinator.data.get("status", {}) if coordinator.data else {}
        device_name = status.get("DeviceName") or status.get("device_name") or coordinator.client.host
        safe_name = (
            device_name.replace(" ", "_")
            .replace("(", "")
            .replace(")", "")
            .replace(",", "")
            .replace(".", "_")
            .replace("none", "")
            .replace("null", "")
            .lower()
        )

        # Get device UUID for more reliable unique identification
        device_id = status.get("uuid") or status.get("device_id") or coordinator.client.host

        # More aggressive cleanup - remove ALL potential conflicts
        potential_conflicts = [
            # Legacy patterns
            f"media_player.wiim_{coordinator.client.host.replace('.', '_')}",
            f"media_player.{safe_name}",
            f"media_player.wiim_{safe_name}",
            # With suffixes that HA might have added
            f"media_player.{safe_name}_2",
            f"media_player.{safe_name}_3",
            f"media_player.{safe_name}_4",
            f"media_player.wiim_{safe_name}_2",
            f"media_player.wiim_{safe_name}_3",
            f"media_player.wiim_{safe_name}_4",
            # IP-based patterns with suffixes
            f"media_player.wiim_{coordinator.client.host.replace('.', '_')}_2",
            f"media_player.wiim_{coordinator.client.host.replace('.', '_')}_3",
            f"media_player.wiim_{coordinator.client.host.replace('.', '_')}_4",
        ]

        removed_count = 0
        for conflict_id in potential_conflicts:
            existing_entry = ent_reg.async_get(conflict_id)
            if existing_entry and existing_entry.platform == DOMAIN:
                # Check if this entity corresponds to our coordinator
                if existing_entry.unique_id == coordinator.client.host or existing_entry.unique_id == device_id:
                    # This is our entity but with wrong name - remove it so we can recreate with proper name
                    _LOGGER.info(
                        "[WiiM] Removing our own entity with conflicting name: %s (unique_id: %s)",
                        conflict_id,
                        existing_entry.unique_id,
                    )
                    ent_reg.async_remove(conflict_id)
                    removed_count += 1
                else:
                    # Check if this entity is stale (not corresponding to active coordinator)
                    entity_state = hass.states.get(conflict_id)
                    if (
                        entity_state is None
                        or entity_state.state in ("unavailable", "unknown")
                        or entity_state.attributes.get("restored", False)
                    ):
                        _LOGGER.info(
                            "[WiiM] Cleaning up conflicting stale entity: %s (unique_id: %s)",
                            conflict_id,
                            existing_entry.unique_id,
                        )
                        ent_reg.async_remove(conflict_id)
                        removed_count += 1

        if removed_count > 0:
            _LOGGER.info(
                "[WiiM] Cleaned up %d conflicting entities for %s",
                removed_count,
                coordinator.client.host,
            )

    except Exception as cleanup_err:
        _LOGGER.debug(
            "[WiiM] Failed to cleanup conflicting entities for %s: %s",
            coordinator.client.host,
            cleanup_err,
        )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM media player from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    # Automatic cleanup of potential conflicting entities before creating new ones
    await _cleanup_conflicting_entities(hass, coordinator)

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

    # --- Group entity management ---
    if not hasattr(hass.data[DOMAIN], "_group_entities"):
        hass.data[DOMAIN]["_group_entities"] = {}

    async def update_group_entities():
        """Create or remove group entities based on coordinator group registry and user preferences."""
        group_entities = hass.data[DOMAIN]["_group_entities"]
        all_coordinators = set()
        ent_reg = None

        # Create a group entity only for devices where user has enabled the option
        for config_entry in hass.config_entries.async_entries(DOMAIN):
            if config_entry.entry_id not in hass.data[DOMAIN]:
                continue

            coord = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
            if not hasattr(coord, "client") or coord.data is None:
                continue

            device_ip = coord.client.host
            all_coordinators.add(device_ip)

            # Check if user has enabled group entities for this device
            enable_group_entity = config_entry.options.get("own_group_entity", False)
            if not enable_group_entity:
                # User has disabled group entities for this device
                continue

            # Only create group entity for master or solo devices
            role = coord.data.get("role", "solo")
            if role not in ("master", "solo"):
                continue

            if device_ip in group_entities:
                continue  # already have runtime entity

            # Build unique_id for the group entity
            status = coord.data.get("status", {})
            device_name = status.get("DeviceName") or status.get("device_name") or device_ip
            safe_name = (  # noqa: F841
                device_name.replace(" ", "_")
                .replace("(", "")
                .replace(")", "")
                .replace(",", "")
                .replace(".", "_")
                .replace("none", "")
                .replace("null", "")
                .lower()
            )
            unique_id = f"wiim_master_{device_ip.replace('.', '_')}_{safe_name}"

            # Check entity registry – skip creating if it already exists
            if ent_reg is None:
                from homeassistant.helpers import entity_registry as er

                ent_reg = er.async_get(hass)

            # Check if entity already exists in registry
            existing_entity_id = ent_reg.async_get_entity_id("media_player", DOMAIN, unique_id)
            if existing_entity_id:
                _LOGGER.debug(
                    "[WiiM] Group entity already exists in registry: %s",
                    existing_entity_id,
                )
                continue  # entity already registered, will be restored by HA

            # Safe to create new runtime entity - group entity (user enabled)
            _LOGGER.info("[WiiM] Creating group entity for %s (user enabled option)", device_ip)
            group_entity = WiiMGroupMediaPlayer(hass, coord, device_ip)
            async_add_entities([group_entity])
            group_entities[device_ip] = group_entity

        # Remove group entities for coordinators that no longer exist OR where user disabled option
        for device_ip in list(group_entities.keys()):
            should_remove = False

            if device_ip not in all_coordinators:
                # Coordinator no longer exists
                should_remove = True
            else:
                # Check if user has disabled group entities for this device
                for config_entry in hass.config_entries.async_entries(DOMAIN):
                    if config_entry.entry_id not in hass.data[DOMAIN]:
                        continue

                    coord = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
                    if hasattr(coord, "client") and coord.client.host == device_ip:
                        enable_group_entity = config_entry.options.get("own_group_entity", False)
                        if not enable_group_entity:
                            should_remove = True
                        break

            if should_remove:
                group_entity = group_entities.pop(device_ip)

                # Properly remove the entity from Home Assistant
                _LOGGER.info(
                    "[WiiM] Removing group entity for %s (option disabled or coordinator removed)",
                    device_ip,
                )

                # First remove from entity registry if it exists
                if ent_reg is None:
                    from homeassistant.helpers import entity_registry as er

                    ent_reg = er.async_get(hass)

                # Find and remove the entity from registry
                entity_id = group_entity.entity_id if hasattr(group_entity, "entity_id") else None
                if entity_id:
                    entity_entry = ent_reg.async_get(entity_id)
                    if entity_entry:
                        _LOGGER.debug("[WiiM] Removing entity %s from registry", entity_id)
                        ent_reg.async_remove(entity_id)

                # Then remove the entity itself
                try:
                    await group_entity.async_remove()
                except Exception as remove_err:
                    _LOGGER.warning(
                        "[WiiM] Failed to remove group entity for %s: %s",
                        device_ip,
                        remove_err,
                    )

    # Listen for coordinator updates to refresh group entities
    async def _on_coordinator_update():
        await update_group_entities()

    # Register the listener properly for async
    def _listener():
        hass.async_create_task(_on_coordinator_update())

    coordinator.async_add_listener(_listener)

    # Listen for options updates to create/remove group entities when user changes settings
    async def _on_options_update(hass, config_entry):
        """Handle options updates to create/remove group entities."""
        await update_group_entities()

    config_entry.add_update_listener(_on_options_update)

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

        # Get device UUID for reliable unique identification
        device_uuid = status.get("uuid") or status.get("device_id")
        device_name = status.get("DeviceName") or status.get("device_name") or coordinator.client.host

        # Enhanced naming for master devices
        role = coordinator.data.get("role", "solo") if coordinator.data else "solo"
        if role == "master":
            multiroom = coordinator.data.get("multiroom", {})
            slave_count = len(multiroom.get("slave_list", []))
            if slave_count > 0:
                device_name = f"{device_name} (Master of {slave_count})"
        elif role == "slave":
            device_name = f"{device_name} (Grouped)"

        # Use UUID-based unique_id if available, otherwise fall back to IP
        if device_uuid and device_uuid != coordinator.client.host:
            # Primary: UUID-based unique_id (most stable)
            self._attr_unique_id = f"wiim_{device_uuid}"
            _LOGGER.debug(
                "[WiiM] %s: Using UUID-based unique_id: %s",
                coordinator.client.host,
                self._attr_unique_id,
            )
        else:
            # Fallback: IP-based unique_id (still reliable)
            self._attr_unique_id = f"wiim_{coordinator.client.host.replace('.', '_')}"
            _LOGGER.debug(
                "[WiiM] %s: Using IP-based unique_id: %s (no UUID available)",
                coordinator.client.host,
                self._attr_unique_id,
            )

        _LOGGER.debug(
            "[WiiM] %s: Entity naming - device_name: %s, role: %s, unique_id: %s",
            coordinator.client.host,
            device_name,
            role,
            self._attr_unique_id,
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.host)},
            name=device_name,
            manufacturer="WiiM",
            model=status.get("project") or status.get("hardware"),
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
        )

        # Add grouping support - check if user prefers HA native or WiiM custom
        # NOTE: self.hass is now available after super().__init__()
        try:
            entry_id = getattr(coordinator, "entry_id", None)
            if entry_id and hasattr(self, "hass"):
                entry = self.hass.config_entries.async_get_entry(entry_id)
                use_ha_native_grouping = entry.options.get("use_ha_native_grouping", True) if entry else True
            else:
                use_ha_native_grouping = True  # Default to HA native for new setups
        except Exception as config_err:
            _LOGGER.debug(
                "[WiiM] %s: Failed to get grouping config, using defaults: %s",
                coordinator.client.host,
                config_err,
            )
            use_ha_native_grouping = True  # Safe default

        if use_ha_native_grouping:
            # Use HA's native grouping (works with new JOIN UI)
            base_features |= MediaPlayerEntityFeature.GROUPING
            _LOGGER.debug(
                "[WiiM] %s: Using HA native grouping (compatible with JOIN UI)",
                coordinator.client.host,
            )
        else:
            # Use WiiM custom grouping only (advanced users)
            _LOGGER.debug(
                "[WiiM] %s: Using WiiM custom grouping only (advanced mode)",
                coordinator.client.host,
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
    def device_info(self) -> DeviceInfo:
        """Return device information for the device registry."""
        status = self.coordinator.data.get("status", {})

        # Get device information from coordinator data
        device_name = status.get("DeviceName") or status.get("device_name") or "WiiM Device"
        device_model = status.get("project") or status.get("hardware") or "WiiM"
        device_id = status.get("uuid") or status.get("device_id")
        firmware_version = status.get("firmware")
        mac_address = status.get("MAC") or status.get("mac_address")

        device_info: DeviceInfo = {
            "identifiers": {(DOMAIN, device_id or self.coordinator.client.host)},
            "name": device_name,
            "manufacturer": "WiiM",
            "model": device_model,
        }

        if firmware_version:
            device_info["sw_version"] = firmware_version

        if mac_address:
            device_info["connections"] = {("mac", mac_address)}

        return device_info

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the device."""
        status = self._effective_status() or {}
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
            _LOGGER.debug(
                "[WiiM] Slave %s: group_master=%s, multiroom=%s, my_ip=%s, my_uuid=%s",
                self.coordinator.client.host,
                master_id,
                multiroom,
                my_ip,
                my_uuid,
            )
            # If group_master is set, try to match by IP or UUID
            if master_id:
                for coord in self.hass.data[DOMAIN].values():
                    if not hasattr(coord, "client"):
                        continue
                    host = coord.client.host
                    uuid = coord.data.get("status", {}).get("device_id")
                    _LOGGER.debug(
                        "[WiiM] Slave %s: checking coord host=%s, uuid=%s against master_id=%s",
                        self.coordinator.client.host,
                        host,
                        uuid,
                        master_id,
                    )
                    if host == master_id or uuid == master_id:
                        status = coord.data.get("status", {})
                        _LOGGER.debug(
                            "[WiiM] Slave %s: mirroring master's status by id: %s",
                            self.coordinator.client.host,
                            status,
                        )
                        return status
            # If group_master is None, search all coordinators for a master whose slave_list includes this device
            _LOGGER.debug(
                "[WiiM] Slave %s: searching for master by slave_list (my_ip=%s, my_uuid=%s)",
                self.coordinator.client.host,
                my_ip,
                my_uuid,
            )
            for coord in self.hass.data[DOMAIN].values():
                if not hasattr(coord, "client"):
                    continue
                # Check if this coordinator is a master
                if not coord.data or coord.data.get("role") != "master":
                    continue
                # Check master's multiroom info for this slave
                master_multiroom = coord.data.get("multiroom", {})
                slave_list = master_multiroom.get("slave_list", [])
                _LOGGER.debug(
                    "[WiiM] Slave %s: checking master %s slave_list=%s",
                    self.coordinator.client.host,
                    coord.client.host,
                    slave_list,
                )
                for slave in slave_list:
                    if isinstance(slave, dict):
                        slave_ip = slave.get("ip")
                        slave_uuid = slave.get("uuid")
                        _LOGGER.debug(
                            "[WiiM] Slave %s: comparing to slave_ip=%s, slave_uuid=%s",
                            self.coordinator.client.host,
                            slave_ip,
                            slave_uuid,
                        )
                        if (my_ip and my_ip == slave_ip) or (my_uuid and my_uuid == slave_uuid):
                            _LOGGER.debug(
                                "[WiiM] Slave %s: found master %s by slave_list",
                                self.coordinator.client.host,
                                coord.client.host,
                            )
                            return coord.data.get("status", {})
            # Could not locate the master in current coordinators – try to
            # automatically start a config-flow for it if we know its IP.
            _LOGGER.debug(
                "[WiiM] Slave %s: could not find master to mirror (master not yet set up)",
                self.coordinator.client.host,
            )

            # If the device advertised the master IP/UUID, attempt an import.
            potential_master = master_id or multiroom.get("master_ip") or multiroom.get("master")
            if potential_master and isinstance(potential_master, str) and "." in potential_master:
                master_ip = potential_master
                # Check if we already have a coordinator for that IP
                if not any(
                    hasattr(c, "client") and c.client.host == master_ip for c in self.hass.data.get(DOMAIN, {}).values()
                ):
                    _LOGGER.debug(
                        "[WiiM] Slave %s: launching import flow for unknown master %s",
                        self.coordinator.client.host,
                        master_ip,
                    )
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
        _LOGGER.debug(
            "[WiiM] %s: media_position_updated_at=%s",
            self.coordinator.client.host,
            updated,
        )
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
        role = self.coordinator.data.get("role", "solo") if self.coordinator.data else "solo"

        if role == "slave":
            # For slaves, show actual sources plus current master as an option
            sources = self.coordinator.data.get("status", {}).get("sources", [])
            mapped_sources = [SOURCE_MAP.get(src, src.title()) for src in sources]

            # Add master device as the first "source" option
            master_coord = self._find_master_coordinator()
            if master_coord and master_coord.data:
                master_status = master_coord.data.get("status", {})
                master_name = (
                    master_status.get("DeviceName") or master_status.get("device_name") or master_coord.client.host
                )
                # Put master first, then separator, then actual sources
                return [f"🔗 {master_name} (Group)"] + mapped_sources
            else:
                return mapped_sources
        else:
            # For solo/master devices, show normal sources
            sources = self.coordinator.data.get("status", {}).get("sources", [])
            _LOGGER.debug("[WiiM] %s source_list raw sources: %s", self.entity_id, sources)
            mapped_sources = [SOURCE_MAP.get(src, src.title()) for src in sources]
            _LOGGER.debug(
                "[WiiM] %s source_list mapped sources: %s",
                self.entity_id,
                mapped_sources,
            )
            return mapped_sources

    @property
    def source(self) -> str | None:
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
            # Remove entity_picture from attributes since we have the property
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
            # Enhanced device information
            "device_model": status.get("project") or status.get("hardware") or "WiiM Device",
            "mac_address": status.get("MAC"),
            "wifi_signal": f"{status.get('wifi_rssi', 'Unknown')} dBm" if status.get("wifi_rssi") else None,
            "wifi_channel": status.get("wifi_channel"),
            "uptime": status.get("uptime"),
            # Connection and status info
            "connection_type": "HTTPS" if "https" in self.coordinator.client._endpoint else "HTTP",
            "api_endpoint": self.coordinator.client._endpoint,
            "last_update_success": self.coordinator.last_update_success,
        }

        # Enhanced group information display
        role = self.coordinator.data.get("role", "solo")
        attrs["wiim_role"] = role

        if role == "master":
            # Show detailed slave information for masters
            multiroom = self.coordinator.data.get("multiroom", {})
            slave_list = multiroom.get("slave_list", [])
            slave_details = []
            total_group_volume = 0
            group_member_count = 1  # Include master

            # Add master volume to total
            master_volume = status.get("volume", 0)
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
                        "channel": slave.get("channel", 0),  # 0=stereo, 1=left, 2=right
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
                master_status = master_coord.data.get("status", {})
                master_name = (
                    master_status.get("DeviceName") or master_status.get("device_name") or master_coord.client.host
                )
                attrs["wiim_group_master"] = master_coord.client.host
                attrs["wiim_master_name"] = master_name
                attrs["group_status"] = f"Grouped with {master_name}"

                # Show if this slave can control group playback
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
            _LOGGER.debug(
                "[WiiM] %s: Searching for master via slave_list (my_ip=%s, my_uuid=%s)",
                self.entity_id,
                my_ip,
                my_uuid,
            )
            for coord in self.hass.data[DOMAIN].values():
                if not hasattr(coord, "client") or coord.data is None:
                    continue
                if coord.data.get("role") != "master":
                    continue
                multiroom = coord.data.get("multiroom", {})
                slave_list = multiroom.get("slave_list", [])
                _LOGGER.debug(
                    "[WiiM] %s: Evaluating potential master %s with slave_list=%s",
                    self.entity_id,
                    coord.client.host,
                    slave_list,
                )
                for slave in slave_list:
                    if isinstance(slave, dict):
                        if (my_ip and my_ip == slave.get("ip")) or (my_uuid and my_uuid == slave.get("uuid")):
                            _LOGGER.debug(
                                "[WiiM] %s: Matched master %s via slave_list",
                                self.entity_id,
                                coord.client.host,
                            )
                            return coord
            _LOGGER.debug("[WiiM] %s: No master coordinator found via slave_list", self.entity_id)
            return None
        _LOGGER.debug("[WiiM] %s: Master_ip present, searching coordinators", self.entity_id)
        for coord in self.hass.data[DOMAIN].values():
            if not hasattr(coord, "client"):
                continue
            if coord.client.host == master_ip:
                _LOGGER.debug(
                    "[WiiM] %s: Found master coordinator object for %s",
                    self.entity_id,
                    master_ip,
                )
                return coord
        _LOGGER.debug(
            "[WiiM] %s: No coordinator object found for master_ip=%s",
            self.entity_id,
            master_ip,
        )
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
                    except Exception as err:
                        _LOGGER.debug("[WiiM] Failed to trigger update for %s: %s", ip, err)
        elif role == "slave":
            # For slave, update master
            master_coord = self._find_master_coordinator()
            if master_coord:
                try:
                    await master_coord.async_request_refresh()
                except Exception as err:
                    _LOGGER.debug(
                        "[WiiM] Failed to trigger update for master %s: %s",
                        master_coord.client.host,
                        err,
                    )

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
        await self._trigger_group_updates()

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
        await self._trigger_group_updates()

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
        await self._trigger_group_updates()

    def _volume_step(self) -> float:
        entry_id = getattr(self.coordinator, "entry_id", None)
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

    async def async_select_source(self, source: str) -> None:
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
                    # User selected current group master - no action needed
                    _LOGGER.debug(
                        "[WiiM] %s: User selected current group master, no action",
                        self.entity_id,
                    )
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
                # Small delay to ensure group leave is processed
                await asyncio.sleep(0.5)
            except Exception as leave_err:
                _LOGGER.warning(
                    "[WiiM] %s: Failed to leave group before source change: %s",
                    self.entity_id,
                    leave_err,
                )
                # Continue anyway - device might already be solo

        # Convert user-friendly source back to API source
        src_api = next((k for k, v in SOURCE_MAP.items() if v == source), source.lower())

        # Handle special group source format by extracting just the source part
        if " (Group)" in source:
            # This shouldn't happen for slaves anymore, but handle it gracefully
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

    def _entity_id_to_host(self, entity_id: str) -> str | None:
        """Map HA entity_id to device IP address (host). Returns None if not found."""
        _LOGGER.debug(
            "[WiiM] %s: _entity_id_to_host() called with entity_id=%s",
            self.entity_id,
            entity_id,
        )

        # First try: Direct IP-based mapping (legacy scheme)
        for coord in self.hass.data[DOMAIN].values():
            if not hasattr(coord, "client"):
                continue
            expected = f"media_player.wiim_{coord.client.host.replace('.', '_')}"
            if expected == entity_id:
                _LOGGER.debug(
                    "[WiiM] _entity_id_to_host: Direct match found for host=%s",
                    coord.client.host,
                )
                return coord.client.host

        # Second try: Entity registry lookup
        try:
            from homeassistant.helpers import entity_registry as er

            ent_reg = er.async_get(self.hass)
            ent_entry = ent_reg.async_get(entity_id)

            if ent_entry and ent_entry.unique_id:
                unique = ent_entry.unique_id
                _LOGGER.debug(
                    "[WiiM] _entity_id_to_host: Registry lookup found unique_id=%s",
                    unique,
                )

                # Try to match by unique_id (which should be the host IP)
                for coord in self.hass.data[DOMAIN].values():
                    if hasattr(coord, "client") and coord.client.host == unique:
                        _LOGGER.debug(
                            "[WiiM] _entity_id_to_host: Match found via unique_id for host=%s",
                            coord.client.host,
                        )
                        return coord.client.host

                # Try to match by device name
                device_name = ent_entry.name or ent_entry.original_name
                if device_name:
                    for coord in self.hass.data[DOMAIN].values():
                        if not hasattr(coord, "client"):
                            continue
                        status = coord.data.get("status", {}) if coord.data else {}
                        device_name_from_status = status.get("DeviceName") or status.get("device_name")
                        if device_name_from_status and device_name_from_status.lower() == device_name.lower():
                            _LOGGER.debug(
                                "[WiiM] _entity_id_to_host: Match found via device name for host=%s",
                                coord.client.host,
                            )
                            return coord.client.host
        except Exception as reg_err:
            _LOGGER.debug("[WiiM] _entity_id_to_host: Entity registry lookup failed: %s", reg_err)

        # Third try: Look for any coordinator with matching entity_id in its data
        for coord in self.hass.data[DOMAIN].values():
            if not hasattr(coord, "client"):
                continue
            if hasattr(coord, "entity_id") and coord.entity_id == entity_id:
                _LOGGER.debug(
                    "[WiiM] _entity_id_to_host: Match found via coordinator entity_id for host=%s",
                    coord.client.host,
                )
                return coord.client.host

        # Fourth try: Use the improved _find_coordinator function and extract host from it
        coord = _find_coordinator(self.hass, entity_id)
        if coord and hasattr(coord, "client"):
            _LOGGER.debug(
                "[WiiM] _entity_id_to_host: Match found via _find_coordinator for host=%s",
                coord.client.host,
            )
            return coord.client.host

        _LOGGER.warning("[WiiM] _entity_id_to_host: No match found for entity_id=%s", entity_id)
        return None

    async def async_join(self, group_members: list[str]) -> None:
        """Join `group_members` as a group.

        This method is called by HA's native grouping UI (JOIN button) as well as
        our custom services. We translate HA's generic grouping to proper WiiM
        multiroom protocols while maintaining compatibility.
        """
        _LOGGER.info(
            "[WiiM] %s: HA native join called with group_members=%s",
            self.entity_id,
            group_members,
        )

        # Pre-validate and filter out stale entities
        validated_members = []
        for entity_id in group_members:
            if entity_id == self.entity_id:
                validated_members.append(entity_id)
                continue

            # Check if entity exists and is valid
            entity_state = self.hass.states.get(entity_id)
            if entity_state is None:
                _LOGGER.warning(
                    "[WiiM] %s: Skipping non-existent entity %s from group members",
                    self.entity_id,
                    entity_id,
                )
                continue

            # Check if entity is stale (unavailable/unknown/restored)
            if entity_state.state in ("unavailable", "unknown") or entity_state.attributes.get("restored", False):
                _LOGGER.warning(
                    "[WiiM] %s: Skipping stale entity %s (state: %s) from group members",
                    self.entity_id,
                    entity_id,
                    entity_state.state,
                )
                continue

            # Check if we can find a coordinator for this entity
            coord = _find_coordinator(self.hass, entity_id)
            if coord is None:
                _LOGGER.warning(
                    "[WiiM] %s: Skipping entity %s - no WiiM coordinator found (may be non-WiiM device or offline)",
                    self.entity_id,
                    entity_id,
                )
                continue

            validated_members.append(entity_id)

        if len(validated_members) != len(group_members):
            _LOGGER.info(
                "[WiiM] %s: Filtered group members from %d to %d valid entities: %s",
                self.entity_id,
                len(group_members),
                len(validated_members),
                validated_members,
            )

        # If no valid members except ourselves, just make sure we're solo
        if len(validated_members) <= 1:
            _LOGGER.info("[WiiM] %s: No valid group members found, ensuring device is solo", self.entity_id)
            if self.coordinator.client.is_slave or self.coordinator.client.is_master:
                await self.async_unjoin()
            return

        # Use WiiM-specific multiroom grouping (better than generic HA grouping)
        await self._create_wiim_multiroom_group(validated_members)

    async def _create_wiim_multiroom_group(self, group_members: list[str]) -> None:
        """Create a proper WiiM multiroom group with enhanced features."""
        try:
            # ------------------------------------------------------------------
            # 1) Ensure *this* device is ready to become/act as master
            # ------------------------------------------------------------------

            # If we are currently a slave but about to act as master, leave current group first
            if self.coordinator.client.is_slave:
                _LOGGER.info(
                    "[WiiM] %s: Currently a SLAVE, leaving existing group before creating new one",
                    self.entity_id,
                )
                try:
                    await self.coordinator.leave_wiim_group()
                except Exception as leave_err:
                    _LOGGER.warning(
                        "[WiiM] %s: Failed to leave existing group (may already be solo): %s",
                        self.entity_id,
                        leave_err,
                    )

            # Ensure there is a master group created (either existing or create new)
            if not self.coordinator.client.group_master:
                _LOGGER.info("[WiiM] %s: Creating new WiiM multiroom group as master", self.entity_id)
                await self.coordinator.create_wiim_group()
                master_ip = self.coordinator.client.host
                _LOGGER.info(
                    "[WiiM] %s: Successfully created WiiM group as master (%s)",
                    self.entity_id,
                    master_ip,
                )
            else:
                master_ip = self.coordinator.client.group_master
                _LOGGER.info(
                    "[WiiM] %s: Using existing WiiM group master %s",
                    self.entity_id,
                    master_ip,
                )

            for entity_id in group_members:
                if entity_id == self.entity_id:
                    _LOGGER.debug("[WiiM] %s: Skipping self in group members", self.entity_id)
                    continue

                # We already validated this entity has a coordinator in pre-validation
                coord = _find_coordinator(self.hass, entity_id)
                member_ip = self._entity_id_to_host(entity_id)

                if member_ip is None:
                    _LOGGER.warning(
                        "[WiiM] %s: Could not resolve host for entity %s – skipping",
                        self.entity_id,
                        entity_id,
                    )
                    continue

                _LOGGER.info(
                    "[WiiM] %s: Instructing %s to join WiiM multiroom master %s",
                    self.entity_id,
                    member_ip,
                    master_ip,
                )
                try:
                    await coord.join_wiim_group(master_ip)
                    _LOGGER.info(
                        "[WiiM] %s: Successfully joined %s to WiiM group",
                        self.entity_id,
                        member_ip,
                    )
                except Exception as join_err:
                    _LOGGER.error(
                        "[WiiM] %s: Failed to join %s to WiiM group: %s",
                        self.entity_id,
                        member_ip,
                        join_err,
                    )
                    # Don't raise - continue with other members
                    continue

            # ------------------------------------------------------------------
            # 2) Remove slaves that are currently in the group but not in the
            #    desired `group_members` list (automatic pruning)
            # ------------------------------------------------------------------
            desired_hosts = set()
            for eid in group_members:
                if eid != self.entity_id and _find_coordinator(self.hass, eid) is not None:
                    member_host = self._entity_id_to_host(eid)
                    if member_host is not None:
                        desired_hosts.add(member_host)

            current_slaves = set(self.coordinator.wiim_group_members)
            _LOGGER.debug(
                "[WiiM] %s: desired_hosts=%s, current_slaves=%s",
                self.entity_id,
                desired_hosts,
                current_slaves,
            )

            extraneous_slaves = current_slaves - desired_hosts
            for slave_ip in extraneous_slaves:
                _LOGGER.info(
                    "[WiiM] %s: Removing extraneous slave %s from WiiM group",
                    self.entity_id,
                    slave_ip,
                )
                slave_coord = next(
                    (c for c in self.hass.data[DOMAIN].values() if hasattr(c, "client") and c.client.host == slave_ip),
                    None,
                )
                if slave_coord is not None:
                    try:
                        await slave_coord.leave_wiim_group()
                    except Exception as kick_err:
                        _LOGGER.warning(
                            "[WiiM] %s: Failed to remove slave %s: %s",
                            self.entity_id,
                            slave_ip,
                            kick_err,
                        )

            _LOGGER.info(
                "[WiiM] %s: Triggering coordinator refresh after WiiM multiroom group creation",
                self.entity_id,
            )
            await self.coordinator.async_request_refresh()
            _LOGGER.info("[WiiM] %s: WiiM multiroom group creation completed successfully", self.entity_id)
        except Exception as err:
            _LOGGER.error("[WiiM] %s: Failed to complete WiiM multiroom group creation: %s", self.entity_id, err)
            raise

    async def async_unjoin(self) -> None:
        """Remove this player from any group.

        This method is called by HA's native grouping UI as well as our custom services.
        We use proper WiiM multiroom protocols for ungrouping.
        """
        _LOGGER.info("[WiiM] %s: HA native unjoin called", self.entity_id)
        try:
            if self.coordinator.client.is_master:
                _LOGGER.info("[WiiM] %s: Disbanding WiiM multiroom group as master", self.entity_id)
                await self.coordinator.delete_wiim_group()
                _LOGGER.info("[WiiM] %s: Successfully disbanded WiiM group", self.entity_id)
            else:
                _LOGGER.info("[WiiM] %s: Leaving WiiM multiroom group as member", self.entity_id)
                await self.coordinator.leave_wiim_group()
                _LOGGER.info("[WiiM] %s: Successfully left WiiM group", self.entity_id)

            _LOGGER.info(
                "[WiiM] %s: Triggering coordinator refresh after WiiM unjoin operation",
                self.entity_id,
            )
            await self.coordinator.async_request_refresh()
            _LOGGER.info("[WiiM] %s: WiiM unjoin operation completed successfully", self.entity_id)
        except Exception as err:
            _LOGGER.error(
                "[WiiM] %s: Failed to complete WiiM unjoin operation: %s",
                self.entity_id,
                err,
            )
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

    async def async_diagnose_entities(self) -> None:
        """Diagnose WiiM entities and coordinators for troubleshooting."""
        _LOGGER.info("[WiiM] %s: Starting entity diagnostics", self.entity_id)

        # Get all WiiM entities from entity registry
        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(self.hass)

        wiim_entities = []
        stale_entities = []
        active_coordinators = []

        # Collect all WiiM entities
        for entry in ent_reg.entities.values():
            if entry.domain == "media_player" and entry.platform == DOMAIN:
                wiim_entities.append(
                    {
                        "entity_id": entry.entity_id,
                        "unique_id": entry.unique_id,
                        "name": entry.name or entry.original_name,
                        "disabled": entry.disabled_by is not None,
                    }
                )

        # Collect active coordinators
        for coord in self.hass.data[DOMAIN].values():
            if hasattr(coord, "client"):
                active_coordinators.append(
                    {
                        "host": coord.client.host,
                        "has_data": coord.data is not None,
                        "device_name": coord.data.get("status", {}).get("DeviceName") if coord.data else None,
                        "role": coord.data.get("role") if coord.data else None,
                    }
                )

        # Find stale entities (entities without corresponding coordinators)
        coordinator_hosts = {coord["host"] for coord in active_coordinators}

        for entity in wiim_entities:
            if entity["unique_id"] not in coordinator_hosts:
                # Check if entity still exists in HA state
                entity_state = self.hass.states.get(entity["entity_id"])
                stale_entities.append(
                    {
                        **entity,
                        "state_exists": entity_state is not None,
                        "state": entity_state.state if entity_state else None,
                    }
                )

        # Log comprehensive diagnostics
        _LOGGER.info(
            "[WiiM] %s: Diagnostics Results:\n"
            "  Total WiiM Entities: %d\n"
            "  Active Coordinators: %d\n"
            "  Potentially Stale Entities: %d\n"
            "\nActive Coordinators:\n%s\n"
            "\nAll WiiM Entities:\n%s\n"
            "\nPotentially Stale Entities:\n%s",
            self.entity_id,
            len(wiim_entities),
            len(active_coordinators),
            len(stale_entities),
            "\n".join(
                f"  - {coord['host']}: {coord['device_name']} ({coord['role']})" for coord in active_coordinators
            ),
            "\n".join(
                f"  - {entity['entity_id']}: {entity['name']} (unique_id: {entity['unique_id']}, disabled: {entity['disabled']})"
                for entity in wiim_entities
            ),
            (
                "\n".join(
                    f"  - {entity['entity_id']}: {entity['name']} (state_exists: {entity['state_exists']}, state: {entity['state']})"
                    for entity in stale_entities
                )
                if stale_entities
                else "  None"
            ),
        )

        if stale_entities:
            _LOGGER.warning(
                "[WiiM] %s: Found %d potentially stale entities. "
                "These entities exist in the registry but have no active coordinator. "
                "This usually happens when devices are removed or renamed. "
                "Consider removing these entities from Home Assistant if they're no longer needed.",
                self.entity_id,
                len(stale_entities),
            )
        else:
            _LOGGER.info("[WiiM] %s: All WiiM entities appear to be healthy!", self.entity_id)

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

    async def async_play_notification(self, url: str) -> None:
        await self.coordinator.client.play_notification(url)
        await self.coordinator.async_refresh()

    # ------------------------------------------------------------------
    # Group Management Services
    # ------------------------------------------------------------------

    async def async_create_group_with_members(self, group_members: list[str]) -> None:
        """Create a new group with specified members (this device as master)."""
        _LOGGER.info("[WiiM] %s: Creating group with members: %s", self.entity_id, group_members)

        # Ensure we include ourselves as the master
        all_members = [self.entity_id] + [m for m in group_members if m != self.entity_id]
        await self.async_join(all_members)

    async def async_add_to_group(self, target_entity: str) -> None:
        """Add another device to this device's group."""
        _LOGGER.info("[WiiM] %s: Adding %s to group", self.entity_id, target_entity)

        # Get current group members and add the new one
        current_members = list(self.group_members) or [self.entity_id]
        if target_entity not in current_members:
            current_members.append(target_entity)

        await self.async_join(current_members)

    async def async_remove_from_group(self, target_entity: str) -> None:
        """Remove a device from this device's group."""
        _LOGGER.info("[WiiM] %s: Removing %s from group", self.entity_id, target_entity)

        # Find the target coordinator and make it leave
        target_coord = _find_coordinator(self.hass, target_entity)
        if target_coord:
            await target_coord.leave_wiim_group()
            await self.coordinator.async_request_refresh()
            await target_coord.async_request_refresh()
        else:
            _LOGGER.warning(
                "[WiiM] %s: Could not find coordinator for %s",
                self.entity_id,
                target_entity,
            )

    async def async_disband_group(self) -> None:
        """Disband the entire group."""
        _LOGGER.info("[WiiM] %s: Disbanding group", self.entity_id)

        if self.coordinator.client.is_master:
            await self.coordinator.delete_wiim_group()
        else:
            # If not master, just leave the group
            await self.coordinator.leave_wiim_group()

        await self.coordinator.async_request_refresh()

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
                        _LOGGER.debug(
                            "[WiiM] %s: Artwork fetch failed – HTTP %s",
                            self.entity_id,
                            resp.status,
                        )
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

    async def async_cleanup_stale_entities(self, dry_run: bool = True) -> None:
        """Clean up stale WiiM entities (with optional dry-run mode)."""
        _LOGGER.info("[WiiM] %s: Starting stale entity cleanup (dry_run=%s)", self.entity_id, dry_run)

        # Get all WiiM entities from entity registry
        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(self.hass)

        wiim_entities = []
        stale_entities = []
        active_coordinators = []

        # Collect all WiiM entities
        for entry in ent_reg.entities.values():
            if entry.domain == "media_player" and entry.platform == DOMAIN:
                wiim_entities.append(entry)

        # Collect active coordinators
        coordinator_hosts = set()
        for coord in self.hass.data[DOMAIN].values():
            if hasattr(coord, "client"):
                coordinator_hosts.add(coord.client.host)
                active_coordinators.append(coord)

        # Find stale entities
        for entity in wiim_entities:
            if entity.unique_id not in coordinator_hosts:
                # Additional check: see if entity state exists and is unavailable
                entity_state = self.hass.states.get(entity.entity_id)
                is_stale = (
                    entity_state is None
                    or entity_state.state in ("unavailable", "unknown")
                    or entity_state.attributes.get("restored", False)
                )

                if is_stale:
                    stale_entities.append(entity)

        if not stale_entities:
            _LOGGER.info("[WiiM] %s: No stale entities found!", self.entity_id)
            return

        _LOGGER.info(
            "[WiiM] %s: Found %d stale entities to %s",
            self.entity_id,
            len(stale_entities),
            "remove" if not dry_run else "potentially remove",
        )

        removed_count = 0
        for entity in stale_entities:
            entity_name = entity.name or entity.original_name or entity.entity_id

            if dry_run:
                _LOGGER.info(
                    "[WiiM] %s: [DRY RUN] Would remove stale entity: %s (%s)",
                    self.entity_id,
                    entity.entity_id,
                    entity_name,
                )
            else:
                try:
                    # Remove the entity from registry
                    ent_reg.async_remove(entity.entity_id)
                    removed_count += 1
                    _LOGGER.info(
                        "[WiiM] %s: Removed stale entity: %s (%s)",
                        self.entity_id,
                        entity.entity_id,
                        entity_name,
                    )
                except Exception as remove_err:
                    _LOGGER.error(
                        "[WiiM] %s: Failed to remove stale entity %s: %s",
                        self.entity_id,
                        entity.entity_id,
                        remove_err,
                    )

        if dry_run:
            _LOGGER.info(
                "[WiiM] %s: [DRY RUN] Would remove %d stale entities. "
                "To actually remove them, call this service with dry_run: false",
                self.entity_id,
                len(stale_entities),
            )
        else:
            _LOGGER.info(
                "[WiiM] %s: Successfully removed %d/%d stale entities",
                self.entity_id,
                removed_count,
                len(stale_entities),
            )

    async def async_auto_maintain(self, auto_cleanup: bool = False, dry_run: bool = True) -> None:
        """Run comprehensive maintenance: diagnostics + optional cleanup."""
        _LOGGER.info(
            "[WiiM] %s: Starting auto maintenance (auto_cleanup=%s, dry_run=%s)",
            self.entity_id,
            auto_cleanup,
            dry_run,
        )

        # First run diagnostics
        await self.async_diagnose_entities()

        # If auto_cleanup is enabled, run cleanup
        if auto_cleanup:
            _LOGGER.info("[WiiM] %s: Running automatic cleanup as requested", self.entity_id)
            await self.async_cleanup_stale_entities(dry_run=dry_run)
        else:
            _LOGGER.info(
                "[WiiM] %s: Auto cleanup disabled. To enable cleanup, set auto_cleanup=true",
                self.entity_id,
            )

    async def async_nuclear_reset_entities(self, i_understand_this_removes_all_wiim_entities: bool = False) -> None:
        """Nuclear option: Remove ALL WiiM entities from Home Assistant.

        Use this when entity naming gets completely corrupted with _2, _3, etc.
        """
        if not i_understand_this_removes_all_wiim_entities:
            _LOGGER.error(
                "[WiiM] %s: Nuclear reset cancelled - confirmation required",
                self.entity_id,
            )
            raise ValueError(
                "You must set 'i_understand_this_removes_all_wiim_entities: true' to confirm this destructive operation"
            )

        _LOGGER.warning(
            "[WiiM] %s: NUCLEAR RESET - Removing ALL WiiM entities from Home Assistant",
            self.entity_id,
        )

        try:
            from homeassistant.helpers import entity_registry as er

            ent_reg = er.async_get(self.hass)

            # Find ALL WiiM entities
            wiim_entities = []
            for entry in ent_reg.entities.values():
                if (entry.domain == "media_player" and entry.platform == DOMAIN) or (
                    entry.platform == DOMAIN
                ):  # Catch any WiiM entities
                    wiim_entities.append(entry)

            _LOGGER.warning(
                "[WiiM] %s: Found %d WiiM entities to remove",
                self.entity_id,
                len(wiim_entities),
            )

            # Remove all WiiM entities
            removed_count = 0
            for entity in wiim_entities:
                try:
                    _LOGGER.warning(
                        "[WiiM] %s: REMOVING entity %s (%s)",
                        self.entity_id,
                        entity.entity_id,
                        entity.name or entity.original_name,
                    )
                    ent_reg.async_remove(entity.entity_id)
                    removed_count += 1
                except Exception as remove_err:
                    _LOGGER.error(
                        "[WiiM] %s: Failed to remove entity %s: %s",
                        self.entity_id,
                        entity.entity_id,
                        remove_err,
                    )

            _LOGGER.warning(
                "[WiiM] %s: NUCLEAR RESET COMPLETE - Removed %d/%d entities. "
                "RESTART HOME ASSISTANT and re-add WiiM integration for clean setup.",
                self.entity_id,
                removed_count,
                len(wiim_entities),
            )

        except Exception as nuclear_err:
            _LOGGER.error(
                "[WiiM] %s: Nuclear reset failed: %s",
                self.entity_id,
                nuclear_err,
            )
            raise


def _find_coordinator(hass: HomeAssistant, entity_id: str) -> WiiMCoordinator | None:
    """Return coordinator for the given entity ID."""
    _LOGGER.debug("[WiiM] _find_coordinator: Looking up coordinator for entity_id=%s", entity_id)

    # First try: Direct entity ID to host mapping (standard WiiM naming pattern)
    for coord in hass.data[DOMAIN].values():
        if not hasattr(coord, "client"):
            continue
        expected = f"media_player.wiim_{coord.client.host.replace('.', '_')}"
        if expected == entity_id:
            _LOGGER.debug(
                "[WiiM] _find_coordinator: Direct match found for host=%s",
                coord.client.host,
            )
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
                    _LOGGER.debug(
                        "[WiiM] _find_coordinator: Match found via unique_id for host=%s",
                        coord.client.host,
                    )
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
                        _LOGGER.debug(
                            "[WiiM] _find_coordinator: Match found via device name for host=%s",
                            coord.client.host,
                        )
                        return coord
    except Exception as reg_err:
        _LOGGER.debug("[WiiM] _find_coordinator: Entity registry lookup failed: %s", reg_err)

    # Third try: Look for any coordinator with matching entity_id in its data
    for coord in hass.data[DOMAIN].values():
        if not hasattr(coord, "client"):
            continue
        if hasattr(coord, "entity_id") and coord.entity_id == entity_id:
            _LOGGER.debug(
                "[WiiM] _find_coordinator: Match found via coordinator entity_id for host=%s",
                coord.client.host,
            )
            return coord

    # Fourth try: Fuzzy matching for entities that might have different naming patterns
    # Extract the device name part from entity_id (e.g., "master_bedroom" from "media_player.master_bedroom_2")
    entity_name_part = entity_id.replace("media_player.", "").replace("_", " ").lower()
    # Remove common suffixes like "_2", "_3" etc. that might indicate duplicates
    import re

    entity_name_part = re.sub(r"_\d+$", "", entity_name_part.replace(" ", "_")).replace("_", " ")

    if entity_name_part:
        _LOGGER.debug("[WiiM] _find_coordinator: Trying fuzzy match with name part: %s", entity_name_part)
        for coord in hass.data[DOMAIN].values():
            if not hasattr(coord, "client") or not coord.data:
                continue
            status = coord.data.get("status", {})
            device_name_from_status = status.get("DeviceName") or status.get("device_name") or ""

            # Try exact match first
            if device_name_from_status.lower().replace(" ", "_") == entity_name_part.replace(" ", "_"):
                _LOGGER.debug(
                    "[WiiM] _find_coordinator: Fuzzy exact match found for device '%s' -> host=%s",
                    device_name_from_status,
                    coord.client.host,
                )
                return coord

            # Try partial match if device name contains the entity name part
            if entity_name_part in device_name_from_status.lower().replace(" ", "_"):
                _LOGGER.debug(
                    "[WiiM] _find_coordinator: Fuzzy partial match found for device '%s' -> host=%s",
                    device_name_from_status,
                    coord.client.host,
                )
                return coord

    # Fifth try: Check all entities in Home Assistant entity registry for WiiM domain
    try:
        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)

        # Get all WiiM entities and see if any of them map to our entity_id
        for entry in ent_reg.entities.values():
            if entry.domain == "media_player" and entry.platform == DOMAIN:
                # If the entry's entity_id matches and it has a unique_id, try to find the coordinator
                if entry.entity_id == entity_id and entry.unique_id:
                    for coord in hass.data[DOMAIN].values():
                        if hasattr(coord, "client") and coord.client.host == entry.unique_id:
                            _LOGGER.debug(
                                "[WiiM] _find_coordinator: Found via registry scan for host=%s",
                                coord.client.host,
                            )
                            return coord
    except Exception as scan_err:
        _LOGGER.debug("[WiiM] _find_coordinator: Registry scan failed: %s", scan_err)

    _LOGGER.warning("[WiiM] _find_coordinator: No coordinator found for entity_id=%s", entity_id)
    _LOGGER.debug(
        "[WiiM] _find_coordinator: Available coordinators: %s",
        [f"{coord.client.host if hasattr(coord, 'client') else 'no_client'}" for coord in hass.data[DOMAIN].values()],
    )
    return None
