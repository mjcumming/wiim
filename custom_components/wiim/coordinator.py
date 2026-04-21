"""WiiM coordinator - minimal integration layer using pywiim."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pywiim import Player, PollingStrategy, WiiMClient
from pywiim.exceptions import WiiMError

_LOGGER = logging.getLogger(__name__)


def _is_expected_unreachable_error(err: Exception) -> bool:
    """Return True when error indicates expected offline/unreachable device."""
    err_text = str(err).lower()
    return "device unreachable" in err_text or "connection failed on all attempted protocols" in err_text


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
                _LOGGER.warning("Error in player_finder for %s: %s", host_or_uuid, _compact_wiim_error(err))
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
                _LOGGER.warning("Error in all_players_finder: %s", _compact_wiim_error(err))
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
        # This bypasses DataUpdateCoordinator's throttling for immediate UI updates
        self.async_update_listeners()

    async def _async_update_data(self) -> dict[str, Any]:
        """Update coordinator data - polls device following pywiim's PollingStrategy."""
        try:
            # Call player.refresh() to poll device and update cached state
            # PollingStrategy determines WHEN to poll (adaptive intervals)
            await self.player.refresh()

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

            result = {"player": self.player}
            # Notify listeners after successful update
            self.async_update_listeners()
            return result

        except WiiMError as err:
            _LOGGER.warning("Update failed for %s: %s", self.player.host, _compact_wiim_error(err))
            # Return cached Player object even on error
            if self.data:
                return self.data
            raise UpdateFailed(f"Failed to communicate with {self.player.host}: {_compact_wiim_error(err)}") from err
