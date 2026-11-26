"""Unit tests for the WiiM Voice Remote device and its entities."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT, EntityCategory
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from pywiim import REMOTE_VOLUME_STEPS, BleRemoteState
from pywiim.exceptions import WiiMError

from custom_components.wiim.binary_sensor import WiiMRemoteConnectedBinarySensor
from custom_components.wiim.binary_sensor import async_setup_entry as binary_sensor_setup
from custom_components.wiim.const import DOMAIN
from custom_components.wiim.diagnostics import async_get_device_diagnostics
from custom_components.wiim.entity import (
    REMOTE_DEFAULT_NAME,
    async_add_remote_entities,
    build_remote_device_info,
    remote_paired,
)
from custom_components.wiim.select import WiiMRemoteVolumeStepSelect
from custom_components.wiim.select import async_setup_entry as select_setup
from custom_components.wiim.sensor import WiiMRemoteBatterySensor, WiiMRemoteSignalSensor
from custom_components.wiim.sensor import async_setup_entry as sensor_setup

FAKE_MAC = "AA:BB:CC:DD:EE:01"
COMPONENT_DIR = Path(__file__).parent.parent.parent / "custom_components" / "wiim"


def remote_state(
    *,
    paired: bool | None = True,
    connected: bool = True,
    name: str | None = "WiiM Voice Remote",
    mac: str | None = FAKE_MAC,
    firmware: str | None = "0054",
    battery: int | None = 87,
    rssi: int | None = -52,
) -> BleRemoteState:
    """Build a real BleRemoteState with a fake MAC."""
    return BleRemoteState(
        paired=paired,
        connected=connected,
        name=name,
        mac=mac,
        firmware=firmware,
        battery=battery if connected else None,
        rssi=rssi if connected else None,
    )


@pytest.fixture
def config_entry():
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.unique_id = "test-uuid"
    entry.title = "Test WiiM"
    entry.data = {"host": "192.168.1.100"}
    entry.options = {}
    return entry


@pytest.fixture
def coordinator():
    coordinator = MagicMock()
    coordinator.last_update_success = True
    player = MagicMock()
    player.host = "192.168.1.100"
    player.name = "Test WiiM"
    player.supports_ble_remote = True
    player.client.capabilities = {"supports_ble_remote": True}
    player.ble_remote = remote_state()
    player.remote_volume_step = 3
    player.set_remote_volume_step = AsyncMock()
    coordinator.player = player
    return coordinator


# ---------------------------------------------------------------- device info


def test_remote_device_info(coordinator, config_entry):
    info = build_remote_device_info(coordinator.player, config_entry)

    assert info["identifiers"] == {(DOMAIN, "test-uuid_remote")}
    assert info["via_device"] == (DOMAIN, "test-uuid")
    assert info["name"] == "WiiM Voice Remote"
    assert info["model"] == "WiiM Voice Remote"
    assert info["manufacturer"] == "WiiM"
    assert info["sw_version"] == "54"
    assert info["connections"] == {(CONNECTION_BLUETOOTH, FAKE_MAC)}


@pytest.mark.parametrize(
    ("raw", "shown"),
    [("0054", "54"), ("54", "54"), ("0000", "0"), ("0", "0"), ("1.2.3", "1.2.3"), ("v0054", "v0054"), ("", None)],
)
def test_remote_firmware_is_shown_without_leading_zeros(coordinator, config_entry, raw, shown):
    """Like the WiiM Home app: 0054 shows as 54, all zeros as 0, anything non-numeric as it is."""
    coordinator.player.ble_remote = remote_state(firmware=raw)

    assert build_remote_device_info(coordinator.player, config_entry).get("sw_version") == shown


def test_remote_device_info_without_name_mac_or_firmware(coordinator, config_entry):
    coordinator.player.ble_remote = remote_state(name=None, mac=None, firmware=None)

    info = build_remote_device_info(coordinator.player, config_entry)

    assert info["name"] == REMOTE_DEFAULT_NAME
    assert info["sw_version"] is None
    assert "connections" not in info or not info["connections"]


def test_remote_device_info_survives_missing_state(coordinator, config_entry):
    """A failed read leaves ble_remote None; the device values fall back, never raise."""
    coordinator.player.ble_remote = None

    info = build_remote_device_info(coordinator.player, config_entry)

    assert info["identifiers"] == {(DOMAIN, "test-uuid_remote")}
    assert info["name"] == REMOTE_DEFAULT_NAME


def test_remote_device_info_uses_host_when_entry_has_no_unique_id(coordinator, config_entry):
    config_entry.unique_id = None

    info = build_remote_device_info(coordinator.player, config_entry)

    assert info["identifiers"] == {(DOMAIN, "192.168.1.100_remote")}
    assert info["via_device"] == (DOMAIN, "192.168.1.100")


def test_remote_device_registers_under_the_speaker(hass, coordinator):
    """The real device registry accepts the remote's values and links it to the speaker."""
    from homeassistant.helpers import device_registry as dr
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(domain=DOMAIN, unique_id="test-uuid", title="Test WiiM")
    entry.add_to_hass(hass)
    registry = dr.async_get(hass)
    speaker = registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "test-uuid")}, name="Test WiiM"
    )

    remote = registry.async_get_or_create(
        config_entry_id=entry.entry_id, **build_remote_device_info(coordinator.player, entry)
    )

    assert remote.id != speaker.id
    assert remote.via_device_id == speaker.id
    assert remote.name == "WiiM Voice Remote"
    assert remote.manufacturer == "WiiM"
    assert remote.sw_version == "54"
    assert remote.model == "WiiM Voice Remote"
    assert remote.identifiers == {(DOMAIN, "test-uuid_remote")}
    assert {value for kind, value in remote.connections if kind == CONNECTION_BLUETOOTH} == {FAKE_MAC}


