"""WiiM coordinator for handling device updates and groups."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any
import asyncio

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WiiMClient, WiiMError
from .const import (
    ATTR_GROUP_MEMBERS,
    ATTR_GROUP_LEADER,
    CONF_HOST,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class WiiMCoordinator(DataUpdateCoordinator):
    """WiiM coordinator for handling device updates and groups.

    This class manages the state and communication for WiiM devices in Home Assistant,
    providing centralized data management and group coordination.

    Key Responsibilities:
    - Periodic polling of device status
    - Group membership tracking and management
    - State synchronization between devices
    - Error handling and recovery
    - Device discovery and setup

    Data Management:
    - Maintains current device state
    - Tracks group membership and roles
    - Manages device configuration
    - Handles state updates and notifications

    Group Management:
    - Coordinates multiroom group operations
    - Maintains group membership information
    - Handles group creation and disbanding
    - Manages group synchronization

    Error Handling:
    - Implements retry logic for failed requests
    - Provides detailed error logging
    - Handles device disconnection gracefully
    - Maintains state consistency during errors
    """

    def __init__(
        self,
        hass: HomeAssistant,
        client: WiiMClient,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
    ) -> None:
        """Initialize WiiM coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{client._host}",
            update_interval=timedelta(seconds=poll_interval),
        )
        self.client = client
        self._group_members: set[str] = set()
        self._is_ha_group_leader = False
        self._ha_group_members: set[str] = set()
        self._base_poll_interval = poll_interval  # seconds
        self._consecutive_failures = 0
        self._imported_hosts: set[str] = set()
        # New: group registry
        self._groups: dict[str, dict] = {}  # master_ip -> group info
        self._last_title = None
        self._last_meta_info = {}
        self._meta_info_unsupported = False
        self._status_unsupported = False
        self._logged_entity_not_found_for_ha_group = False
        # Capability flags exposed to UI controls
        self.eq_supported: bool = True  # cleared when /getEQ answers "unknown command"
        self.eq_enabled: bool = False  # track EQ enabled state
        self.eq_presets: list[str] = []  # available EQ presets
        # Enable input source selection for all devices.  The media-player
        # entity will expose the selector unconditionally so users can swap
        # between Wi-Fi, Bluetooth, Line-In, etc. directly from Home-Assistant.
        self.source_supported: bool = True
        # Adaptive polling state
        self._last_play_state = None
        self._last_play_time = None
        self._eq_poll_counter = 0
        self._idle_timeout = 600  # 10 minutes in seconds

    def _parse_plm_support(self, plm_support: str) -> list[str]:
        """Parse plm_support bitmask into list of available sources."""
        try:
            # Convert hex string to integer
            mask = int(plm_support, 16)
            sources = []

            # Check each bit position
            if mask & 0x1:  # bit1
                sources.append("line_in")
            if mask & 0x2:  # bit2
                sources.append("bluetooth")
            if mask & 0x4:  # bit3
                sources.append("usb")
            if mask & 0x8:  # bit4
                sources.append("optical")
            if mask & 0x20:  # bit6
                sources.append("coaxial")
            if mask & 0x80:  # bit8
                sources.append("line_in_2")
            if mask & 0x8000:  # bit15
                sources.append("usbdac")

            # Add network sources that are always available
            sources.extend(["wifi", "airplay", "dlna"])

            return sources
        except (ValueError, TypeError):
            _LOGGER.error("[WiiM] Failed to parse plm_support: %s", plm_support)
            return []

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data from WiiM device."""
        try:
            # Fetch endpoints individually so we can gracefully degrade on devices lacking them
            player_status: dict[str, Any]
            basic_status: dict[str, Any]
            multiroom: dict[str, Any]

            # 1) Player status (getPlayerStatus) - primary source of playback state
            try:
                player_status = await self.client.get_player_status()
            except WiiMError as err:
                _LOGGER.debug("[WiiM] get_player_status failed on %s: %s", self.client.host, err)
                player_status = {}

            # 2) Basic status (getStatusEx) – skip if we previously marked unsupported
            # This provides additional device info like firmware version, device name, etc.
            if self._status_unsupported:
                basic_status = {}
            else:
                try:
                    basic_status = await self.client.get_status()
                except WiiMError as err:
                    _LOGGER.debug("[WiiM] get_status unsupported on %s: %s (will not retry)", self.client.host, err)
                    basic_status = {}
                    self._status_unsupported = True

            # 3) Multiroom info (always attempted) - required for group management
            try:
                multiroom = await self.client.get_multiroom_info()
            except WiiMError as err:
                _LOGGER.debug("[WiiM] get_multiroom_info failed on %s: %s", self.client.host, err)
                multiroom = {}

            # ------------------------------------------------------------------
            # Bail out early if *all* three primary endpoints failed.  Returning
            # an empty payload would incorrectly mark ``last_update_success`` as
            # True even though we have **zero** data.  Instead raise a
            # ``WiiMError`` which the outer handler converts into UpdateFailed.
            # ------------------------------------------------------------------
            if not player_status and not basic_status and not multiroom:
                raise WiiMError("All status endpoints failed")

            # Merge status data, preferring player_status for playback state
            status = {**basic_status, **player_status}
            current_title = status.get("title")
            current_play_state = status.get("play_status")

            # Update adaptive polling state
            now = asyncio.get_running_loop().time()
            if current_play_state != self._last_play_state:
                self._last_play_state = current_play_state
                self._last_play_time = now

            # Determine polling interval based on state
            if current_play_state == "play":
                # Active playback - poll every second
                self.update_interval = timedelta(seconds=1)
            elif self._last_play_time and (now - self._last_play_time) < self._idle_timeout:
                # Recently played - poll every 5 seconds
                self.update_interval = timedelta(seconds=5)
            else:
                # Idle - poll every 10 seconds
                self.update_interval = timedelta(seconds=10)

            # Only fetch meta info if supported & title changed
            if not self._meta_info_unsupported and (
                current_title != self._last_title or not self._last_meta_info
            ):
                meta_info = await self.client.get_meta_info()
                if not meta_info:
                    # Empty dict – very likely unsupported on this device
                    self._meta_info_unsupported = True
                else:
                    self._last_title = current_title
                    self._last_meta_info = meta_info
            else:
                meta_info = self._last_meta_info

            # Merge meta info
            if meta_info:
                status["album"] = meta_info.get("album")
                status["title"] = meta_info.get("title")
                status["artist"] = meta_info.get("artist")
                status["entity_picture"] = meta_info.get("albumArtURI")

            # ------------------------------------------------------------------
            # 4) EQ information – poll at 1/3 rate and only if supported
            # ------------------------------------------------------------------
            self._eq_poll_counter += 1
            if self.eq_supported and self._eq_poll_counter >= 3:
                self._eq_poll_counter = 0
                try:
                    # ----------------------------------------------
                    # 1) Determine whether EQ is enabled.  On some
                    #    builds EQGetStat is absent; our helper tries a
                    #    heuristic and may leave the state unchanged.
                    # ----------------------------------------------
                    eq_enabled = await self.client.get_eq_status()
                    self.eq_enabled = eq_enabled
                    status["eq_enabled"] = eq_enabled

                    # ----------------------------------------------
                    # 2) Always fetch the current EQ settings – even
                    #    when *disabled*.  This guarantees that changes
                    #    made in the WiiM mobile app are reflected in
                    #    Home-Assistant without having to toggle the
                    #    enable switch first.
                    # ----------------------------------------------
                    eq_info = await self.client.get_eq()
                    if eq_info:
                        mode_raw = eq_info.get("mode")
                        if mode_raw is not None:
                            preset = self.client._EQ_NUMERIC_MAP.get(str(mode_raw), mode_raw)
                            status["eq_preset"] = preset

                        # Custom curve – list of 10 integers (-12…+12 dB)
                        if "custom" in eq_info and isinstance(eq_info["custom"], list):
                            status["eq_custom"] = eq_info["custom"]

                    # Get available presets if we haven't yet
                    if not self.eq_presets:
                        self.eq_presets = await self.client.get_eq_presets()
                        status["eq_presets"] = self.eq_presets

                except Exception as eq_err:  # noqa: BLE001 – non-fatal
                    # Mark EQ as unsupported after the first explicit "unknown command"
                    if isinstance(eq_err, Exception) and "unknown command" in str(eq_err).lower():
                        if self.eq_supported:
                            _LOGGER.info("[WiiM] %s: getEQ not supported – hiding EQ selector", self.client.host)
                        self.eq_supported = False
                    _LOGGER.debug("[WiiM] get_eq failed on %s: %s", self.client.host, eq_err)

            # Parse available sources from plm_support
            plm_support = status.get("plm_support", "0")
            sources = self._parse_plm_support(plm_support)
            _LOGGER.debug("[WiiM] %s: Parsed sources from plm_support: %s", self.client.host, sources)
            status["sources"] = sources

            # -----------------------------------------------------------
            # Streaming-service provider (Spotify / Tidal / Amazon …)
            # The *vendor* field set by LinkPlay is our best hint.  Expose
            # it under a stable key so the media_player entity can surface
            # it via app_name/extra attributes.
            # -----------------------------------------------------------
            vendor_raw = str(status.get("vendor", "")).strip()
            if vendor_raw and vendor_raw.lower() not in ("", "unknown", "unknow"):
                # Many firmwares include **extra context** after a colon
                # (e.g. "Spotify:Station:Playlist:…").  Keep only the
                # provider name so the HA card shows a clean label.
                vendor_clean = vendor_raw.split(":", 1)[0]
                status["streaming_service"] = vendor_clean.title()

            # Determine role
            role = "solo"
            # LinkPlay firmwares sometimes return the numeric value **1** instead of the string "1".
            # Cast to *str* so we detect both representations transparently.
            if str(multiroom.get("type")) == "1":
                role = "slave"
            elif multiroom.get("slave_list"):
                role = "master"

            # Update group registry
            self._update_group_registry(status, multiroom)

            # If we reach here the poll succeeded – reset failure counter and interval
            if self._consecutive_failures:
                self._consecutive_failures = 0
                if (
                    self.update_interval is not None
                    and self.update_interval.total_seconds() != self._base_poll_interval
                ):
                    self.update_interval = timedelta(seconds=self._base_poll_interval)

            # Update multiroom status & trigger discovery of new slave IPs
            self._group_members = {
                entry.get("ip") for entry in multiroom.get("slave_list", []) if entry.get("ip")
            }

            await self._async_trigger_slave_discovery()
            self._update_ha_group_status()

            # ------------------------------------------------------------------
            # Post-process *source* to avoid confusing "Follower" on SOLO / MASTER
            # speakers.  Some firmwares keep reporting ``mode = 99`` (follower)
            # even after the device left a group which leaves the UI showing an
            # incorrect source.  When our *role* detection says we are NOT a
            # slave we translate the source back to "wifi" (internal streamer).
            # ------------------------------------------------------------------
            if role != "slave" and status.get("source") == "follower":
                _LOGGER.debug("[WiiM] %s: Overriding stray 'follower' source with 'wifi' (role=%s)", self.client.host, role)
                status["source"] = "wifi"

            return {
                "status": status,
                "multiroom": multiroom,
                "role": role,
                "ha_group": {
                    "is_leader": self._is_ha_group_leader,
                    "members": list(self._ha_group_members),
                },
            }
        except WiiMError as err:
            # Progressive back-off on consecutive failures to reduce log spam
            self._consecutive_failures += 1
            if self._consecutive_failures >= 3:
                new_interval = min(
                    self._base_poll_interval * (2 ** (self._consecutive_failures - 2)),
                    60,
                )
                if (
                    self.update_interval is None
                    or new_interval != self.update_interval.total_seconds()
                ):
                    self.update_interval = timedelta(seconds=new_interval)
            raise UpdateFailed(f"Error updating WiiM device: {err}")

    def _update_group_registry(self, status: dict, multiroom: dict) -> None:
        """Update the group registry with current group info."""
        _LOGGER.debug("[WiiM] _update_group_registry: status=%s, multiroom=%s", status, multiroom)

        # ------------------------------------------------------------------
        # 0) House-keeping – drop *stale* groups this coordinator may still
        #    carry from an earlier poll.  A group is considered stale if
        #    (a) its master_ip equals *this* speaker and (b) the speaker is
        #    currently not hosting any slaves and does not report itself as a
        #    slave.  Without this cleanup the virtual "<Room> (Group)"
        #    entity lingers after a user calls multiroom:Ungroup().
        # ------------------------------------------------------------------
        is_currently_master = multiroom.get("slaves", 0) > 0
        is_currently_slave = str(multiroom.get("type")) == "1" or str(status.get("type")) == "1"

        if not is_currently_master and not is_currently_slave:
            # Speaker is in *solo* mode → remove any registry that still lists
            # it as a master.
            if self.client.host in self._groups:
                _LOGGER.debug(
                    "[WiiM] _update_group_registry: Removing stale group entry for %s (device is solo)",
                    self.client.host,
                )
                self._groups.pop(self.client.host, None)

        # ------------------------------------------------------------------
        # 1) Determine if the current poll contains *valid* group info (either
        #    because we're a master or a slave).  If we cannot identify a
        #    master_ip we bail out – the above cleanup already made sure no
        #    stale entry with our own host remains.
        # ------------------------------------------------------------------
        # Try to determine master_ip from own multiroom info
        master_ip = self.client.host if multiroom.get("slaves", 0) > 0 else multiroom.get("master_uuid")
        # If not found and this device is a slave, search all coordinators for a master whose slave_list includes this device
        if not master_ip and (str(multiroom.get("type")) == "1" or str(status.get("type")) == "1"):
            my_ip = self.client.host
            my_uuid = status.get("device_id")
            for coord in self.hass.data[DOMAIN].values():
                if not hasattr(coord, "client") or coord.data is None:
                    continue
                # Check if this coordinator is a master
                coord_multiroom = coord.data.get("multiroom", {})
                slave_list = coord_multiroom.get("slave_list", [])
                for slave in slave_list:
                    if isinstance(slave, dict):
                        slave_ip = slave.get("ip")
                        slave_uuid = slave.get("uuid")
                        if (my_ip and my_ip == slave_ip) or (my_uuid and my_uuid == slave_uuid):
                            master_ip = coord.client.host
                            _LOGGER.debug("[WiiM] _update_group_registry: Found master %s for slave %s by slave_list", master_ip, my_ip)
                            break
                if master_ip:
                    break
        _LOGGER.debug("[WiiM] _update_group_registry: master_ip=%s", master_ip)
        if not master_ip:
            _LOGGER.debug("[WiiM] _update_group_registry: No master_ip found, skipping group registry update.")
            return
        master_name = status.get("device_name") or "WiiM Group"
        group_info = self._groups.setdefault(master_ip, {"members": {}, "master": master_ip, "name": master_name})
        group_info["name"] = master_name  # Always update name in case it changes
        # Add master
        group_info["members"][self.client.host] = {
            "volume": status.get("volume", 0),
            "mute": status.get("mute", False),
            "state": status.get("play_status"),
            "name": master_name,
        }
        # Add slaves
        for entry in multiroom.get("slave_list", []):
            ip = entry.get("ip")
            if not ip:
                continue
            slave_name = entry.get("name") or f"WiiM {ip}"
            group_info["members"][ip] = {
                "volume": entry.get("volume", 0),
                "mute": bool(entry.get("mute", False)),
                "state": None,  # Will be filled in by polling that device
                "name": slave_name,
            }
        # Clean up any members no longer present
        current_ips = {self.client.host} | {entry.get("ip") for entry in multiroom.get("slave_list", []) if entry.get("ip")}
        group_info["members"] = {ip: v for ip, v in group_info["members"].items() if ip in current_ips}
        _LOGGER.debug("[WiiM] _update_group_registry: group_info=%s", group_info)

    def _update_ha_group_status(self) -> None:
        """Update Home Assistant group status."""
        entity_id = f"media_player.wiim_{self.client._host.replace('.', '_')}"
        entity = self.hass.states.get(entity_id)

        if entity is None:
            if not hasattr(self, '_logged_entity_not_found_for_ha_group') or not self._logged_entity_not_found_for_ha_group:
                _LOGGER.debug(
                    "[WiiM] Coordinator: Entity %s not found for group status update. "
                    "This may be normal on startup or if the entity is not part of an HA group. "
                    "Further similar messages for this entity will be suppressed.",
                    entity_id
                )
                self._logged_entity_not_found_for_ha_group = True
            return

        # If entity is found, reset the flag so it would log again if it disappears later
        self._logged_entity_not_found_for_ha_group = False

        group_members = entity.attributes.get(ATTR_GROUP_MEMBERS, [])
        group_leader = entity.attributes.get(ATTR_GROUP_LEADER)

        _LOGGER.debug("[WiiM] Coordinator: Entity %s group_members: %s, group_leader: %s", entity_id, group_members, group_leader)

        self._ha_group_members = set(group_members)
        self._is_ha_group_leader = group_leader == entity_id

    async def _async_trigger_slave_discovery(self) -> None:
        """Start config flows for new slave IPs that HA doesn't know yet."""
        for ip in self._group_members:
            if ip in self._imported_hosts:
                continue

            # Skip if already present – ensure we only inspect coordinator objects
            if any(
                hasattr(coord, "client") and coord.client.host == ip
                for coord in self.hass.data.get(DOMAIN, {}).values()
            ):
                self._imported_hosts.add(ip)
                continue

            # If we're the master of the current group, force the slave to leave
            # before importing it so Home-Assistant discovers it in *solo* mode
            # and avoids the missing-coordinator noise.  This replicates the
            # behaviour of python-linkplay which issues a leave/kick on
            # discovery.
            try:
                if self.is_wiim_master:
                    _LOGGER.debug("[WiiM] Master %s kicking slave %s prior to import", self.client.host, ip)
                    await self.client.kick_slave(ip)
            except Exception as kick_err:
                _LOGGER.debug("[WiiM] Failed to kick slave %s: %s (continuing import)", ip, kick_err)

            # Prevent duplicate config-entries: skip if another entry already
            # has the same host (even if its unique_id differs for legacy
            # reasons or the entry is not fully set up yet)
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if entry.data.get(CONF_HOST) == ip:
                    _LOGGER.debug("[WiiM] Config entry for %s already exists (%s). Skipping import.", ip, entry.entry_id)
                    self._imported_hosts.add(ip)
                    break
            else:
                # Only start a flow if no existing entry with this host
                self.hass.async_create_task(
                    self.hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={"source": "import"},
                        data={CONF_HOST: ip},
                    )
                )
                _LOGGER.debug("Started import flow for slave %s", ip)

            # Mark as processed to avoid future duplicate attempts
            self._imported_hosts.add(ip)

    async def create_wiim_group(self) -> None:
        """Create a WiiM multiroom group."""
        try:
            _LOGGER.info("[WiiM] Coordinator: Creating new WiiM group for %s", self.client.host)
            await self.client.create_group()
            _LOGGER.info("[WiiM] Coordinator: Successfully created WiiM group for %s", self.client.host)
            await self.async_refresh()
        except WiiMError as err:
            _LOGGER.error("[WiiM] Coordinator: Failed to create WiiM group for %s: %s", self.client.host, err)
            raise

    async def delete_wiim_group(self) -> None:
        """Delete the WiiM multiroom group."""
        try:
            _LOGGER.info("[WiiM] Coordinator: Deleting WiiM group for %s", self.client.host)
            await self.client.delete_group()
            _LOGGER.info("[WiiM] Coordinator: Successfully deleted WiiM group for %s", self.client.host)
            await self.async_refresh()
        except WiiMError as err:
            _LOGGER.error("[WiiM] Coordinator: Failed to delete WiiM group for %s: %s", self.client.host, err)
            raise

    async def join_wiim_group(self, master_ip: str) -> None:
        """Join a WiiM multiroom group."""
        try:
            _LOGGER.info("[WiiM] Coordinator: %s joining WiiM group with master %s", self.client.host, master_ip)
            await self.client.join_group(master_ip)
            _LOGGER.info("[WiiM] Coordinator: %s successfully joined WiiM group with master %s", self.client.host, master_ip)
            await self.async_refresh()
        except WiiMError as err:
            _LOGGER.error("[WiiM] Coordinator: %s failed to join WiiM group with master %s: %s", self.client.host, master_ip, err)
            raise

    async def leave_wiim_group(self) -> None:
        """Leave the WiiM multiroom group."""
        try:
            _LOGGER.info("[WiiM] Coordinator: %s leaving WiiM group", self.client.host)
            await self.client.leave_group()
            _LOGGER.info("[WiiM] Coordinator: %s successfully left WiiM group", self.client.host)
            await self.async_refresh()
        except WiiMError as err:
            _LOGGER.error("[WiiM] Coordinator: %s failed to leave WiiM group: %s", self.client.host, err)
            raise

    @property
    def is_wiim_master(self) -> bool:
        """Return whether this device is a WiiM multiroom master."""
        return self.client.is_master

    @property
    def is_wiim_slave(self) -> bool:
        """Return whether this device is a WiiM multiroom slave."""
        return self.client.is_slave

    @property
    def wiim_group_members(self) -> set[str]:
        """Return set of WiiM group member IPs."""
        return self._group_members

    @property
    def is_ha_group_leader(self) -> bool:
        """Return whether this device is a HA media player group leader."""
        return self._is_ha_group_leader

    @property
    def ha_group_members(self) -> set[str]:
        """Return set of HA group member entity IDs."""
        return self._ha_group_members

    @property
    def groups(self) -> dict:
        """Return the current group registry."""
        return self._groups

    def get_group_by_master(self, master_ip: str) -> dict | None:
        """Get group info by master IP."""
        return self._groups.get(master_ip)

    def get_member_info(self, ip: str) -> dict | None:
        """Get member info by IP."""
        for group in self._groups.values():
            if ip in group["members"]:
                return group["members"][ip]
        return None

    # ---------------------------------------------------------------------
    # Convenience helpers --------------------------------------------------
    # ---------------------------------------------------------------------

    @property
    def friendly_name(self) -> str:
        """Return a human-friendly name for the device.

        Prefer the HTTP-API field ``device_name`` (normalised) or the raw
        ``DeviceName`` if present; otherwise fall back to the host.
        """

        status = self.data.get("status", {}) if isinstance(self.data, dict) else {}
        return (
            status.get("device_name")
            or status.get("DeviceName")  # legacy field – shouldn't exist now
            or self.client.host
        )

    # ---------------------------------------------------------------------
    # Compatibility helpers (used by Number entities) ---------------------
    # ---------------------------------------------------------------------

    async def async_stop(self) -> None:
        """Pause the periodic polling loop.

        The :class:`homeassistant.helpers.update_coordinator.DataUpdateCoordinator`
        keeps an internal unsubscribe callback (``_unsub_refresh``) that is used
        to cancel the scheduled refresh timer.  We call it here to ensure the
        old timer is cleared before adjusting the update interval.
        """

        unsub = getattr(self, "_unsub_refresh", None)
        if unsub is not None:
            # Cancel the existing scheduled refresh call
            unsub()
            # Mark as unscheduled so ``_schedule_refresh`` can create a new one
            self._unsub_refresh = None  # type: ignore[attr-defined]

    async def async_start(self) -> None:
        """Resume the periodic polling loop using the current update_interval."""

        # The base coordinator exposes a private ``_schedule_refresh`` helper
        # that (re-)schedules the periodic call.  It is safe to invoke here.
        if hasattr(self, "_schedule_refresh"):
            # pylint: disable=protected-access
            self._schedule_refresh()  # type: ignore[attr-defined]
        # Trigger an immediate refresh so listeners get up-to-date data
        await self.async_refresh()
