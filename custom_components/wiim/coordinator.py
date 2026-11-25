"""WiiM coordinator - minimal integration layer using pywiim."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Coroutine
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pywiim import Player, PollingStrategy, WiiMClient
from pywiim.exceptions import WiiMConnectionError, WiiMError, WiiMTimeoutError
from pywiim.upnp import UpnpClient, UpnpEventer

_LOGGER = logging.getLogger(__name__)

# Wait before subscribing to UPnP events again. After a failed attempt it
# doubles up to the maximum, so a speaker that never accepts is not asked often.
_UPNP_RETRY_INITIAL = 60.0
_UPNP_RETRY_MAX = 3600.0
_PYWIIM_MISC_LOGGER_NAME = "pywiim.api.misc"
_LED_READ_FALLBACK_MESSAGE = "LED indicator read not available for device (no API or read failed); assuming on"
_EXPECTED_PYWIIM_LOG_FILTER_INSTALLED = False


class _ExpectedPywiimFallbackFilter(logging.Filter):
    """Suppress pywiim fallback warnings that are expected in HA polling."""

    _wiim_expected_pywiim_fallback_filter = True

    def filter(self, record: logging.LogRecord) -> bool:
        """Return False for known noisy pywiim fallback records."""
        return record.getMessage() != _LED_READ_FALLBACK_MESSAGE


def _install_expected_pywiim_log_filter() -> None:
    """Install log filtering for pywiim fallbacks that HA should not surface."""
    global _EXPECTED_PYWIIM_LOG_FILTER_INSTALLED

    if _EXPECTED_PYWIIM_LOG_FILTER_INSTALLED:
        return

    logger = logging.getLogger(_PYWIIM_MISC_LOGGER_NAME)
    if not any(getattr(log_filter, "_wiim_expected_pywiim_fallback_filter", False) for log_filter in logger.filters):
        logger.addFilter(_ExpectedPywiimFallbackFilter())
    _EXPECTED_PYWIIM_LOG_FILTER_INSTALLED = True


_UNREACHABLE_ERROR_MARKERS = (
    "device unreachable",
    "connection failed on all attempted protocols",
    "cannot connect to host",
    "connect call failed",
    "connection refused",
    "connection reset",
    "network is unreachable",
    "name or service not known",
)


def _is_expected_unreachable_error(err: Exception) -> bool:
    """Return True when error indicates expected offline/unreachable device."""
    if isinstance(err, (WiiMConnectionError, WiiMTimeoutError)):
        return True
    last_error = getattr(err, "last_error", None)
    if last_error is not None and last_error is not err and _is_expected_unreachable_error(last_error):
        return True
    # Powered-off devices often surface as WiiMRequestError after retries
    # ("Request failed after 2 attempts: Cannot connect to host"), not as
    # WiiMConnectionError. Treat those connect failures as unreachable too.
    err_text = str(err).lower()
    return any(marker in err_text for marker in _UNREACHABLE_ERROR_MARKERS)


def _compact_wiim_error(err: Exception) -> str:
    """Return compact error text to avoid log spam."""
    if _is_expected_unreachable_error(err):
        return "device unreachable"
    return str(err)


class WiiMCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """WiiM coordinator - minimal glue between pywiim and Home Assistant."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        entry=None,
        capabilities: dict[str, Any] | None = None,
        port: int | None = None,
        protocol: str | None = None,
        timeout: int = 10,
    ) -> None:
        """Initialize the coordinator."""
        _install_expected_pywiim_log_filter()
        super().__init__(
            hass,
            _LOGGER,
            name=f"WiiM {host}",
            update_interval=timedelta(seconds=5),  # Default, will adapt
        )
        self.hass = hass
        self.entry = entry
        self._capabilities = capabilities or {}

        # Get HA's shared aiohttp session (for connection pooling)
        session = async_get_clientsession(hass)

        # Create pywiim client with HA's session
        # Only pass port/protocol if we have a cached endpoint (optimized pattern)
        # Otherwise, let pywiim probe automatically (simplest pattern)
        client_kwargs = {
            "host": host,
            "timeout": timeout,
            "session": session,
            "capabilities": capabilities,
        }
        if port is not None and protocol is not None:
            # We have a cached endpoint - use it for faster startup
            client_kwargs["port"] = port
            client_kwargs["protocol"] = protocol
        # If port/protocol not provided, pywiim will probe automatically

        client = WiiMClient(**client_kwargs)

        # Wrap client in Player (recommended for HA - pywiim manages all state)
        # pywiim 2.1.70+ handles player linking internally via its player registry

        # We need to include player_finder and all_players_finder to enable cross-coordinator group linking.
        # In pywiim's player/groupsops.py the "Case 2" for device is master but we don't have a group object
        # short-circuits if there isn't a player_finder callback.
        # all_players_finder is also included as a final fallback in case the UUID lookup doesn't work for
        # some reason.

        self.player = Player(
            client,
            on_state_changed=self._on_player_state_changed,
            player_finder=self._player_finder,
            all_players_finder=self._all_players_finder,
        )

        # Use pywiim's PollingStrategy to determine when to poll
        self._polling_strategy = PollingStrategy(self._capabilities) if self._capabilities else PollingStrategy({})
        self._refresh_in_progress = False

        # UPnP events are an addition to polling. See async_start_upnp_events().
        self._upnp_events_enabled = False
        self._upnp_eventer: UpnpEventer | None = None
        self._upnp_task: asyncio.Task[None] | None = None
        self._upnp_retry_delay = _UPNP_RETRY_INITIAL
        self._upnp_retry_at = 0.0

    def update_capabilities(self, capabilities: dict[str, Any]) -> None:
        """Apply a refreshed capabilities mapping (e.g. after firmware change).

        Config entry data is updated separately in ``__init__``; this keeps the
        coordinator, adaptive polling, and the pywiim client flags in sync.
        """
        merged = dict(capabilities)
        self._capabilities.clear()
        self._capabilities.update(merged)
        client_caps = getattr(self.player.client, "_capabilities", None)
        if client_caps is not None and client_caps is not self._capabilities:
            client_caps.clear()
            client_caps.update(merged)
        self._polling_strategy = PollingStrategy(self._capabilities) if self._capabilities else PollingStrategy({})

    def _player_finder(self, host_or_uuid: str) -> Player | None:
        """Find a Player object across all coordinators by host IP or UUID.

        Called by pywiim when it needs to resolve a slave's IP/UUID (from
        getSlaveList) to an actual Player object for group linking.
        """
        from .data import get_all_coordinators

        for coordinator in get_all_coordinators(self.hass):
            if coordinator is self:
                continue
            try:
                p = coordinator.player
                if getattr(p, "host", None) == host_or_uuid:
                    return p
                if getattr(p, "uuid", None) == host_or_uuid:
                    return p
            except Exception as err:
                _LOGGER.debug("Error in player_finder for %s: %s", host_or_uuid, _compact_wiim_error(err))
        return None

    def _all_players_finder(self) -> list[Player]:
        """Return all Player objects from every registered coordinator.

        Called by pywiim to infer slave role if e.g. a device is still reporting
        that it's solo even though it appears in another device's getSlaveList.
        """
        from .data import get_all_coordinators

        players = []
        for c in get_all_coordinators(self.hass):
            try:
                players.append(c.player)
            except Exception as err:
                _LOGGER.debug("Error in all_players_finder: %s", _compact_wiim_error(err))
        return players

    @callback
    def _on_player_state_changed(self) -> None:
        """Callback when pywiim Player detects state changes.

        Directly notifies listeners to update immediately without going through
        the coordinator's data update mechanism (which has throttling/debouncing).
        The callback fires AFTER pywiim has fully updated the Player object's
        properties (including metadata), so entities can read fresh data directly
        from self.player.
        """
        # Update coordinator's cached data reference (but don't trigger update flow)
        # This ensures self.data is always in sync with self.player
        self.data = {"player": self.player}

        # Directly notify all entities to refresh their state from the player
        # This bypasses DataUpdateCoordinator's throttling for immediate UI updates,
        # except while the coordinator is already performing a timed refresh. In
        # that case DataUpdateCoordinator publishes the completed refresh once.
        if self._refresh_in_progress:
            return
        self.async_update_listeners()

    # ===== UPnP events =====

    @callback
    def async_start_upnp_events(self) -> None:
        """Subscribe to UPnP events once the Player has a UPnP client.

        Events report play state, volume and track changes without waiting for
        the next poll. Polling is unchanged, so a speaker that rejects the
        subscription, or a Home Assistant address the speaker cannot reach,
        leaves the integration working as it does without events.
        """
        self._upnp_events_enabled = True
        self._async_update_upnp_events(reachable=self.last_update_success)

    async def async_stop_upnp_events(self) -> None:
        """Unsubscribe from UPnP events and close the callback listener."""
        self._upnp_events_enabled = False
        if (task := self._upnp_task) is not None:
            await asyncio.wait([task])
        if (eventer := self._upnp_eventer) is not None:
            self._upnp_eventer = None
            await eventer.async_unsubscribe()

    @property
    def upnp_event_state(self) -> dict[str, Any]:
        """Return the UPnP event subscription state for diagnostics."""
        if (eventer := self._upnp_eventer) is None:
            return {"subscribed": False}
        stats = eventer.statistics
        return {
            "subscribed": True,
            "event_count": stats["event_count"],
            "seconds_since_last_event": stats["time_since_last_event"],
        }

    @callback
    def _async_update_upnp_events(self, reachable: bool) -> None:
        """Bring the UPnP subscription in line with the latest poll result."""
        if self._upnp_task is not None:
            # A subscribe or unsubscribe is still running. The next poll re-checks.
            return

        if (eventer := self._upnp_eventer) is not None:
            if reachable:
                return
            # async-upnp-client drops a subscription it cannot renew while the
            # speaker is away and does not retry. Release this one now and
            # subscribe again once the speaker answers polls. The wait keeps a
            # speaker with a poor connection from being re-subscribed every poll.
            self._upnp_eventer = None
            self._upnp_retry_at = time.monotonic() + _UPNP_RETRY_INITIAL
            self._async_run_upnp_task(eventer.async_unsubscribe(), "unsubscribe")
            return

        if not (reachable and self._upnp_events_enabled) or time.monotonic() < self._upnp_retry_at:
            return
        # pywiim's Player creates its UPnP client in the background and retries
        # on its own, so the client can appear on any poll.
        upnp_client = getattr(self.player, "_upnp_client", None)
        if isinstance(upnp_client, UpnpClient):
            self._async_run_upnp_task(self._async_subscribe_upnp(upnp_client), "subscribe")

    @callback
    def _async_run_upnp_task(self, coro: Coroutine[Any, Any, None], action: str) -> None:
        """Run one subscribe or unsubscribe at a time, off the polling path."""
        task = self.hass.async_create_background_task(coro, f"wiim_upnp_{action}_{self.player.host}")
        self._upnp_task = task
        task.add_done_callback(self._async_upnp_task_done)

    @callback
    def _async_upnp_task_done(self, task: asyncio.Task[None]) -> None:
        """Allow the next subscribe or unsubscribe."""
        if self._upnp_task is task:
            self._upnp_task = None

    async def _async_subscribe_upnp(self, upnp_client: UpnpClient) -> None:
        """Subscribe to the speaker's UPnP events through the Player's client."""
        host = self.player.host
        eventer = UpnpEventer(
            upnp_client,
            self.player,
            self.player.uuid or host,
            state_updated_callback=self._on_player_state_changed,
        )
        try:
            # pywiim listens on the local address that routes to the speaker, as
            # Home Assistant's DLNA integration does. network.async_get_source_ip
            # only returns addresses of enabled adapters, so on a host with several
            # adapters it can name one the speaker cannot reach.
            await eventer.start()
        except Exception as err:  # noqa: BLE001 - events are optional and polling continues
            _LOGGER.debug(
                "UPnP event subscription failed for %s, polling continues; next attempt in %.0fs: %s",
                host,
                self._upnp_retry_delay,
                err,
            )
            self._upnp_retry_at = time.monotonic() + self._upnp_retry_delay
            self._upnp_retry_delay = min(self._upnp_retry_delay * 2, _UPNP_RETRY_MAX)
            await eventer.async_unsubscribe()
            return

        self._upnp_retry_delay = _UPNP_RETRY_INITIAL
        self._upnp_eventer = eventer
        _LOGGER.debug("Subscribed to UPnP events for %s", host)

    async def _async_update_data(self) -> dict[str, Any]:
        """Update coordinator data - polls device following pywiim's PollingStrategy."""
        try:
            # Call player.refresh() to poll device and update cached state
            # PollingStrategy determines WHEN to poll (adaptive intervals)
            self._refresh_in_progress = True
            try:
                await self.player.refresh()
            finally:
                self._refresh_in_progress = False

            # Update polling interval using pywiim's PollingStrategy
            role = self.player.role
            is_playing = self.player.is_playing  # pywiim v2.1.37+ provides bool directly
            optimal_interval = self._polling_strategy.get_optimal_interval(role, is_playing)
            current_interval = self.update_interval.total_seconds() if self.update_interval else 5.0
            if current_interval != optimal_interval:
                self.update_interval = timedelta(seconds=optimal_interval)

            # Return Player object - it has everything (state, metadata, group info, etc.)
            if is_playing and _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug(
                    "Poll result for %s: state=%s, pos=%s, dur=%s, title='%s'",
                    self.player.host,
                    self.player.play_state,
                    self.player.media_position,
                    self.player.media_duration,
                    self.player.media_title,
                )

            self._async_update_upnp_events(reachable=True)

            result = {"player": self.player}
            return result

        except WiiMError as err:
            if _is_expected_unreachable_error(err):
                self._async_update_upnp_events(reachable=False)
                _LOGGER.debug("Update failed for %s: %s", self.player.host, _compact_wiim_error(err))
                # Powered-off / unreachable devices must go unavailable so automations
                # that wait on availability (e.g. smart-plug scripts) can proceed.
                raise UpdateFailed(
                    f"Failed to communicate with {self.player.host}: {_compact_wiim_error(err)}"
                ) from err
            _LOGGER.warning("Update failed for %s: %s", self.player.host, _compact_wiim_error(err))
            # Return cached Player object for non-connectivity errors (parse blips, etc.)
            if self.data:
                return self.data
            raise UpdateFailed(f"Failed to communicate with {self.player.host}: {_compact_wiim_error(err)}") from err