# ------------------------------------------------------------- remote_paired


@pytest.mark.parametrize(
    ("supported", "state", "expected"),
    [
        (True, remote_state(), True),
        (True, remote_state(connected=False), True),
        (True, remote_state(paired=False, name=None, mac=None, firmware=None), False),
        (True, remote_state(paired=None), False),
        (True, None, False),
        (False, remote_state(), False),
    ],
)
def test_remote_paired(coordinator, supported, state, expected):
    coordinator.player.supports_ble_remote = supported
    coordinator.player.ble_remote = state

    assert remote_paired(coordinator.player) is expected


# ------------------------------------------------------------- entity helper


def test_add_remote_entities_adds_when_paired(coordinator, config_entry):
    add = MagicMock()
    factory = MagicMock(return_value=["a", "b"])

    async_add_remote_entities(coordinator, config_entry, add, factory)

    add.assert_called_once_with(["a", "b"])
    coordinator.async_add_listener.assert_not_called()


def test_add_remote_entities_waits_for_pairing(coordinator, config_entry):
    coordinator.player.ble_remote = remote_state(paired=False, name=None, mac=None, firmware=None)
    add = MagicMock()
    factory = MagicMock(return_value=["a"])

    async_add_remote_entities(coordinator, config_entry, add, factory)

    add.assert_not_called()
    listener = coordinator.async_add_listener.call_args.args[0]
    unsubscribe = config_entry.async_on_unload.call_args.args[0]

    listener()  # still not paired
    add.assert_not_called()

    coordinator.player.ble_remote = remote_state()
    listener()
    listener()  # a second update must not add the entities again
    add.assert_called_once_with(["a"])
    coordinator.async_add_listener.return_value.assert_called_once()
    unsubscribe()  # unloading after the listener is gone must not remove it twice
    coordinator.async_add_listener.return_value.assert_called_once()


def test_add_remote_entities_ignores_unsupported_speaker(coordinator, config_entry):
    coordinator.player.supports_ble_remote = False
    coordinator.player.client.capabilities = {"supports_ble_remote": False}
    add = MagicMock()

    async_add_remote_entities(coordinator, config_entry, add, MagicMock())

    add.assert_not_called()
    coordinator.async_add_listener.assert_not_called()


def test_add_remote_entities_waits_out_an_inconclusive_probe(coordinator, config_entry):
    """ADR 025: a transient probe error leaves supports_ble_remote None; a later refresh sets it True."""
    coordinator.player.supports_ble_remote = False  # the property is True only for True
    coordinator.player.client.capabilities = {"supports_ble_remote": None}
    coordinator.player.ble_remote = None
    add = MagicMock()

    async_add_remote_entities(coordinator, config_entry, add, lambda: ["a"])
    add.assert_not_called()
    listener = coordinator.async_add_listener.call_args.args[0]

    coordinator.player.supports_ble_remote = True
    coordinator.player.client.capabilities = {"supports_ble_remote": True}
    coordinator.player.ble_remote = remote_state()
    listener()

    add.assert_called_once_with(["a"])


