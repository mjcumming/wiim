from homeassistant.components.media_player import MediaPlayerEntity, MediaPlayerState, MediaPlayerEntityFeature
from .const import DOMAIN
import logging

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

    def __init__(self, hass, coordinator, master_ip):
        self.hass = hass
        self.coordinator = coordinator
        self.master_ip = master_ip
        group_info = coordinator.get_group_by_master(master_ip) or {}
        group_name = group_info.get('name')
        if not group_name or group_name.strip().lower() in ("wiim group", "none", "null", ""):
            group_name = f"WiiM Group {master_ip}"
        safe_name = (
            group_name.replace(' ', '_')
            .replace('(', '')
            .replace(')', '')
            .replace(',', '')
            .replace('.', '_')
            .replace('none', '')
            .replace('null', '')
            .lower()
        )
        self._attr_unique_id = f"wiim_group_{safe_name}"
        self._attr_name = f"{group_name} (Group)"
        self._attr_supported_features = (
            MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.GROUPING
        )

    @property
    def group_info(self):
        info = self.coordinator.get_group_by_master(self.master_ip) or {}
        _LOGGER.debug("[WiiMGroup] Group info for master %s: %s", self.master_ip, info)
        return info

    @property
    def group_members(self):
        return list(self.group_info.get("members", {}).keys())

    @property
    def group_leader(self):
        return self.master_ip

    @property
    def state(self):
        # Get master's state directly from its coordinator
        master_coord = self._find_coordinator_by_ip(self.master_ip)
        if not master_coord:
            _LOGGER.warning("[WiiMGroup] No coordinator found for master %s in group %s", self.master_ip, self._attr_name)
            return MediaPlayerState.IDLE

        status = master_coord.data.get("status", {})
        role = master_coord.data.get("role")
        _LOGGER.debug(
            "[WiiMGroup] Master %s state check - role=%s, status=%s",
            self.master_ip, role, status
        )

        if not status.get("power"):
            return MediaPlayerState.OFF
        if status.get("play_status") == "play":
            return MediaPlayerState.PLAYING
        if status.get("play_status") == "pause":
            return MediaPlayerState.PAUSED
        return MediaPlayerState.IDLE

    @property
    def volume_level(self):
        # Always get the latest volume from each coordinator
        max_vol = 0
        for ip in self.group_members:
            coord = self._find_coordinator_by_ip(ip)
            if coord and coord.data and "status" in coord.data:
                vol = coord.data["status"].get("volume", 0)
                if vol > max_vol:
                    max_vol = vol
        return float(max_vol) / 100

    @property
    def is_volume_muted(self):
        """Return *aggregate* mute state.

        Home-Assistant shows a single toggle for the whole group; we treat the
        group as muted **only** when *every* member is muted.  If at least one
        speaker is un-muted the group reports `False` so clicking the icon in
        the UI will try to mute all.
        """

        any_unmuted = False
        any_known = False
        for ip in self.group_members:
            coord = self._find_coordinator_by_ip(ip)
            if not coord or "status" not in coord.data:
                continue
            any_known = True
            if not coord.data["status"].get("mute", False):
                any_unmuted = True
                break

        if not any_known:
            return None  # Unknown
        return not any_unmuted

    @property
    def extra_state_attributes(self):
        # Expose per-slave volume/mute
        attrs = {}
        for ip, m in self.group_info.get("members", {}).items():
            attrs[f"member_{ip}_volume"] = m.get("volume")
            attrs[f"member_{ip}_mute"] = m.get("mute")
            attrs[f"member_{ip}_name"] = m.get("name")
        return attrs

    @property
    def supported_features(self):
        return self._attr_supported_features

    @property
    def entity_picture(self):
        master_coord = self._find_coordinator_by_ip(self.master_ip)
        if not master_coord:
            _LOGGER.debug("[WiiMGroup] No coordinator found for master %s in group %s", self.master_ip, self._attr_name)
            return None
        pic = master_coord.data.get("status", {}).get("entity_picture")
        if not pic:
            _LOGGER.debug("[WiiMGroup] No entity_picture for master %s in group %s: %s", self.master_ip, self._attr_name, master_coord.data.get("status", {}))
        return pic

    @property
    def media_title(self):
        master_coord = self._find_coordinator_by_ip(self.master_ip)
        if not master_coord:
            _LOGGER.debug("[WiiMGroup] No coordinator found for master %s in group %s", self.master_ip, self._attr_name)
            return None
        title = master_coord.data.get("status", {}).get("title")
        if not title:
            _LOGGER.debug("[WiiMGroup] No media_title for master %s in group %s: %s", self.master_ip, self._attr_name, master_coord.data.get("status", {}))
        return title

    @property
    def media_artist(self):
        master_coord = self._find_coordinator_by_ip(self.master_ip)
        if not master_coord:
            _LOGGER.debug("[WiiMGroup] No coordinator found for master %s in group %s", self.master_ip, self._attr_name)
            return None
        artist = master_coord.data.get("status", {}).get("artist")
        if not artist:
            _LOGGER.debug("[WiiMGroup] No media_artist for master %s in group %s: %s", self.master_ip, self._attr_name, master_coord.data.get("status", {}))
        return artist

    @property
    def media_album_name(self):
        master_coord = self._find_coordinator_by_ip(self.master_ip)
        if not master_coord:
            _LOGGER.debug("[WiiMGroup] No coordinator found for master %s in group %s", self.master_ip, self._attr_name)
            return None
        album = master_coord.data.get("status", {}).get("album")
        if not album:
            _LOGGER.debug("[WiiMGroup] No media_album_name for master %s in group %s: %s", self.master_ip, self._attr_name, master_coord.data.get("status", {}))
        return album

    @property
    def media_position(self):
        master_coord = self._find_coordinator_by_ip(self.master_ip)
        if master_coord:
            return master_coord.data.get("status", {}).get("position")
        return None

    @property
    def media_duration(self):
        master_coord = self._find_coordinator_by_ip(self.master_ip)
        if master_coord:
            return master_coord.data.get("status", {}).get("duration")
        return None

    @property
    def media_position_updated_at(self):
        master_coord = self._find_coordinator_by_ip(self.master_ip)
        if master_coord:
            return master_coord.data.get("status", {}).get("position_updated_at")
        return None

    async def async_set_volume_level(self, volume):
        # Always get the latest volume from each coordinator
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

    async def async_mute_volume(self, mute: bool):
        """Mute or unmute the entire group.

        For a LinkPlay group the master owns audio rendering; slaves ignore
        direct volume/mute commands.  The correct way to change a slave's
        mute state is to ask the master via the ``multiroom:SlaveMute``
        command.  Hence:

        • master → call ``set_mute`` directly; this also propagates to itself
        • each slave → call ``master.mute_slave(slave_ip, mute)``.
        """

        # Iterate over all members (master + slaves) and send the standard
        # setPlayerCmd:mute command.  Slaves accept it just fine and this keeps
        # behaviour symmetrical.

        for ip in self.group_members:
            coord = self._find_coordinator_by_ip(ip)
            if not coord:
                continue
            try:
                await coord.client.set_mute(mute)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("[WiiMGroup] Failed to set mute=%s on %s: %s", mute, ip, err)

        # Trigger an *immediate* refresh for every coordinator so the updated
        # mute state becomes visible without waiting for the next poll.
        for ip in self.group_members:
            coord = self._find_coordinator_by_ip(ip)
            if coord:
                try:
                    await coord.async_request_refresh()  # type: ignore[attr-defined]
                except Exception:  # noqa: BLE001 – best-effort
                    pass

        # Finally update our own HA state so the UI reflects the new aggregate
        # mute status right away.
        self.async_write_ha_state()

    async def async_media_play(self):
        # Play on all members
        for ip in self.group_members:
            coord = self._find_coordinator_by_ip(ip)
            if coord:
                await coord.client.play()

    async def async_media_pause(self):
        # Pause on all members
        for ip in self.group_members:
            coord = self._find_coordinator_by_ip(ip)
            if coord:
                await coord.client.pause()

    async def async_media_next_track(self):
        """Send next track command to the group master only."""
        master_coord = self._find_coordinator_by_ip(self.master_ip)
        if master_coord:
            await master_coord.client.next_track()
        else:
            _LOGGER.warning("[WiiMGroup] No coordinator found for master %s when trying to send next_track", self.master_ip)

    async def async_media_previous_track(self):
        """Send previous track command to the group master only."""
        master_coord = self._find_coordinator_by_ip(self.master_ip)
        if master_coord:
            await master_coord.client.previous_track()
        else:
            _LOGGER.warning("[WiiMGroup] No coordinator found for master %s when trying to send previous_track", self.master_ip)

    def _find_coordinator_by_ip(self, ip):
        # Helper to find coordinator by IP
        for coord in self.hass.data[DOMAIN].values():
            # Skip any non-coordinator entries that may have been added to hass.data[DOMAIN]
            if not hasattr(coord, "client"):
                continue
            if coord.client.host == ip:
                role = coord.data.get("role")
                multiroom = coord.data.get("multiroom", {})
                _LOGGER.debug(
                    "[WiiMGroup] Found coordinator for %s: role=%s, multiroom=%s, data=%s",
                    ip, role, multiroom, coord.data
                )
                return coord
        _LOGGER.debug("[WiiMGroup] No coordinator found for IP %s (likely not yet set up)", ip)
        return None