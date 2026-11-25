"""UPnP event subscription lifecycle: started, failed, speaker offline and stopped."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pywiim import Player
from pywiim.exceptions import WiiMConnectionError
from pywiim.upnp import UpnpClient, UpnpEventer

from custom_components.wiim import async_setup_entry, async_unload_entry
from custom_components.wiim import coordinator as coordinator_module
from custom_components.wiim.const import DOMAIN
from custom_components.wiim.coordinator import WiiMCoordinator
from custom_components.wiim.version import REQUIRED_PYWIIM_VERSION
from tests.const import MOCK_CONFIG, MOCK_DEVICE_DATA

HOST = "192.168.1.100"


def _eventer(start_error: Exception | None = None) -> MagicMock:
    """Return a stand-in for pywiim's UpnpEventer."""
    eventer = MagicMock(spec=UpnpEventer)
    eventer.start = AsyncMock(side_effect=start_error)
    eventer.async_unsubscribe = AsyncMock()
    eventer.statistics = {"event_count": 4, "time_since_last_event": 1.5}
    return eventer


@pytest.fixture
def player() -> MagicMock:
    """A Player that already has the UPnP client pywiim creates on refresh."""
    player = MagicMock(spec=Player)
    player.host = HOST
    player.uuid = MOCK_DEVICE_DATA["uuid"]
    player.refresh = AsyncMock()
    player.role = "solo"
    player.is_playing = False
    player._upnp_client = MagicMock(spec=UpnpClient)
    return player


@pytest.fixture
def coordinator(hass: HomeAssistant, player: MagicMock) -> WiiMCoordinator:
    """A coordinator around the mocked Player."""
    with (
        patch("custom_components.wiim.coordinator.Player", return_value=player),
        patch("custom_components.wiim.coordinator.async_get_clientsession"),
    ):
        return WiiMCoordinator(hass, host=HOST)


@pytest.fixture
def eventers() -> list[MagicMock]:
    """Eventers handed out in order; the last one is reused when the list runs out."""
    return [_eventer()]


@pytest.fixture(autouse=True)
def eventer_cls(eventers: list[MagicMock]):
    """Replace UpnpEventer so no test opens a listener or contacts a speaker."""
    created = iter(eventers)

    def _create(*_args, **_kwargs) -> MagicMock:
        return next(created, eventers[-1])

    with patch("custom_components.wiim.coordinator.UpnpEventer", side_effect=_create) as cls:
        yield cls


async def _settle(hass: HomeAssistant) -> None:
    """Let a background subscribe or unsubscribe finish."""
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_start_subscribes_and_events_reach_listeners(
    hass: HomeAssistant, coordinator, player, eventers, eventer_cls
) -> None:
    """Starting subscribes through the Player's client and events update entities."""
    coordinator.async_start_upnp_events()
    await _settle(hass)

    # No callback address is passed: pywiim uses the one that routes to the speaker.
    eventers[0].start.assert_awaited_once_with()
    args, kwargs = eventer_cls.call_args
    assert args == (player._upnp_client, player, MOCK_DEVICE_DATA["uuid"])
    assert coordinator.upnp_event_state == {
        "subscribed": True,
        "event_count": 4,
        "seconds_since_last_event": 1.5,
    }

    listener = MagicMock()
    remove_listener = coordinator.async_add_listener(listener)
    try:
        kwargs["state_updated_callback"]()
    finally:
        remove_listener()
    listener.assert_called_once_with()

    # A working subscription is left alone by later polls.
    await coordinator._async_update_data()
    await _settle(hass)
    eventer_cls.assert_called_once()


async def test_waits_for_the_player_to_create_its_upnp_client(
    hass: HomeAssistant, coordinator, player, eventers
) -> None:
    """pywiim creates the client in the background, so it may appear on a later poll."""
    upnp_client = player._upnp_client
    player._upnp_client = None

    coordinator.async_start_upnp_events()
    await coordinator._async_update_data()
    await _settle(hass)
    assert coordinator.upnp_event_state == {"subscribed": False}

    player._upnp_client = upnp_client
    await coordinator._async_update_data()
    await _settle(hass)
    assert coordinator.upnp_event_state["subscribed"] is True