# ----------------------------------------------------------------- entities


def test_select_options_are_the_app_labels(coordinator, config_entry):
    entity = WiiMRemoteVolumeStepSelect(coordinator, config_entry)

    assert entity.options == [
        "Fine Adjustment",
        "Small Step",
        "Medium Step",
        "Large Step",
        "Quick Adjustment",
    ]
    assert entity.options == list(REMOTE_VOLUME_STEPS.values())
    assert entity.entity_category is EntityCategory.CONFIG
    assert entity.unique_id == "test-uuid_remote_volume_step"
    assert entity.current_option == "Medium Step"


@pytest.mark.parametrize("step", [None, 9])
def test_select_unknown_step_has_no_option(coordinator, config_entry, step):
    coordinator.player.remote_volume_step = step

    assert WiiMRemoteVolumeStepSelect(coordinator, config_entry).current_option is None


@pytest.mark.asyncio
@pytest.mark.parametrize(("label", "step"), [(label, step) for step, label in REMOTE_VOLUME_STEPS.items()])
async def test_select_option_sets_step(coordinator, config_entry, label, step):
    entity = WiiMRemoteVolumeStepSelect(coordinator, config_entry)

    await entity.async_select_option(label)

    coordinator.player.set_remote_volume_step.assert_awaited_once_with(step)


@pytest.mark.asyncio
async def test_select_unknown_option_is_rejected(coordinator, config_entry):
    entity = WiiMRemoteVolumeStepSelect(coordinator, config_entry)

    with pytest.raises(HomeAssistantError):
        await entity.async_select_option("Giant Leap")

    coordinator.player.set_remote_volume_step.assert_not_awaited()


@pytest.mark.asyncio
async def test_select_device_error_becomes_home_assistant_error(coordinator, config_entry):
    coordinator.player.set_remote_volume_step.side_effect = WiiMError("read-back differs")
    entity = WiiMRemoteVolumeStepSelect(coordinator, config_entry)

    with pytest.raises(HomeAssistantError):
        await entity.async_select_option("Small Step")


def test_battery_sensor(coordinator, config_entry):
    entity = WiiMRemoteBatterySensor(coordinator, config_entry)

    assert entity.unique_id == "test-uuid_remote_battery"
    assert entity.device_class is SensorDeviceClass.BATTERY
    assert entity.native_unit_of_measurement == PERCENTAGE
    assert entity.state_class is SensorStateClass.MEASUREMENT
    assert entity.native_value == 87


def test_signal_sensor(coordinator, config_entry):
    entity = WiiMRemoteSignalSensor(coordinator, config_entry)

    assert entity.unique_id == "test-uuid_remote_rssi"
    assert entity.device_class is SensorDeviceClass.SIGNAL_STRENGTH
    assert entity.native_unit_of_measurement == SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    assert entity.state_class is SensorStateClass.MEASUREMENT
    assert entity.entity_category is EntityCategory.DIAGNOSTIC
    assert entity.entity_registry_enabled_default is False
    assert entity.native_value == -52


def test_connected_binary_sensor(coordinator, config_entry):
    entity = WiiMRemoteConnectedBinarySensor(coordinator, config_entry)

    assert entity.unique_id == "test-uuid_remote_connected"
    assert entity.device_class is BinarySensorDeviceClass.CONNECTIVITY
    assert entity.is_on is True

    coordinator.player.ble_remote = remote_state(connected=False)
    assert entity.is_on is False


def test_remote_entities_share_one_device(coordinator, config_entry):
    entities = [
        WiiMRemoteVolumeStepSelect(coordinator, config_entry),
        WiiMRemoteBatterySensor(coordinator, config_entry),
        WiiMRemoteSignalSensor(coordinator, config_entry),
        WiiMRemoteConnectedBinarySensor(coordinator, config_entry),
    ]

    for entity in entities:
        info = entity.device_info
        assert info["identifiers"] == {(DOMAIN, "test-uuid_remote")}
        assert info["via_device"] == (DOMAIN, "test-uuid")


# -------------------------------------------------------------- availability


def all_entities(coordinator, config_entry):
    return {
        "select": WiiMRemoteVolumeStepSelect(coordinator, config_entry),
        "battery": WiiMRemoteBatterySensor(coordinator, config_entry),
        "rssi": WiiMRemoteSignalSensor(coordinator, config_entry),
        "connected": WiiMRemoteConnectedBinarySensor(coordinator, config_entry),
    }


