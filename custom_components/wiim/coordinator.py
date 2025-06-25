"""WiiM coordinator for fixed 5-second polling and device updates."""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import WiiMClient, WiiMError
from .coordinator_backoff import BackoffController
from .models import DeviceInfo, PlayerStatus

_LOGGER = logging.getLogger(__name__)

# Toggle to True if you really need full payloads in the log.
# When False (default) large dicts are truncated to a list of top-level keys
# which is usually enough for troubleshooting without spamming the log.
VERBOSE_DEBUG = False

# Number of consecutive failures after which we escalate to ERROR level
FAILURE_ERROR_THRESHOLD = 3  # Reduced from 10 - mark offline after 15 seconds instead of 50

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
    ) -> None:
        """Initialize the coordinator with adaptive polling."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"WiiM {client.host}",
            update_interval=timedelta(seconds=5),  # Initial interval, will be adaptive
        )
        self.client = client
        self.hass = hass
        self.entry = entry

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
        """Thin wrapper delegating polling logic to external module (see coordinator_polling)."""
        from . import coordinator_polling as _poll

        return await _poll.async_update_data(self)

    async def _fetch_multiroom_info(self) -> dict:
        """Get multiroom info with proper API usage per API guide.

        According to the API guide:
        - getSlaveList only works on MASTER devices
        - Slave devices (group: "1") already know they're slaves
        - Only call getSlaveList when group: "0" to distinguish master from solo
        """
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

    def _extract_basic_metadata(self, status: dict) -> dict:  # noqa: D401
        """Delegated to *coordinator_metadata* (legacy shim)."""
        from . import coordinator_metadata as _meta

        return _meta._extract_basic_metadata(self, status)

    async def _fetch_eq_info(self) -> dict:  # noqa: D401
        """Thin wrapper delegating heavy logic to *coordinator_eq* helper."""
        from . import coordinator_eq as _eq

        return await _eq.fetch_eq_info(self)

    def _should_update_device_info(self) -> bool:
        """Check if we should update device info (every 30-60 seconds)."""
        now = time.time()
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

    async def _update_speaker_object(self, status: dict) -> None:
        """Update Speaker object if it exists."""
        try:
            from .data import get_speaker_from_config_entry

            # In v2.0.0 simplified architecture, get speaker directly from config entry
            speaker = get_speaker_from_config_entry(self.hass, self.entry)

            # Build data structure for speaker update
            speaker.update_from_coordinator_data(status)

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
        """Record immediate command failure for user feedback.

        This provides instant feedback when user commands fail, separate from
        background polling failures. Device will appear temporarily unavailable
        until either a command succeeds or the failure timeout expires.
        """
        import time

        self._last_command_failure = time.time()
        self._command_failure_count += 1

        _LOGGER.warning(
            "Command '%s' failed for %s (failure #%d): %s - device temporarily unavailable",
            command_type,
            self.client.host,
            self._command_failure_count,
            error,
        )

    def clear_command_failures(self) -> None:
        """Clear command failure state when a command succeeds."""
        if self._last_command_failure is not None:
            _LOGGER.info("Command succeeded for %s - clearing failure state", self.client.host)
            self._last_command_failure = None
            self._command_failure_count = 0

    def has_recent_command_failures(self) -> bool:
        """Check if there have been recent command failures."""
        if self._last_command_failure is None:
            return False

        import time

        time_since_failure = time.time() - self._last_command_failure
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

    async def _resolve_multiroom_source_and_media(
        self, status: PlayerStatus, metadata: dict, role: str
    ) -> None:  # noqa: D401
        """Thin wrapper delegating heavy logic to *coordinator_multiroom* helper."""
        from . import coordinator_multiroom as _mr

        await _mr.resolve_multiroom_source_and_media(self, status, metadata, role)

    # ------------------------------------------------------------------
    # Dynamic EQ preset discovery --------------------------------------
    # ------------------------------------------------------------------

    async def _extend_eq_preset_map_once(self) -> None:
        """Fetch *additional* EQ presets from the device (EQGetList).

        Some WiiM firmwares expose extra presets (e.g. "Latin", "Small Speakers").
        We merge them into EQ_PRESET_MAP exactly once at start-up so they turn
        up in the sound-mode dropdown.  If the endpoint is missing we simply
        mark the attempt as done and move on silently.
        """

        # Guard – only run once per coordinator instance
        if self._eq_list_extended:
            return

        try:
            presets = await self.client.get_eq_presets()
            if not isinstance(presets, list):
                self._eq_list_extended = True
                return

            import re

            from .const import EQ_PRESET_MAP

            def _slug(label: str) -> str:
                slug = label.strip().lower().replace(" ", "_").replace("-", "_")
                # keep only ascii letters/numbers/underscore
                return re.sub(r"[^0-9a-z_]+", "", slug)

            added: list[str] = []
            for label in presets:
                if not isinstance(label, str):
                    continue
                key = _slug(label)
                if key and key not in EQ_PRESET_MAP:
                    EQ_PRESET_MAP[key] = label
                    added.append(label)

            if added:
                _LOGGER.info(
                    "[WiiM] %s: Added %d additional EQ presets from EQGetList: %s",
                    self.client.host,
                    len(added),
                    added,
                )
        except WiiMError as err:
            _LOGGER.debug("[WiiM] %s: EQGetList not supported (%s)", self.client.host, err)
        except Exception as err:  # pragma: no cover – safety
            _LOGGER.debug(
                "[WiiM] %s: Unexpected error during EQ list fetch: %s",
                self.client.host,
                err,
            )
        finally:
            # Always mark as attempted so we do not retry every poll
            self._eq_list_extended = True