@pytest.mark.parametrize("eventers", [[_eventer(start_error=OSError("refused")), _eventer()]])
async def test_failed_subscription_keeps_polling_and_retries_later(
    hass: HomeAssistant, coordinator, player, eventers, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A speaker that refuses the subscription is polled as before and asked again later."""
    now = [1000.0]
    monkeypatch.setattr(coordinator_module, "time", SimpleNamespace(monotonic=lambda: now[0]))

    coordinator.async_start_upnp_events()
    await _settle(hass)

    assert coordinator.upnp_event_state == {"subscribed": False}
    # The listener opened for the attempt is closed again.
    eventers[0].async_unsubscribe.assert_awaited_once()

    assert await coordinator._async_update_data() == {"player": player}
    await _settle(hass)
    eventers[1].start.assert_not_awaited()

    now[0] += coordinator_module._UPNP_RETRY_INITIAL
    await coordinator._async_update_data()
    await _settle(hass)
    eventers[1].start.assert_awaited_once()
    assert coordinator.upnp_event_state["subscribed"] is True


@pytest.mark.parametrize("eventers", [[_eventer(), _eventer()]])
async def test_unreachable_speaker_releases_subscription_until_it_returns(
    hass: HomeAssistant, coordinator, player, eventers, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Going offline drops the subscription; it is made again once the speaker is back."""
    now = [1000.0]
    monkeypatch.setattr(coordinator_module, "time", SimpleNamespace(monotonic=lambda: now[0]))
    coordinator.async_start_upnp_events()
    await _settle(hass)

    player.refresh.side_effect = WiiMConnectionError("Connection lost")
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    await _settle(hass)
    eventers[0].async_unsubscribe.assert_awaited_once()
    assert coordinator.upnp_event_state == {"subscribed": False}

    # A speaker that drops in and out is not re-subscribed on every poll.
    player.refresh.side_effect = None
    await coordinator._async_update_data()
    await _settle(hass)
    eventers[1].start.assert_not_awaited()

    now[0] += coordinator_module._UPNP_RETRY_INITIAL
    await coordinator._async_update_data()
    await _settle(hass)
    eventers[1].start.assert_awaited_once()
    assert coordinator.upnp_event_state["subscribed"] is True


async def test_stop_unsubscribes_and_stays_stopped(hass: HomeAssistant, coordinator, eventers, eventer_cls) -> None:
    """Stopping releases the subscription and later polls do not bring it back."""
    coordinator.async_start_upnp_events()
    await _settle(hass)

    await coordinator.async_stop_upnp_events()
    eventers[0].async_unsubscribe.assert_awaited_once()
    assert coordinator.upnp_event_state == {"subscribed": False}

    await coordinator._async_update_data()
    await _settle(hass)
    eventer_cls.assert_called_once()


async def test_stop_while_subscribing_releases_the_new_subscription(
    hass: HomeAssistant, coordinator, eventers, eventer_cls
) -> None:
    """A stop that arrives mid-subscribe waits for it, then unsubscribes."""
    speaker_answered = asyncio.Event()

    async def _slow_start(**_kwargs) -> None:
        await speaker_answered.wait()

    eventers[0].start.side_effect = _slow_start
    coordinator.async_start_upnp_events()

    # A poll during the attempt does not start a second one.
    await coordinator._async_update_data()
    eventer_cls.assert_called_once()

    stop = hass.async_create_task(coordinator.async_stop_upnp_events())
    await asyncio.sleep(0)
    eventers[0].async_unsubscribe.assert_not_awaited()
    speaker_answered.set()
    await stop

    eventers[0].async_unsubscribe.assert_awaited_once()
    assert coordinator.upnp_event_state == {"subscribed": False}


async def test_unload_entry_stops_upnp_events(hass: HomeAssistant) -> None:
    """Unloading the entry releases the speaker's subscription."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_DEVICE_DATA["uuid"])
    entry.add_to_hass(hass)
    coordinator = MagicMock()
    coordinator.async_stop_upnp_events = AsyncMock()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"coordinator": coordinator, "entry": entry}

    with patch.object(hass.config_entries, "async_unload_platforms", AsyncMock(return_value=True)):
        assert await async_unload_entry(hass, entry)

    coordinator.async_stop_upnp_events.assert_awaited_once()


async def test_setup_entry_starts_events_and_ha_stop_releases_them(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Entry setup starts the subscription; stopping Home Assistant releases it."""
    capabilities = {"device_type": "WiiM_Pro_with_gc4a", "vendor": "wiim", "supports_firmware_install": True}
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Master Bedroom",
        data={"host": HOST, "endpoint": f"https://{HOST}:443"},
        unique_id=MOCK_DEVICE_DATA["uuid"],
    )
    entry.add_to_hass(hass)

    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.async_stop_upnp_events = AsyncMock()
    coordinator.player.name = "Master Bedroom"
    coordinator.player.firmware = None
    coordinator.player.client.capabilities = capabilities

    monkeypatch.setattr(
        "custom_components.wiim.async_ensure_pywiim_version", AsyncMock(return_value=REQUIRED_PYWIIM_VERSION)
    )
    monkeypatch.setattr("custom_components.wiim.is_pywiim_version_compatible", lambda _version: True)
    detecting_client = MagicMock()
    detecting_client._detect_capabilities = AsyncMock(return_value=capabilities)
    monkeypatch.setattr("custom_components.wiim.WiiMClient", MagicMock(return_value=detecting_client))
    monkeypatch.setattr("custom_components.wiim.WiiMCoordinator", MagicMock(return_value=coordinator))
    monkeypatch.setattr("custom_components.wiim._register_ha_device", AsyncMock())
    monkeypatch.setattr(hass.config_entries, "async_forward_entry_setups", AsyncMock())

    assert await async_setup_entry(hass, entry)
    coordinator.async_start_upnp_events.assert_called_once_with()
    coordinator.async_stop_upnp_events.assert_not_awaited()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    coordinator.async_stop_upnp_events.assert_awaited_once()