def test_all_available_when_connected(coordinator, config_entry):
    assert all(entity.available for entity in all_entities(coordinator, config_entry).values())


def test_disconnected_remote(coordinator, config_entry):
    """Not connected: battery, signal and volume step are unavailable; Connected reports off."""
    coordinator.player.ble_remote = remote_state(connected=False)
    entities = all_entities(coordinator, config_entry)

    assert not entities["select"].available
    assert not entities["battery"].available
    assert not entities["rssi"].available
    assert entities["connected"].available
    assert entities["connected"].is_on is False


@pytest.mark.parametrize(
    "state",
    [
        remote_state(paired=False, name=None, mac=None, firmware=None),
        remote_state(paired=None),
        None,
    ],
)
def test_unpaired_or_unread_remote_makes_everything_unavailable(coordinator, config_entry, state):
    coordinator.player.ble_remote = state

    assert not any(entity.available for entity in all_entities(coordinator, config_entry).values())


def test_speaker_offline_makes_everything_unavailable(coordinator, config_entry):
    coordinator.last_update_success = False

    assert not any(entity.available for entity in all_entities(coordinator, config_entry).values())


def test_unsupported_speaker_makes_everything_unavailable(coordinator, config_entry):
    coordinator.player.supports_ble_remote = False

    assert not any(entity.available for entity in all_entities(coordinator, config_entry).values())


# ------------------------------------------------------------ platform setup


def setup_hass(coordinator, config_entry):
    hass = MagicMock()
    hass.data = {DOMAIN: {config_entry.entry_id: {"coordinator": coordinator}}}
    return hass


def quiet_speaker(coordinator):
    """Make the mocked speaker look like one with no other optional features."""
    player = coordinator.player
    player.supports_audio_output = False
    player.supports_eq = False
    player.supports_digital_filter = False
    player.supports_standby_timeout = False
    player.supports_output_channel = False
    player.room_correction_profiles = []
    player.client.capabilities = {"supports_peq": False}
    coordinator._metadata_supported = False


@pytest.mark.asyncio
async def test_select_platform_creates_remote_select_when_paired(coordinator, config_entry):
    quiet_speaker(coordinator)
    add = MagicMock()

    await select_setup(setup_hass(coordinator, config_entry), config_entry, add)

    created = [e for call in add.call_args_list for e in call.args[0]]
    assert [type(e) for e in created] == [WiiMRemoteVolumeStepSelect]


@pytest.mark.asyncio
async def test_select_platform_skips_remote_when_unsupported(coordinator, config_entry):
    quiet_speaker(coordinator)
    coordinator.player.supports_ble_remote = False
    coordinator.player.client.capabilities = {"supports_ble_remote": False}
    coordinator.player.ble_remote = None
    add = MagicMock()

    await select_setup(setup_hass(coordinator, config_entry), config_entry, add)

    assert not [e for call in add.call_args_list for e in call.args[0] if isinstance(e, WiiMRemoteVolumeStepSelect)]
    coordinator.async_add_listener.assert_not_called()


@pytest.mark.asyncio
async def test_sensor_platform_creates_remote_sensors_when_paired(coordinator, config_entry):
    quiet_speaker(coordinator)
    add = MagicMock()

    await sensor_setup(setup_hass(coordinator, config_entry), config_entry, add)

    created = [e for call in add.call_args_list for e in call.args[0]]
    kinds = {type(e) for e in created}
    assert {WiiMRemoteBatterySensor, WiiMRemoteSignalSensor} <= kinds


@pytest.mark.asyncio
async def test_binary_sensor_platform_creates_remote_connected(coordinator, config_entry):
    add = MagicMock()

    await binary_sensor_setup(setup_hass(coordinator, config_entry), config_entry, add)

    created = [e for call in add.call_args_list for e in call.args[0]]
    assert [type(e) for e in created] == [WiiMRemoteConnectedBinarySensor]


@pytest.mark.asyncio
async def test_remote_entities_appear_after_a_later_pairing(coordinator, config_entry):
    coordinator.player.ble_remote = remote_state(paired=False, name=None, mac=None, firmware=None)
    add = MagicMock()

    await binary_sensor_setup(setup_hass(coordinator, config_entry), config_entry, add)
    created = [e for call in add.call_args_list for e in call.args[0]]
    assert created == []

    coordinator.player.ble_remote = remote_state()
    coordinator.async_add_listener.call_args.args[0]()

    created = [e for call in add.call_args_list for e in call.args[0]]
    assert [type(e) for e in created] == [WiiMRemoteConnectedBinarySensor]


