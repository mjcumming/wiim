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

from .data import find_coordinator_by_ip, find_coordinator_by_uuid

_LOGGER = logging.getLogger(__name__)


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
        # Provide player_finder for automatic group linking (supports IP and UUID)
        self.player = Player(
            client,
            on_state_changed=self._on_player_state_changed,
            player_finder=self._find_player,
        )

        # Use pywiim's PollingStrategy to determine when to poll
        self._polling_strategy = PollingStrategy(self._capabilities) if self._capabilities else PollingStrategy({})

    def _find_player(self, identifier: str):
        """Find Player object by IP or UUID for automatic group linking.

        This callback allows pywiim to automatically link Player objects when
        groups are detected, enabling group.all_players to be populated.

        WiFi Direct multiroom groups may report slaves by UUID instead of IP,
        so we try both lookup methods. (pywiim v2.1.60 provides slave_uuids)
        """
        # First try IP-based lookup (most common case)
        coordinator = find_coordinator_by_ip(self.hass, identifier)
        if coordinator and coordinator.player:
            return coordinator.player

        # Fallback: try UUID-based lookup (for WiFi Direct multiroom)
        # Normalize UUID by removing "uuid:" prefix if present
        normalized_uuid = identifier.replace("uuid:", "") if identifier else None
        if normalized_uuid:
            coordinator = find_coordinator_by_uuid(self.hass, normalized_uuid)
            if coordinator and coordinator.player:
                return coordinator.player

        return None

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
            _LOGGER.warning("Update failed for %s: %s", self.player.host, err)
            # Return cached Player object even on error
            if self.data:
                return self.data
            raise UpdateFailed(f"Failed to communicate with {self.player.host}: {err}") from err
