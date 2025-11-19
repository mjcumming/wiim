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

# Optional imports for UPnP (may not be available in all pywiim versions)
try:
    from pywiim import UpnpClient

    UPNP_AVAILABLE = True
except ImportError:
    UPNP_AVAILABLE = False
    UpnpClient = None  # type: ignore[assignment, misc]

_LOGGER = logging.getLogger(__name__)


class WiiMCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """WiiM coordinator - minimal glue between pywiim and Home Assistant."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        entry=None,
        capabilities: dict[str, Any] | None = None,
        port: int = 443,
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
        self._last_group_info: dict[str, Any] | None = None

        # Get HA's shared aiohttp session (for connection pooling)
        session = async_get_clientsession(hass)

        # Create pywiim client with HA's session
        client = WiiMClient(
            host=host,
            port=port,
            timeout=timeout,
            session=session,
            capabilities=capabilities,
        )

        # Wrap client in Player (recommended for HA - pywiim manages all state)
        # Set up callback so Player state changes trigger coordinator updates
        self.player = Player(
            client,
            on_state_changed=self._on_player_state_changed,
        )

        # Use pywiim's PollingStrategy to determine when to poll
        self._polling_strategy = PollingStrategy(self._capabilities) if self._capabilities else PollingStrategy({})

        # UPnP client for events and queue management (optional, set up later)
        self.upnp_client: UpnpClient | None = None
        self._upnp_setup_attempted = False

    @callback
    def _on_player_state_changed(self) -> None:
        """Callback when pywiim Player detects state changes.

        Uses async_set_updated_data() to properly update coordinator data
        and notify all entities. The callback now fires AFTER pywiim has
        fully updated the Player object's properties (including metadata).
        """
        # Update coordinator data to trigger entity updates
        # Create a new dict to ensure Home Assistant detects the change
        # (even though Player object reference is the same, its internal state has changed)
        if self.data:
            # Create a new dict with the updated Player object to force state change detection
            new_data = {
                "player": self.player,
                "group_info": self._last_group_info,
            }
            self.async_set_updated_data(new_data)
        else:
            # If no data yet, just notify listeners (will be populated on next refresh)
            self.async_update_listeners()

    async def _async_update_data(self) -> dict[str, Any]:
        """Update coordinator data - pywiim Player manages all state."""
        try:
            # pywiim 0.65 manages all state - we call refresh() based on polling strategy
            await self.player.refresh()

            # Update polling interval using pywiim's PollingStrategy
            role = self.player.role
            play_state = self.player.play_state or ""
            is_playing = play_state.lower() in ("play", "playing", "load")
            optimal_interval = self._polling_strategy.get_optimal_interval(role, is_playing)
            current_interval = self.update_interval.total_seconds() if self.update_interval else 5.0
            if current_interval != optimal_interval:
                self.update_interval = timedelta(seconds=optimal_interval)

            group_info = await self._async_fetch_group_info()
            self._last_group_info = group_info

            # Return only the Player object plus cached group info - entities read all state directly from it
            # pywiim handles all playback state management internally (UPnP events, polling, etc.)
            return {
                "player": self.player,
                "group_info": group_info,
            }

        except WiiMError as err:
            _LOGGER.warning("Update failed for %s: %s", self.player.host, err)
            # Return Player object even on error (may have cached state)
            if self.data:
                return self.data
            raise UpdateFailed(f"Failed to communicate with {self.player.host}: {err}") from err

    async def _async_fetch_group_info(self) -> dict[str, Any] | None:
        """Fetch latest group info from pywiim (role, master/slave hosts)."""
        try:
            group_info = await self.player.client.get_device_group_info()
        except WiiMError as err:
            _LOGGER.debug("Failed to fetch group info for %s: %s", self.player.host, err)
            return self._last_group_info
        except Exception as err:
            _LOGGER.debug("Unexpected error fetching group info for %s: %s", self.player.host, err)
            return self._last_group_info

        return {
            "role": group_info.role,
            "master_host": group_info.master_host,
            "master_uuid": group_info.master_uuid,
            "slave_hosts": list(group_info.slave_hosts or []),
            "slave_count": group_info.slave_count,
        }

    async def async_setup_upnp(self) -> None:
        """Set up UPnP client and Player for queue management and events."""
        if self._upnp_setup_attempted:
            return

        self._upnp_setup_attempted = True

        if not UPNP_AVAILABLE:
            _LOGGER.debug("UPnP support not available in pywiim version (queue management disabled)")
            self.upnp_client = None
            return

        try:
            # Create UPnP client
            description_url = f"http://{self.player.host}:49152/description.xml"
            self.upnp_client = await UpnpClient.create(  # type: ignore[misc]
                self.player.host,
                description_url,
            )

            # Recreate Player with UPnP client for queue management and events
            # Get the client from the existing Player to recreate it
            player_client = getattr(self.player, "_client", None) or getattr(self.player, "client", None)
            if player_client:
                self.player = Player(
                    player_client,
                    upnp_client=self.upnp_client,
                    on_state_changed=self._on_player_state_changed,
                )
            else:
                # Fallback: create new client with HA's session
                session = async_get_clientsession(self.hass)
                client = WiiMClient(
                    host=self.player.host,
                    port=getattr(self.player, "port", 443),
                    timeout=getattr(self.player, "timeout", 10),
                    session=session,
                    capabilities=self._capabilities,
                )
                self.player = Player(
                    client,
                    upnp_client=self.upnp_client,
                    on_state_changed=self._on_player_state_changed,
                )

            _LOGGER.info(
                "UPnP client initialized and Player updated for %s (queue management and events enabled)",
                self.player.host,
            )
        except Exception as err:
            _LOGGER.debug(
                "Failed to set up UPnP client for %s (queue management will be unavailable): %s",
                self.player.host,
                err,
            )
            # UPnP is optional - don't fail if it's not available
            self.upnp_client = None