# --------------------------------------------------------- enabled platforms


@pytest.mark.parametrize(("flag", "expected"), [(True, True), (None, True), (False, False)])
def test_binary_sensor_platform_enabled_by_capability(hass, config_entry, flag, expected):
    """True or None (inconclusive probe) loads the platform; False and a missing key do not."""
    from homeassistant.const import Platform

    from custom_components.wiim import get_enabled_platforms

    config_entry.data = {}

    platforms = get_enabled_platforms(hass, config_entry, {"supports_ble_remote": flag})

    assert (Platform.BINARY_SENSOR in platforms) is expected
    assert Platform.BINARY_SENSOR not in get_enabled_platforms(hass, config_entry, {})


# --------------------------------------------------------------- diagnostics


def diagnostics_player(state):
    player = MagicMock()
    player.supports_ble_remote = True
    player.ble_remote = state
    player.remote_volume_step = 4
    player.device_info = None
    player.client.capabilities = {}
    return player


async def diagnostics_for(hass, config_entry, player, *, remote_device=False):
    coordinator = MagicMock()
    coordinator.player = player
    coordinator.last_update_success = True
    hass.data = {DOMAIN: {config_entry.entry_id: {"coordinator": coordinator}}}
    device = MagicMock()
    device.id = "device-id"
    device.identifiers = {(DOMAIN, "test-uuid_remote" if remote_device else "test-uuid")}
    return await async_get_device_diagnostics(hass, config_entry, device)


@pytest.mark.asyncio
async def test_remote_device_diagnostics_are_only_the_remote(hass, config_entry):
    player = diagnostics_player(remote_state())
    player.name = "Living Room"

    result = await diagnostics_for(hass, config_entry, player, remote_device=True)

    assert result == {
        "ble_remote": {
            "paired": True,
            "connected": True,
            "name": "WiiM Voice Remote",
            "mac": "XX:XX:XX:XX:XX:XX",
            "firmware": "0054",
            "battery": 87,
            "rssi": -52,
            "volume_step": 4,
        },
        "speaker_name": "Living Room",
    }
    assert FAKE_MAC not in json.dumps(result)


@pytest.mark.asyncio
async def test_speaker_device_diagnostics_stay_complete(hass, config_entry):
    result = await diagnostics_for(hass, config_entry, diagnostics_player(remote_state()))

    assert {"device_info", "capabilities", "playback_state", "ble_remote"} <= set(result)
    assert "speaker_name" not in result


@pytest.mark.asyncio
async def test_diagnostics_ble_remote_section_masks_mac(hass, config_entry):
    result = await diagnostics_for(hass, config_entry, diagnostics_player(remote_state()))

    assert result["ble_remote"] == {
        "paired": True,
        "connected": True,
        "name": "WiiM Voice Remote",
        "mac": "XX:XX:XX:XX:XX:XX",
        "firmware": "0054",
        "battery": 87,
        "rssi": -52,
        "volume_step": 4,
    }
    assert FAKE_MAC not in json.dumps(result, default=str)
    assert FAKE_MAC.replace(":", "") not in json.dumps(result, default=str)


@pytest.mark.asyncio
async def test_diagnostics_ble_remote_when_not_paired(hass, config_entry):
    state = remote_state(paired=False, name=None, mac=None, firmware=None)

    result = await diagnostics_for(hass, config_entry, diagnostics_player(state))

    assert result["ble_remote"]["paired"] is False
    assert result["ble_remote"]["mac"] is None


@pytest.mark.asyncio
async def test_diagnostics_ble_remote_unsupported_or_unread(hass, config_entry):
    player = diagnostics_player(None)
    player.supports_ble_remote = False
    assert (await diagnostics_for(hass, config_entry, player))["ble_remote"] == {"supported": False}

    player = diagnostics_player(None)
    assert (await diagnostics_for(hass, config_entry, player))["ble_remote"] == {"supported": True, "paired": None}


