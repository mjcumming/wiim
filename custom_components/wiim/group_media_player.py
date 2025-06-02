import logging

from homeassistant.components.media_player import MediaPlayerEntity, MediaPlayerEntityFeature, MediaPlayerState
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .utils.device_registry import find_coordinator_by_ip

_LOGGER = logging.getLogger(__name__)


class WiiMGroupMediaPlayer(MediaPlayerEntity):
    """Representation of a WiiM group media player entity.

    This class implements a virtual media player entity that represents a group of WiiM devices
    working together in a multiroom setup. It provides unified control over the group while
    maintaining individual device control capabilities.

    Key Features:
    - Unified group control (playback, volume, mute)
    - Individual device control within the group
    - Automatic group state synchronization
    - Real-time status updates
    - Group membership management

    State Management:
    - Aggregates state from all group members
    - Maintains group volume and mute state
    - Tracks media playback information
    - Monitors group membership changes

    Volume Control:
    - Implements relative volume changes across group
    - Maintains volume relationships between devices
    - Supports individual device volume control
    - Handles volume synchronization

    Error Handling:
    - Graceful handling of device disconnections
    - Automatic group state recovery
    - Detailed error logging
    - Maintains group consistency during errors
    """

    def __init__(self, hass, coordinator, device_ip):
        self.hass = hass
        self.coordinator = coordinator
        self.device_ip = device_ip  # This device's IP (not necessarily master)

        # Get device name for this specific device
        status = coordinator.data.get("status", {}) if coordinator.data else {}
        device_name = status.get("DeviceName") or status.get("device_name") or device_ip

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
        self._attr_unique_id = f"wiim_master_{device_ip.replace('.', '_')}_{safe_name}"
        self._attr_name = f"{device_name} Master"
        self._attr_supported_features = (
            MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
        )

        # Set device_info to match the main device so the group entity is grouped under the main device
        # Use the MAC address as the primary identifier to match the main media player
        device_mac = status.get("MAC")
        device_identifiers = set()
        if device_mac:
            # Use MAC as primary identifier (same as main media player)
            device_identifiers.add((DOMAIN, device_mac.lower().replace(":", "")))
        # Always include IP as fallback identifier
        device_identifiers.add((DOMAIN, coordinator.client.host))

        self._attr_device_info = DeviceInfo(
            identifiers=device_identifiers,
            name=device_name,
            manufacturer="WiiM",
            model=status.get("project") or status.get("hardware"),
            sw_version=status.get("firmware"),
            connections={("mac", device_mac)} if device_mac else set(),
        )

    @property
    def group_info(self):
        info = self.coordinator.get_group_by_master(self.device_ip) or {}
        _LOGGER.debug("[WiiMGroup] Group info for master %s: %s", self.device_ip, info)
        return info

    @property
    def group_members(self):
        return list(self.group_info.get("members", {}).keys())

    @property
    def group_leader(self):
        return self.device_ip

    @property
    def state(self):
        """Return state based on this device's role."""
        if self.coordinator.data is None:
            return MediaPlayerState.IDLE

        role = self.coordinator.data.get("role", "solo")

        if role == "solo":
            # Solo device - show its own state
            status = self.coordinator.data.get("status", {})
            if not status.get("power"):
                return MediaPlayerState.OFF
            if status.get("play_status") == "play":
                return MediaPlayerState.PLAYING
            if status.get("play_status") == "pause":
                return MediaPlayerState.PAUSED
            return MediaPlayerState.IDLE

        elif role == "master":
            # Master device - show its own state (controls group)
            status = self.coordinator.data.get("status", {})
            if not status.get("power"):
                return MediaPlayerState.OFF
            if status.get("play_status") == "play":
                return MediaPlayerState.PLAYING
            if status.get("play_status") == "pause":
                return MediaPlayerState.PAUSED
            return MediaPlayerState.IDLE

        else:  # slave
            # Slave device - mirror master's state
            master_coord = self._find_master_coordinator()
            if not master_coord or master_coord.data is None:
                return MediaPlayerState.IDLE

            master_status = master_coord.data.get("status", {})
            if not master_status.get("power"):
                return MediaPlayerState.OFF
            if master_status.get("play_status") == "play":
                return MediaPlayerState.PLAYING
            if master_status.get("play_status") == "pause":
                return MediaPlayerState.PAUSED
            return MediaPlayerState.IDLE

    @property
    def volume_level(self):
        """Return volume level based on role."""
        role = self.coordinator.data.get("role", "solo") if self.coordinator.data else "solo"

        if role == "solo":
            # Solo: return own volume
            status = self.coordinator.data.get("status", {})
            volume = status.get("volume")
            return float(volume) / 100 if volume is not None else None

        elif role == "master":
            # Master: return group max volume (existing behavior)
            max_vol = 0
            for ip in self.group_members:
                coord = self._find_coordinator_by_ip(ip)
                if coord and coord.data and "status" in coord.data:
                    vol = coord.data["status"].get("volume", 0)
                    if vol > max_vol:
                        max_vol = vol
            return float(max_vol) / 100

        else:  # slave
            # Slave: return own volume only
            status = self.coordinator.data.get("status", {})
            volume = status.get("volume")
            return float(volume) / 100 if volume is not None else None

    @property
    def is_volume_muted(self):
        """Return mute state based on role."""
        role = self.coordinator.data.get("role", "solo") if self.coordinator.data else "solo"

        if role == "solo":
            # Solo: return own mute state
            return self.coordinator.data.get("status", {}).get("mute")

        elif role == "master":
            # Master: return aggregate group mute state (existing behavior)
            any_unmuted = False
            any_known = False
            for ip in self.group_members:
                coord = self._find_coordinator_by_ip(ip)
                if not coord or not coord.data or "status" not in coord.data:
                    continue
                any_known = True
                if not coord.data["status"].get("mute", False):
                    any_unmuted = True
                    break
            if not any_known:
                return None  # Unknown
            return not any_unmuted

        else:  # slave
            # Slave: return own mute state only
            return self.coordinator.data.get("status", {}).get("mute")

    @property
    def extra_state_attributes(self):
        """Show group status and members based on current role."""
        if self.coordinator.data is None:
            return {}

        role = self.coordinator.data.get("role", "solo")
        attrs = {"wiim_role": role}

        if role == "solo":
            attrs["group_status"] = "Not grouped"
            # Show available devices for potential grouping
            available_devices = []
            for coord in self.hass.data[DOMAIN].values():
                if not hasattr(coord, "client") or coord.client.host == self.device_ip:
                    continue
                device_status = coord.data.get("status", {}) if coord.data else {}
                device_name = device_status.get("DeviceName") or device_status.get("device_name") or coord.client.host
                available_devices.append(
                    {
                        "name": device_name,
                        "ip": coord.client.host,
                        "entity_id": f"media_player.wiim_{coord.client.host.replace('.', '_')}",
                    }
                )
            attrs["available_devices"] = available_devices

        elif role == "master":
            # Show slave information for masters
            multiroom = self.coordinator.data.get("multiroom", {})
            slave_list = multiroom.get("slave_list", [])

            if slave_list:
                slave_names = [slave.get("name", "Unknown") for slave in slave_list if isinstance(slave, dict)]
                attrs["group_status"] = f"Master of: {', '.join(slave_names)} ({len(slave_list)} slaves)"

                # Detailed slave info
                slave_details = []
                for slave in slave_list:
                    if isinstance(slave, dict):
                        slave_info = {
                            "name": slave.get("name", "Unknown"),
                            "ip": slave.get("ip"),
                            "volume": slave.get("volume", 0),
                            "muted": bool(slave.get("mute", False)),
                        }
                        slave_details.append(slave_info)
                attrs["slaves"] = slave_details
            else:
                attrs["group_status"] = "Master (no slaves)"

        else:  # slave
            master_ip = self.coordinator.client.group_master
            if master_ip:
                # Try to find master name
                master_coord = self._find_master_coordinator()
                if master_coord and master_coord.data:
                    master_status = master_coord.data.get("status", {})
                    master_name = master_status.get("DeviceName") or master_status.get("device_name") or master_ip
                    attrs["group_status"] = f"Slave of: {master_name}"
                    attrs["master_name"] = master_name
                else:
                    attrs["group_status"] = f"Slave of: {master_ip}"
                attrs["master_ip"] = master_ip
            else:
                attrs["group_status"] = "Slave (unknown master)"

        return attrs

    @property
    def supported_features(self):
        return self._attr_supported_features

    @property
    def entity_picture(self):
        """Return artwork based on role."""
        role = self.coordinator.data.get("role", "solo") if self.coordinator.data else "solo"

        if role == "slave":
            # Slave: show master's artwork
            master_coord = self._find_master_coordinator()
            if master_coord and master_coord.data:
                return master_coord.data.get("status", {}).get("entity_picture")

        # Solo or Master: show own artwork
        return self.coordinator.data.get("status", {}).get("entity_picture") if self.coordinator.data else None

    @property
    def media_title(self):
        """Return track title based on role."""
        role = self.coordinator.data.get("role", "solo") if self.coordinator.data else "solo"

        if role == "slave":
            # Slave: show master's title
            master_coord = self._find_master_coordinator()
            if master_coord and master_coord.data:
                return master_coord.data.get("status", {}).get("title")

        # Solo or Master: show own title
        return self.coordinator.data.get("status", {}).get("title") if self.coordinator.data else None

    @property
    def media_artist(self):
        """Return artist based on role."""
        role = self.coordinator.data.get("role", "solo") if self.coordinator.data else "solo"

        if role == "slave":
            # Slave: show master's artist
            master_coord = self._find_master_coordinator()
            if master_coord and master_coord.data:
                return master_coord.data.get("status", {}).get("artist")

        # Solo or Master: show own artist
        return self.coordinator.data.get("status", {}).get("artist") if self.coordinator.data else None

    @property
    def media_album_name(self):
        """Return album based on role."""
        role = self.coordinator.data.get("role", "solo") if self.coordinator.data else "solo"

        if role == "slave":
            # Slave: show master's album
            master_coord = self._find_master_coordinator()
            if master_coord and master_coord.data:
                return master_coord.data.get("status", {}).get("album")

        # Solo or Master: show own album
        return self.coordinator.data.get("status", {}).get("album") if self.coordinator.data else None

    @property
    def media_position(self):
        """Return playback position based on role."""
        role = self.coordinator.data.get("role", "solo") if self.coordinator.data else "solo"

        if role == "slave":
            # Slave: show master's position
            master_coord = self._find_master_coordinator()
            if master_coord and master_coord.data:
                return master_coord.data.get("status", {}).get("position")

        # Solo or Master: show own position
        return self.coordinator.data.get("status", {}).get("position") if self.coordinator.data else None

    @property
    def media_duration(self):
        """Return track duration based on role."""
        role = self.coordinator.data.get("role", "solo") if self.coordinator.data else "solo"

        if role == "slave":
            # Slave: show master's duration
            master_coord = self._find_master_coordinator()
            if master_coord and master_coord.data:
                return master_coord.data.get("status", {}).get("duration")

        # Solo or Master: show own duration
        return self.coordinator.data.get("status", {}).get("duration") if self.coordinator.data else None

    @property
    def media_position_updated_at(self):
        """Return position update time based on role."""
        role = self.coordinator.data.get("role", "solo") if self.coordinator.data else "solo"

        if role == "slave":
            # Slave: show master's position update time
            master_coord = self._find_master_coordinator()
            if master_coord and master_coord.data:
                return master_coord.data.get("status", {}).get("position_updated_at")

        # Solo or Master: show own position update time
        return self.coordinator.data.get("status", {}).get("position_updated_at") if self.coordinator.data else None

    async def async_set_volume_level(self, volume):
        """Set volume based on role."""
        role = self.coordinator.data.get("role", "solo") if self.coordinator.data else "solo"

        if role == "solo":
            # Solo: set own volume
            await self.coordinator.client.set_volume(volume)
            await self.coordinator.async_refresh()

        elif role == "master":
            # Master: set group volume with relative changes (existing behavior)
            member_vols = {}
            for ip in self.group_members:
                coord = self._find_coordinator_by_ip(ip)
                if coord and coord.data and "status" in coord.data:
                    member_vols[ip] = coord.data["status"].get("volume", 0)
                else:
                    member_vols[ip] = 0
            if not member_vols:
                return
            current_max = max(member_vols.values())
            new_max = int(volume * 100)
            delta = new_max - current_max
            for ip, cur in member_vols.items():
                new_vol = max(0, min(100, cur + delta))
                coord = self._find_coordinator_by_ip(ip)
                if coord:
                    await coord.client.set_volume(new_vol / 100)

        else:  # slave
            # Slave: set only own volume
            await self.coordinator.client.set_volume(volume)
            await self.coordinator.async_refresh()

    async def async_mute_volume(self, mute: bool):
        """Mute/unmute based on role."""
        role = self.coordinator.data.get("role", "solo") if self.coordinator.data else "solo"

        if role == "solo":
            # Solo: mute/unmute self
            await self.coordinator.client.set_mute(mute)
            await self.coordinator.async_refresh()

        elif role == "master":
            # Master: mute/unmute entire group (existing behavior)
            for ip in self.group_members:
                coord = self._find_coordinator_by_ip(ip)
                if not coord:
                    continue
                try:
                    await coord.client.set_mute(mute)
                except Exception as err:
                    _LOGGER.debug("[WiiMGroup] Failed to set mute=%s on %s: %s", mute, ip, err)

            # Trigger refresh for all coordinators
            for ip in self.group_members:
                coord = self._find_coordinator_by_ip(ip)
                if coord:
                    try:
                        await coord.async_request_refresh()
                    except Exception:
                        pass

            self.async_write_ha_state()

        else:  # slave
            # Slave: mute/unmute only self
            await self.coordinator.client.set_mute(mute)
            await self.coordinator.async_refresh()

    async def async_media_play(self):
        """Handle play command based on role."""
        role = self.coordinator.data.get("role", "solo") if self.coordinator.data else "solo"

        if role == "slave":
            # Slave: propagate to master
            master_coord = self._find_master_coordinator()
            if master_coord:
                await master_coord.client.play()
                await master_coord.async_refresh()
                await self.coordinator.async_refresh()
            else:
                _LOGGER.warning(
                    "[WiiMGroup] Slave %s cannot find master to send play command",
                    self.device_ip,
                )
        else:
            # Solo or Master: control directly (solo) or all members (master)
            if role == "master":
                # Master: play on all members
                for ip in self.group_members:
                    coord = self._find_coordinator_by_ip(ip)
                    if coord:
                        await coord.client.play()
            else:
                # Solo: play on self
                await self.coordinator.client.play()

    async def async_media_pause(self):
        """Handle pause command based on role."""
        role = self.coordinator.data.get("role", "solo") if self.coordinator.data else "solo"

        if role == "slave":
            # Slave: propagate to master
            master_coord = self._find_master_coordinator()
            if master_coord:
                await master_coord.client.pause()
                await master_coord.async_refresh()
                await self.coordinator.async_refresh()
            else:
                _LOGGER.warning(
                    "[WiiMGroup] Slave %s cannot find master to send pause command",
                    self.device_ip,
                )
        else:
            # Solo or Master: control directly (solo) or all members (master)
            if role == "master":
                # Master: pause on all members
                for ip in self.group_members:
                    coord = self._find_coordinator_by_ip(ip)
                    if coord:
                        await coord.client.pause()
            else:
                # Solo: pause on self
                await self.coordinator.client.pause()

    async def async_media_next_track(self):
        """Handle next track command based on role."""
        role = self.coordinator.data.get("role", "solo") if self.coordinator.data else "solo"

        if role == "slave":
            # Slave: propagate to master
            master_coord = self._find_master_coordinator()
            if master_coord:
                await master_coord.client.next_track()
                await master_coord.async_refresh()
                await self.coordinator.async_refresh()
            else:
                _LOGGER.warning(
                    "[WiiMGroup] Slave %s cannot find master to send next_track command",
                    self.device_ip,
                )
        else:
            # Solo or Master: send command
            await self.coordinator.client.next_track()

    async def async_media_previous_track(self):
        """Handle previous track command based on role."""
        role = self.coordinator.data.get("role", "solo") if self.coordinator.data else "solo"

        if role == "slave":
            # Slave: propagate to master
            master_coord = self._find_master_coordinator()
            if master_coord:
                await master_coord.client.previous_track()
                await master_coord.async_refresh()
                await self.coordinator.async_refresh()
            else:
                _LOGGER.warning(
                    "[WiiMGroup] Slave %s cannot find master to send previous_track command",
                    self.device_ip,
                )
        else:
            # Solo or Master: send command
            await self.coordinator.client.previous_track()

    def _find_coordinator_by_ip(self, ip):
        # Helper to find coordinator by IP
        coord = find_coordinator_by_ip(self.hass, DOMAIN, ip)
        if coord:
            # coord.data may be None before the first successful poll
            role = coord.data.get("role") if coord.data else None
            multiroom = coord.data.get("multiroom", {}) if coord.data else {}
            _LOGGER.debug(
                "[WiiMGroup] Found coordinator for %s: role=%s, multiroom=%s, data=%s",
                ip,
                role,
                multiroom,
                coord.data,
            )
            return coord
        _LOGGER.debug("[WiiMGroup] No coordinator found for IP %s (likely not yet set up)", ip)
        return None

    def _find_master_coordinator(self):
        """Find the coordinator for the master of this device's group."""
        master_ip = self.coordinator.client.group_master
        if not master_ip:
            return None

        return find_coordinator_by_ip(self.hass, DOMAIN, master_ip)

    # ---------------------------------------------------------------------
    # Helper – centralised guard so we don't repeat None checks everywhere
    # ---------------------------------------------------------------------

    def _master_status(self) -> dict:
        """Return master's status dict or an empty one when unavailable."""

        coord = self._find_coordinator_by_ip(self.device_ip)
        if not coord or coord.data is None:
            return {}
        return coord.data.get("status", {})

    @property
    def available(self) -> bool:
        """Always available - this is an always-on entity."""
        return self.coordinator.data is not None

    @property
    def unique_id(self) -> str:
        """Return the unique_id for this entity."""
        return self._attr_unique_id

    @property
    def name(self) -> str:
        """Return the name of the entity, always using the latest device name from status."""
        if self.coordinator.data:
            status = self.coordinator.data.get("status", {})
            device_name = status.get("DeviceName") or status.get("device_name") or self.device_ip
            return f"{device_name} Master"
        # Fallback to initial name if no coordinator data
        return self._attr_name
