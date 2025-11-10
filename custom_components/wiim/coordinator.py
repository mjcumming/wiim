"""WiiM coordinator for polling and device updates."""

from __future__ import annotations

import logging
import time as _time
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WiiMClient, WiiMError
from .coordinator_backoff import BackoffController
from .models import DeviceInfo, PlayerStatus

_LOGGER = logging.getLogger(__name__)

# Toggle to True if you really need full payloads in the log.
# When False (default) large dicts are truncated to a list of top-level keys
# which is usually enough for troubleshooting without spamming the log.
VERBOSE_DEBUG = False

# Enhanced logging escalation thresholds (more balanced for production)
# 1-2 failures: debug (likely transient network issues)
# 3-4 failures: warning (device having connectivity problems)
# 5+ failures: error (device likely offline/unavailable)
FAILURE_ERROR_THRESHOLD = 5  # More balanced - escalate after ~25s with normal polling

# Command failure tracking - for immediate user feedback
COMMAND_FAILURE_TIMEOUT = 30  # seconds - how long to remember command failures


class WiiMCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """WiiM coordinator with adaptive smart polling per POLLING_STRATEGY.md.

    This coordinator implements smart polling that adapts to device activity:
    - 1-second polling during active playback for real-time updates
    - 5-second polling when idle for resource efficiency
    - Conditional fetching based on data type and activity
    - Graceful degradation with fallbacks for unreliable endpoints

    Key principles:
    - getPlayerStatus is universal endpoint (works on all devices)
    - getStatusEx is universal endpoint (works on all devices)
    - getMetaInfo may not work on many LinkPlay devices
    - EQ endpoints are highly inconsistent across manufacturers
    """

    def __init__(
        self,
        hass: HomeAssistant,
        client: WiiMClient,
        entry=None,
        capabilities: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the coordinator with adaptive polling and firmware capabilities."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"WiiM {client.host}",
            update_interval=timedelta(seconds=5),  # Default interval, will adapt based on state/failures
        )
        self.client = client
        self.hass = hass
        self.entry = entry
        self._capabilities = capabilities or {}

        # Enhanced Audio Pro logging on initialization
        is_legacy_device = self._capabilities.get("is_legacy_device", False)
        audio_pro_generation = self._capabilities.get("audio_pro_generation", "unknown")

        if is_legacy_device:
            if audio_pro_generation == "mkii":
                _LOGGER.info(
                    "🔊 Audio Pro MkII device detected: %s - using enhanced compatibility mode",
                    client.host,
                )
            elif audio_pro_generation == "w_generation":
                _LOGGER.info(
                    "🔊 Audio Pro W-Generation device detected: %s - using advanced features",
                    client.host,
                )
            else:
                _LOGGER.info(
                    "🔊 Audio Pro legacy device detected: %s - using compatibility mode",
                    client.host,
                )
        elif self._capabilities.get("is_wiim_device", False):
            _LOGGER.info("✅ WiiM device detected: %s - using full feature set", client.host)
        else:
            _LOGGER.info(
                "📻 LinkPlay device detected: %s - using standard compatibility",
                client.host,
            )

        # API capability flags (None = untested, True/False = tested)
        self._statusex_supported: bool | None = None
        self._metadata_supported: bool | None = None
        self._eq_supported: bool | None = None
        self._presets_supported: bool | None = None

        # Device state tracking
        self._last_status: dict[str, Any] = {}

        # Back-off controller for failure handling
        self._backoff = BackoffController()

        # Command failure tracking for immediate user feedback
        self._last_command_failure: float | None = None  # timestamp of last command failure
        self._command_failure_count = 0  # count of recent command failures

        # Track device info update timing (every 30-60 seconds)
        self._last_device_info_update = 0.0  # type: ignore[assignment]
        self._device_info_interval = 30

        # Debug: Track update calls
        self._update_count = 0

        # One-time flag for dynamic EQ preset discovery
        self._eq_list_extended: bool = False

        # ---------------- Performance metrics ----------------
        # Duration of the last successful coordinator update (ms)
        self._last_response_time: float | None = None

        # Per-endpoint health flags (True = last call succeeded, False = failed)
        self._player_status_working: bool | None = None
        self._device_info_working: bool | None = None
        self._multiroom_working: bool | None = None

        # ---------------- Statistics tracking ----------------
        # HTTP polling statistics
        self._http_poll_total: int = 0  # Total polls attempted
        self._http_poll_success: int = 0  # Successful polls
        self._http_poll_failure: int = 0  # Failed polls
        self._http_response_times: list[float] = []  # Last 100 response times (ms)
        self._http_last_success_time: float | None = None  # Timestamp of last success
        self._http_last_failure_time: float | None = None  # Timestamp of last failure

        # Command statistics
        self._command_total: int = 0  # Total commands sent
        self._command_success: int = 0  # Successful commands
        self._command_failure_total: int = 0  # Total failed commands (not just recent)
        self._command_last_success_time: float | None = None  # Timestamp of last success
        self._command_last_failure_time: float | None = None  # Timestamp of last failure

        _LOGGER.info(
            "Coordinator initialized for %s with adaptive polling (1s when playing, 5s when idle)",
            client.host,
        )

    @property
    def device_uuid(self) -> str | None:
        """Return device UUID using typed models first, falling back gracefully."""

        if not self.data or not isinstance(self.data, dict):
            return None

        device_model = self.data.get("device_model")
        if isinstance(device_model, DeviceInfo) and device_model.uuid:
            return device_model.uuid

        status_model = self.data.get("status_model")
        if isinstance(status_model, PlayerStatus):
            return getattr(status_model, "uuid", None)

        return None

    @property
    def device_name(self) -> str:
        """Return device name derived from :class:`DeviceInfo` if available."""

        if not self.data or not isinstance(self.data, dict):
            return self.client.host

        device_model = self.data.get("device_model")
        if isinstance(device_model, DeviceInfo) and device_model.name:
            return device_model.name

        # Fallback to client host as final resort
        return self.client.host

    def has_slaves(self) -> bool:
        """Check if this device has slaves (making it a master)."""
        if self.data and isinstance(self.data, dict):
            multiroom = self.data.get("multiroom", {})
            # Handle both scenarios: slaves as list or as count
            slaves_data = multiroom.get("slaves", 0)
            if isinstance(slaves_data, list):
                # If slaves is a list, check its length
                return len(slaves_data) > 0
            # If slaves is a number, use it directly
            slave_count = slaves_data or multiroom.get("slave_count", 0)
            return slave_count > 0
        return False

    async def _get_player_status(self) -> dict:
        """Get player status – prefers typed model, falls back to raw dict.

        This maintains backward-compatibility with existing unit-tests that
        patch ``get_player_status`` on a mock client while allowing real
        runtime code to benefit from the new Pydantic helpers without code
        duplication across the coordinator.
        """
        try:
            from . import coordinator_endpoints as _endpoints

            model = await _endpoints.fetch_player_status(self.client)
            result: dict[str, Any] = model.model_dump(exclude_none=True)

            if VERBOSE_DEBUG:
                _LOGGER.debug("Player status result for %s: %s", self.client.host, result)
            else:
                _LOGGER.debug(
                    "Player status result for %s (keys=%s)",
                    self.client.host,
                    list(result.keys()),
                )

            return result

        except WiiMError as err:
            _LOGGER.warning("[WiiM] %s: getPlayerStatus failed: %s", self.client.host, err)
            raise
        except Exception as err:
            _LOGGER.error(
                "[WiiM] %s: Unexpected error in get_player_status: %s",
                self.client.host,
                err,
            )
            raise

    async def _fetch_device_info(self) -> dict[str, Any]:
        """Fetch device information, handling potential errors or missing support."""
        try:
            from . import coordinator_endpoints as _endpoints

            model = await _endpoints.fetch_device_info(self.client)
            device_info: dict[str, Any] = model.model_dump(exclude_none=True)

            if not device_info.get("uuid"):
                # Some devices don't provide UUID in their API responses - this is normal
                # The integration uses the unique_id from config entry (set during discovery)
                _LOGGER.debug(
                    "Device API does not provide UUID for %s (using config entry unique_id instead)",
                    self.client.host,
                )
                # Note: The unique ID established in ConfigFlow is the primary one and is sufficient
                # This missing API UUID does not affect integration functionality
            return device_info
        except WiiMError as err:
            _LOGGER.debug(
                "Failed to get device info for %s: %s, device info will be unavailable",
                self.client.host,
                err,
            )
        return {}

    async def _async_update_data(self) -> dict[str, Any]:
        """Centralized polling logic with adaptive intervals and backoff on failure."""
        # Imports are here to prevent circular dependency issues at startup
        from . import coordinator_polling as _poll
        from .coordinator_polling import (
            NORMAL_POLL_INTERVAL,
            _determine_adaptive_interval,
        )

        try:
            # Delegate the actual data fetching to the polling module
            data = await _poll.async_update_data(self)

            # On success, reset the backoff controller
            if self._backoff.consecutive_failures > 0:
                _LOGGER.info(
                    "Successfully reconnected to %s, restoring normal polling",
                    self.client.host,
                )
            self._backoff.record_success()

            # Track HTTP polling success
            self._http_poll_total += 1
            self._http_poll_success += 1
            self._http_last_success_time = _time.time()

            # Dynamically adjust polling interval based on the device's current state
            status_model = data.get("status_model")
            role = data.get("role")

            if status_model and role:
                new_interval_seconds = _determine_adaptive_interval(self, status_model, role)
            else:
                # Fallback to normal idle polling if state is not fully determined
                new_interval_seconds = NORMAL_POLL_INTERVAL

            # Only update the interval if it has changed to avoid unnecessary churn
            if self.update_interval.total_seconds() != new_interval_seconds:
                _LOGGER.debug(
                    "Polling interval for %s set to %ss",
                    self.client.host,
                    new_interval_seconds,
                )
                self.update_interval = timedelta(seconds=new_interval_seconds)

            return data

        except (WiiMError, aiohttp.ClientError) as err:
            # Track HTTP polling failure
            self._http_poll_total += 1
            self._http_poll_failure += 1
            self._http_last_failure_time = _time.time()

            # Handle firmware-specific errors
            from .firmware_capabilities import is_legacy_firmware_error

            if self._capabilities.get("is_legacy_device", False) and is_legacy_firmware_error(err):
                _LOGGER.debug("Legacy firmware error on %s: %s", self.client.host, err)
                # Return cached data instead of failing completely for legacy devices
                return self._get_cached_data_with_fallback()
            else:
                # If the update fails, engage the backoff strategy
                self._backoff.record_failure()

                # Determine the new interval from the backoff controller
                base_interval = NORMAL_POLL_INTERVAL
                new_interval = self._backoff.next_interval(default_seconds=base_interval)
                self.update_interval = new_interval

                # Enhanced escalation: debug → debug → warning → warning → error
                failures = self._backoff.consecutive_failures
                if failures <= 2:
                    log_level = logging.DEBUG  # Likely transient network issues
                elif failures <= 4:
                    log_level = logging.WARNING  # Device having connectivity problems
                else:
                    log_level = logging.ERROR  # Device likely offline/unavailable
                _LOGGER.log(
                    log_level,
                    "Update failed for %s (%d consecutive), backing off to %ss. Error: %s",
                    self.client.host,
                    self._backoff.consecutive_failures,
                    new_interval.total_seconds(),
                    err,
                )

                # Raise UpdateFailed to notify Home Assistant of the failure
                raise UpdateFailed(f"Failed to communicate with {self.client.host}: {err}") from err

    async def _fetch_multiroom_info(self) -> dict:
        """Enhanced multiroom info with firmware compatibility.

        According to the API guide:
        - getSlaveList only works on MASTER devices
        - Slave devices (group: "1") already know they're slaves
        - Only call getSlaveList when group: "0" to distinguish master from solo
        """
        # For legacy devices, use simplified approach
        if self._capabilities.get("is_legacy_device", False):
            generation = self._capabilities.get("audio_pro_generation", "original")
            _LOGGER.debug(
                "Using legacy multiroom approach for %s (generation: %s)",
                self.client.host,
                generation,
            )
            return await self._fetch_multiroom_info_legacy()

        # Enhanced approach for WiiM devices
        return await self._fetch_multiroom_info_enhanced()

    async def _fetch_multiroom_info_legacy(self) -> dict:
        """Simplified multiroom info for legacy Audio Pro units."""
        try:
            device_info = await self._fetch_device_info()
            group_field = device_info.get("group", "0")

            if group_field == "1":
                # Device reports being in a group (slave)
                return {"slaves": 0, "slave_list": [], "legacy_group": True}

            # For potential masters/solos (group: "0"), try getSlaveList if supported
            # This is critical for detecting masters - masters report group="0" but have slaves
            supports_getslavelist = self._capabilities.get("supports_getslavelist", True)
            if supports_getslavelist:
                try:
                    _LOGGER.debug(
                        "Legacy device %s checking slave status (group='%s')",
                        self.client.host,
                        group_field,
                    )
                    result = await self.client._request("/httpapi.asp?command=multiroom:getSlaveList")
                    _LOGGER.debug("Raw multiroom response for legacy %s: %s", self.client.host, result)
                    if result:
                        return result
                except WiiMError as err:
                    _LOGGER.debug(
                        "Legacy device %s: getSlaveList failed: %s (treating as solo)",
                        self.client.host,
                        err,
                    )

            # Fallback: Device reports being solo (no slaves detected)
            return {"slaves": 0, "slave_list": [], "legacy_group": False}

        except Exception as err:
            _LOGGER.debug("Legacy multiroom info failed: %s", err)
            return {"slaves": 0, "slave_list": [], "legacy_group": False}

    async def _fetch_multiroom_info_enhanced(self) -> dict:
        """Enhanced multiroom info for WiiM devices (original logic)."""
        try:
            # First check if this device is a slave - if so, no need for getSlaveList
            device_info = await self._fetch_device_info()
            group_field = device_info.get("group", "0")

            # If device is a slave (group: "1"), don't call getSlaveList
            if group_field == "1":
                _LOGGER.debug(
                    "Device %s is slave (group='1') - skipping getSlaveList",
                    self.client.host,
                )
                return {"slaves": 0, "slave_list": []}

            # For potential masters/solos (group: "0"), call getSlaveList to distinguish
            _LOGGER.debug(
                "Device %s checking slave status (group='%s')",
                self.client.host,
                group_field,
            )
            result = await self.client._request("/httpapi.asp?command=multiroom:getSlaveList")
            _LOGGER.debug("Raw multiroom response for %s: %s", self.client.host, result)
            return result or {}

        except WiiMError as err:
            _LOGGER.debug("[WiiM] %s: getSlaveList failed: %s", self.client.host, err)
            # Fallback to basic empty response
            return {"slaves": 0, "slave_list": []}

    async def _fetch_track_metadata(self, status: PlayerStatus) -> dict:  # noqa: D401
        """Thin wrapper delegating heavy logic to *coordinator_metadata* helper."""
        from . import coordinator_metadata as _meta

        return await _meta.fetch_track_metadata(self, status)

    def _enhance_metadata_with_artwork(self, metadata: dict, status: dict) -> dict:  # noqa: D401
        """Delegated to *coordinator_metadata* (legacy shim)."""
        from . import coordinator_metadata as _meta

        # Type ignore because helper expects coordinator instance first.
        return _meta._enhance_metadata_with_artwork(self, metadata, status)  # type: ignore[attr-defined]

    async def _extract_basic_metadata(self, status: dict) -> dict:  # noqa: D401
        """Delegated to *coordinator_metadata* (legacy shim)."""
        from . import coordinator_metadata as _meta

        return await _meta._extract_basic_metadata(self, status)

    async def _fetch_eq_info(self) -> dict:  # noqa: D401
        """Thin wrapper delegating heavy logic to *coordinator_eq* helper."""
        from . import coordinator_eq as _eq

        return await _eq.fetch_eq_info(self)

    def _should_update_device_info(self) -> bool:
        """Check if we should update device info (every 30-60 seconds)."""
        now = _time.time()
        if now - self._last_device_info_update >= self._device_info_interval:
            self._last_device_info_update = now  # type: ignore[assignment]
            return True
        return False

    def _track_changed(self, status: dict) -> bool:
        """Check if track changed (indicates need for metadata update)."""
        current_title = status.get("title")
        if not current_title:
            return False

        last_title = self._last_status.get("title")
        changed = current_title != last_title

        if changed:
            _LOGGER.debug(
                "[WiiM] %s: Track changed: %s -> %s",
                self.client.host,
                last_title,
                current_title,
            )

        self._last_status = status.copy()
        return changed

    async def _detect_role_from_status_and_slaves(
        self, status: PlayerStatus, multiroom: dict, device_info: DeviceInfo
    ) -> str:  # noqa: D401
        """Thin wrapper delegating heavy logic to *coordinator_role* helper."""
        from . import coordinator_role as _role

        return await _role.detect_role_from_status_and_slaves(self, status, multiroom, device_info)

    async def _update_speaker_object(self, data: dict) -> None:
        """Update Speaker object if it exists."""
        try:
            from .data import get_speaker_from_config_entry

            # In v2.0.0 simplified architecture, get speaker directly from config entry
            speaker = get_speaker_from_config_entry(self.hass, self.entry)

            if speaker:
                _LOGGER.debug(
                    "🎵 Found speaker %s, calling update_from_coordinator_data",
                    speaker.name,
                )
                # Build data structure for speaker update
                speaker.update_from_coordinator_data(data)
            else:
                _LOGGER.debug("🎵 No speaker found for config entry %s", self.entry.entry_id)

        except Exception as speaker_err:
            _LOGGER.debug(
                "[WiiM] %s: Speaker update failed: %s",
                self.client.host,
                speaker_err,
            )

    # User interaction methods
    def record_user_command(self, command_type: str) -> None:
        """Record user command and force immediate update."""
        _LOGGER.debug(
            "[WiiM] %s: User command '%s' - requesting immediate refresh",
            self.client.host,
            command_type,
        )
        # Force immediate refresh by setting short interval
        self.update_interval = timedelta(seconds=1)

    def record_command_failure(self, command_type: str, error: Exception) -> None:
        """Record command failure for immediate UI feedback."""
        import time

        self._last_command_failure = time.time()
        self._command_failure_count += 1

        # Track command statistics
        self._command_total += 1
        self._command_failure_total += 1
        self._command_last_failure_time = time.time()

        # Log for debugging (avoid noise from common issues)
        if self._command_failure_count <= 3:  # Only log first few failures
            _LOGGER.warning(
                "Command '%s' failed for %s: %s (failure count: %d)",
                command_type,
                self.client.host,
                error,
                self._command_failure_count,
            )

        # Force endpoint reprobe on severe connection failures
        if isinstance(error, aiohttp.ClientConnectorError | aiohttp.ServerDisconnectedError):
            self.force_endpoint_reprobe()

    def force_endpoint_reprobe(self) -> None:
        """Force the client to reprobe protocol/port on next request.

        Useful when connection is completely lost and we need to re-establish
        communication from scratch.
        """
        _LOGGER.info(
            "Forcing endpoint reprobe for %s due to connection failure",
            self.client.host,
        )
        self.client._endpoint = None  # Clear established endpoint

    def clear_command_failures(self) -> None:
        """Clear command failure state when a command succeeds."""
        if self._last_command_failure is not None:
            _LOGGER.info("Command succeeded for %s - clearing failure state", self.client.host)
            self._last_command_failure = None
            self._command_failure_count = 0

        # Track command success
        self._command_total += 1
        self._command_success += 1
        self._command_last_success_time = _time.time()

    def has_recent_command_failures(self) -> bool:
        """Check if there have been recent command failures."""
        if self._last_command_failure is None:
            return False

        time_since_failure = _time.time() - self._last_command_failure
        return time_since_failure < COMMAND_FAILURE_TIMEOUT

    # Group management methods (simplified from legacy)
    def get_current_role(self) -> str:
        """Get current device role."""
        if self.data and isinstance(self.data, dict):
            return self.data.get("role", "solo")
        return "solo"

    def get_cached_group_members(self) -> list[str]:
        """Get cached group member IPs."""
        if self.data and isinstance(self.data, dict):
            multiroom = self.data.get("multiroom", {})
            # Check both possible field names for slaves
            slaves_list = multiroom.get("slave_list", [])
            return [
                entry.get("ip") if isinstance(entry, dict) else str(entry)
                for entry in slaves_list
                if (isinstance(entry, dict) and entry.get("ip")) or (isinstance(entry, str) and entry)
            ]
        return []

    def get_cached_group_leader(self) -> str | None:
        """Get cached group leader IP."""
        status_model = self.data.get("status_model") if self.data else None
        if isinstance(status_model, PlayerStatus):
            status_dict = status_model.model_dump(exclude_none=True)
            return status_dict.get("master_ip")
        return None

    # Legacy compatibility properties
    @property
    def is_wiim_master(self) -> bool:
        """Check if device is a WiiM group master."""
        return self.get_current_role() == "master"

    @property
    def is_wiim_slave(self) -> bool:
        """Check if device is a WiiM group slave."""
        return self.get_current_role() == "slave"

    @property
    def wiim_group_members(self) -> set[str]:
        """Get WiiM group member IPs."""
        return set(self.get_cached_group_members())

    @property
    def friendly_name(self) -> str:
        """Return friendly name for the device."""
        return self.device_name

    async def _resolve_multiroom_source_and_media(self, status: PlayerStatus, metadata: dict, role: str) -> None:  # noqa: D401
        """Thin wrapper delegating heavy logic to *coordinator_multiroom* helper."""
        from . import coordinator_multiroom as _mr

        await _mr.resolve_multiroom_source_and_media(self, status, metadata, role)

    # ------------------------------------------------------------------
    # Dynamic EQ preset discovery --------------------------------------
    # ------------------------------------------------------------------

    async def _extend_eq_preset_map_once(self) -> None:  # noqa: D401
        """Thin wrapper delegating heavy logic to *coordinator_eq* helper."""
        from . import coordinator_eq as _eq

        await _eq.extend_eq_preset_map_once(self)

    def _get_cached_data_with_fallback(self) -> dict[str, Any]:
        """Return cached data with safe fallbacks for legacy devices.

        Returns:
            Dictionary with cached data or safe defaults
        """
        if not self.data:
            return {"role": "solo", "status_model": None, "device_model": None}

        # Ensure we have safe defaults for legacy devices
        data = self.data.copy()
        if "role" not in data:
            data["role"] = "solo"

        return data