@pytest.mark.asyncio
async def test_diagnostics_ble_remote_error_does_not_break_diagnostics(hass, config_entry):
    player = diagnostics_player(remote_state())
    type(player).ble_remote = property(lambda self: (_ for _ in ()).throw(RuntimeError("boom")))

    result = await diagnostics_for(hass, config_entry, player)

    assert result["ble_remote"] == {"error": "RuntimeError"}
    assert "device_info" in result


# -------------------------------------------------------------- translations


@pytest.mark.parametrize("file", ["strings.json", "translations/en.json"])
def test_remote_entity_names_are_translated(file):
    entity = json.loads((COMPONENT_DIR / file).read_text(encoding="utf-8"))["entity"]

    assert entity["select"]["remote_volume_step"]["name"] == "Volume adjustment step"
    assert entity["sensor"]["remote_battery"]["name"] == "Battery"
    assert entity["sensor"]["remote_rssi"]["name"] == "Signal strength"
    assert entity["binary_sensor"]["remote_connected"]["name"] == "Connected"


REMOTE_ENTITY_CLASSES = {
    "select": WiiMRemoteVolumeStepSelect,
    "sensor": (WiiMRemoteBatterySensor, WiiMRemoteSignalSensor),
    "binary_sensor": WiiMRemoteConnectedBinarySensor,
}


@pytest.mark.parametrize("file", ["strings.json", "translations/en.json"])
def test_every_remote_translation_key_exists(coordinator, config_entry, file):
    """Each remote entity's translation_key has a name under its platform in strings.json and en.json."""
    entity = json.loads((COMPONENT_DIR / file).read_text(encoding="utf-8"))["entity"]

    for platform, classes in REMOTE_ENTITY_CLASSES.items():
        for cls in classes if isinstance(classes, tuple) else (classes,):
            key = cls(coordinator, config_entry).translation_key
            assert key, f"{cls.__name__} has no translation_key"
            assert entity[platform][key]["name"], f"{file}: entity.{platform}.{key}.name is missing"


@pytest.mark.asyncio
async def test_entity_names_resolve_on_a_real_platform(hass, coordinator, config_entry):
    """Registered through a real entity platform, each entity gets its own name, not the device name."""
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry, MockEntityPlatform

    entry = MockConfigEntry(domain=DOMAIN, unique_id="test-uuid", title="Test WiiM")
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    for platform, classes in REMOTE_ENTITY_CLASSES.items():
        mock_platform = MockEntityPlatform(hass, domain=platform, platform_name=DOMAIN)
        mock_platform.config_entry = entry
        await mock_platform.async_load_translations()
        await mock_platform.async_add_entities(
            [cls(coordinator, config_entry) for cls in (classes if isinstance(classes, tuple) else (classes,))]
        )

    names = {entry.unique_id: entry.original_name for entry in registry.entities.values()}
    assert names == {
        "test-uuid_remote_volume_step": "Volume adjustment step",
        "test-uuid_remote_battery": "Battery",
        "test-uuid_remote_rssi": "Signal strength",
        "test-uuid_remote_connected": "Connected",
    }


# After "Forget" in the WiiM Home app (WiiM Pro Plus, Linkplay.4.8.833841) the speaker answers
# status "notconnect", not "scanning", with no name and an all-zero MAC.
GETBLEHIDSTATUS_AFTER_FORGET = {
    "status": "notconnect",
    "error": 0,
    "name": "",
    "mac": "00:00:00:00:00:00",
    "battery": 100,
    "ver": "",
    "rssi": 0,
    "powerstatus": 0,
    "doubleclickdisable": 0,
}


def test_remote_forgotten_in_the_app_is_unavailable(coordinator, config_entry):
    from pywiim.api.ble_remote import build_ble_remote_state, parse_ble_remote_identity

    state = build_ble_remote_state(parse_ble_remote_identity(GETBLEHIDSTATUS_AFTER_FORGET))
    assert state is not None
    assert (state.paired, state.connected, state.battery, state.rssi) == (False, False, None, None)
    coordinator.player.ble_remote = state

    assert remote_paired(coordinator.player) is False
    assert not any(entity.available for entity in all_entities(coordinator, config_entry).values())


def test_entities_use_the_translation_keys(coordinator, config_entry):
    entities = all_entities(coordinator, config_entry)

    assert entities["select"].translation_key == "remote_volume_step"
    assert entities["battery"].translation_key == "remote_battery"
    assert entities["rssi"].translation_key == "remote_rssi"
    assert entities["connected"].translation_key == "remote_connected"
