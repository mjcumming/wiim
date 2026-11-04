"""Unit tests for WiiM Select Entity - output mode and EQ preset selection."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError
from pywiim.exceptions import WiiMConnectionError, WiiMError, WiiMTimeoutError

from custom_components.wiim.select import (
    WiiMChannelSelect,
    WiiMEQPresetSelect,
    WiiMOutputModeSelect,
    WiiMPEQPresetSelect,
    WiiMRoomFitSelect,
)


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.unique_id = "test-uuid"
    entry.title = "Test WiiM"
    entry.data = {"host": "192.168.1.100"}
    entry.options = {}
    return entry


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.data = {"player": MagicMock()}
    coordinator.last_update_success = True
    coordinator.async_request_refresh = AsyncMock()
    coordinator.player = MagicMock()
    coordinator.player.available_outputs = ["Analog", "Optical", "BT: Speaker"]
    coordinator.player.audio_output_mode = "Analog"
    coordinator.player.is_bluetooth_output_active = False
    coordinator.player.bluetooth_output_devices = []
    coordinator.player.audio = MagicMock()
    coordinator.player.audio.select_output = AsyncMock(return_value=True)
    coordinator.player.name = "Test WiiM"
    coordinator.player.supports_eq = False
    coordinator.player.client.capabilities = {"supports_peq": False}
    coordinator.player.peq_presets = []
    coordinator.player.peq_preset = None
    coordinator.player.peq_enabled = None
    coordinator.player.initialize_peq_presets = AsyncMock()
    coordinator.player.set_peq_preset = AsyncMock()
    coordinator.player.disable_peq = AsyncMock()
    coordinator.player.supports_digital_filter = False
    coordinator.player.digital_filter_types = []
    coordinator.player.digital_filter = None
    coordinator.player.set_digital_filter = AsyncMock()
    coordinator.player.room_correction_profiles = []
    coordinator.player.room_correction = None
    coordinator.player.set_room_correction = AsyncMock()
    coordinator.player.supports_output_channel = False
    coordinator.player.output_channel = None
    coordinator.player.set_output_channel = AsyncMock()
    coordinator.player.eq_preset = "Flat"
    coordinator.player.eq_is_custom = False
    coordinator.player.eq_presets = ["Off", "Flat", "Rock", "Jazz"]
    coordinator.player.set_eq_preset = AsyncMock()
    return coordinator


@pytest.mark.asyncio
async def test_peq_off_and_unknown_states(mock_coordinator, mock_config_entry):
    player = mock_coordinator.player
    player.peq_presets = ["Night"]
    entity = WiiMPEQPresetSelect(mock_coordinator, mock_config_entry)
    assert entity.options == ["Off", "Night"]
    assert entity.current_option is None
    player.peq_enabled = False
    assert entity.current_option == "Off"
    player.peq_enabled = True
    player.peq_preset = "Night"
    assert entity.current_option == "Night"
    await entity.async_select_option("Off")
    player.disable_peq.assert_awaited_once()


@pytest.mark.asyncio
async def test_active_peq_uses_saved_preset_spelling(mock_coordinator, mock_config_entry):
    """A case variant stays selectable using the saved device name."""
    player = mock_coordinator.player
    player.peq_presets = ["Night"]
    player.peq_enabled = True
    player.peq_preset = "night"
    entity = WiiMPEQPresetSelect(mock_coordinator, mock_config_entry)

    assert entity.options == ["Off", "Night"]
    assert entity.current_option == "Night"
    await entity.async_select_option("Night")
    player.set_peq_preset.assert_awaited_once_with("Night")


@pytest.mark.asyncio
async def test_saved_peq_named_off_keeps_its_existing_option(mock_coordinator, mock_config_entry):
    player = mock_coordinator.player
    player.peq_presets = ["Off", "Night"]
    player.peq_enabled = False
    entity = WiiMPEQPresetSelect(mock_coordinator, mock_config_entry)
    assert entity.options == ["Off (disable)", "Off", "Night"]
    assert entity.current_option == "Off (disable)"
    await entity.async_select_option("Off")
    player.set_peq_preset.assert_awaited_once_with("Off")
    await entity.async_select_option("Off (disable)")
    player.disable_peq.assert_awaited_once()


@pytest.mark.asyncio
async def test_peq_disable_label_does_not_hide_saved_presets(mock_coordinator, mock_config_entry):
    player = mock_coordinator.player
    player.peq_presets = ["Off", "Off (disable)", "off (disable 2)"]
    player.peq_enabled = False
    entity = WiiMPEQPresetSelect(mock_coordinator, mock_config_entry)
    assert entity.options == ["Off (disable 3)", *player.peq_presets]
    assert entity.current_option == "Off (disable 3)"
    await entity.async_select_option("Off (disable)")
    player.set_peq_preset.assert_awaited_once_with("Off (disable)")
    await entity.async_select_option("Off (disable 3)")
    player.disable_peq.assert_awaited_once()


@pytest.mark.asyncio
async def test_active_unlisted_peq_named_off_is_distinct_from_disable(mock_coordinator, mock_config_entry):
    player = mock_coordinator.player
    player.peq_enabled = True
    player.peq_preset = "Off"
    entity = WiiMPEQPresetSelect(mock_coordinator, mock_config_entry)
    assert entity.options == ["Off (disable)", "Off"]
    assert entity.current_option == "Off"
    await entity.async_select_option("Off")
    player.set_peq_preset.assert_not_awaited()
    await entity.async_select_option("Off (disable)")
    player.disable_peq.assert_awaited_once()


@pytest.mark.asyncio
async def test_unsaved_custom_graphic_state_is_visible_but_not_loadable(mock_coordinator, mock_config_entry):
    player = mock_coordinator.player
    player.eq_presets = ["Off", "Flat", "Custom"]
    player.eq_preset = "Custom"
    player.eq_is_custom = True
    entity = WiiMEQPresetSelect(mock_coordinator, mock_config_entry)
    assert entity.current_option == "Custom"
    await entity.async_select_option("Custom")
    player.set_eq_preset.assert_not_awaited()
    player.eq_preset = None
    assert entity.current_option is None


@pytest.mark.asyncio
async def test_observed_graphic_name_is_visible_without_claiming_it_is_loadable(mock_coordinator, mock_config_entry):
    player = mock_coordinator.player
    player.eq_presets = []
    player.eq_preset = "Spoken Word"
    entity = WiiMEQPresetSelect(mock_coordinator, mock_config_entry)
    assert entity.options == ["Off", "Spoken Word"]
    assert entity.current_option == "Spoken Word"
    await entity.async_select_option("Spoken Word")
    player.set_eq_preset.assert_not_awaited()


@pytest.mark.asyncio
async def test_a10_reported_list_reaches_home_assistant_selector(mock_coordinator, mock_config_entry):
    """The #187 array travels through legacy validation, Player cache and HA."""
    from pywiim.api.base import ApiResponse
    from pywiim.client import WiiMClient
    from pywiim.models import PlayerStatus
    from pywiim.player import Player

    names = [
        "Flat",
        "Acoustic",
        "Bass Booster",
        "Bass Reducer",
        "Classical",
        "Dance",
        "Deep",
        "Electronic",
        "Game",
        "Hip-Hop",
        "Jazz",
        "Latin",
        "Loudness",
        "Lounge",
        "Movie",
        "Piano",
        "Pop",
        "R&B",
        "Rock",
        "Small Speakers",
        "Spoken Word",
        "Treble Booster",
        "Treble Reducer",
        "Vocal Booster",
    ]
    client = WiiMClient(
        "192.0.2.1", capabilities={"is_legacy_device": True, "supports_eq": True, "supports_subwoofer": False}
    )
    client._ensure_session = AsyncMock()

    async def response(endpoint, *_args, **_kwargs):
        if "EQGetList" in endpoint:
            return ApiResponse(parsed=names, raw=None)
        if "EQGetBand" in endpoint:
            return ApiResponse(parsed={"source_name": "wifi", "EQStat": "On", "Name": "Bass Booster"}, raw=None)
        return ApiResponse(parsed={}, raw=None)

    client._request_with_protocol_fallback = AsyncMock(side_effect=response)
    player = Player(client)
    player._status_model = PlayerStatus(source="wifi", eq_preset="0")
    await player._state_mgr._refresh_periodic_data(True, player._status_model, False)
    mock_coordinator.player = player
    entity = WiiMEQPresetSelect(mock_coordinator, mock_config_entry)
    assert entity.options == ["Off", *names]
    assert entity.current_option == "Bass Booster"


@pytest.mark.asyncio
async def test_periodic_eq_preset_refresh_updates_both_selectors(mock_coordinator, mock_config_entry):
    """New names from the library's scheduled refresh appear in HA options."""
    from pywiim.api.peq import PEQSettings
    from pywiim.client import WiiMClient
    from pywiim.models import PlayerStatus
    from pywiim.player import Player

    client = WiiMClient("192.0.2.1", capabilities={"supports_eq": True, "supports_peq": True})
    client.get_eq_presets = AsyncMock(side_effect=[["Flat"], ["Flat", "Movie"]])
    client.get_peq_preset_list = AsyncMock(
        side_effect=[{"custom": ["Night"], "preset": []}, {"custom": ["Desk"], "preset": []}]
    )
    client.get_eq = AsyncMock(return_value={"EQStat": "Off", "Name": "Flat"})
    client.get_peq_bands = AsyncMock(return_value=PEQSettings(enabled=False))
    client.get_room_correction = AsyncMock(side_effect=WiiMError("not available"))
    player = Player(client)
    player._status_model = PlayerStatus(source="wifi")
    await player._state_mgr._refresh_periodic_data(True, player._status_model, False)
    mock_coordinator.player = player
    graphic = WiiMEQPresetSelect(mock_coordinator, mock_config_entry)
    parametric = WiiMPEQPresetSelect(mock_coordinator, mock_config_entry)
    assert graphic.options == ["Off", "Flat"]
    assert parametric.options == ["Off", "Night"]

    player._last_eq_presets_check -= 901
    player._last_peq_presets_check -= 901
    await player._state_mgr._refresh_periodic_data(False, player._status_model, False)

    assert graphic.options == ["Off", "Flat", "Movie"]
    assert parametric.options == ["Off", "Desk"]


@pytest.mark.asyncio
async def test_saved_peq_profiles_reconcile_both_selectors(mock_coordinator, mock_config_entry):
    """Exercise the observed WiiM PEQ and stale graphic readbacks end to end."""
    import json
    from urllib.parse import unquote

    from pywiim.api.base import ApiResponse
    from pywiim.api.constants import GEQ_PLUGIN_URI
    from pywiim.api.peq import GEQ_BAND_NAMES, PEQBand
    from pywiim.client import WiiMClient
    from pywiim.models import PlayerStatus
    from pywiim.player import Player

    names = ["Test PEQ A", "Test-PEQ-B", "Test_PEQ_C"]
    state = {"peq": None, "graphic": True, "graphic_custom": False, "bands": []}
    client = WiiMClient("192.0.2.1", capabilities={"supports_eq": True, "supports_peq": True})

    async def response(endpoint, *_args, **_kwargs):
        if "EQv2GetList:" in endpoint:
            return ApiResponse(parsed={"status": "OK", "custom": names, "preset": []}, raw=None)
        if "EQv2SourceLoad:" in endpoint:
            payload = json.loads(unquote(endpoint.split("EQv2SourceLoad:", 1)[1]))
            state.update(peq=payload["Name"], graphic=False)
            return ApiResponse(parsed={"status": "OK", "EQStat": "On", "Name": state["peq"]}, raw=None)
        if "EQSetLV2SourceBand:" in endpoint:
            payload = json.loads(unquote(endpoint.split("EQSetLV2SourceBand:", 1)[1]))
            assert payload["pluginURI"] == GEQ_PLUGIN_URI
            state.update(peq=None, graphic=True, graphic_custom=True, bands=payload["EQBand"])
            return ApiResponse(parsed={"status": "OK"}, raw=None)
        if "EQGetLV2Band" in endpoint or "EQGetLV2SourceBand" in endpoint:
            if GEQ_PLUGIN_URI in unquote(endpoint):
                return ApiResponse(
                    parsed={
                        "status": "OK",
                        "source_name": "wifi",
                        "EQStat": "On" if state["graphic"] else "Off",
                        "Name": "" if state["graphic_custom"] else "Acoustic",
                        "pluginURI": GEQ_PLUGIN_URI,
                        "channelMode": "Stereo",
                        "EQBand": state["bands"],
                    },
                    raw=None,
                )
            return ApiResponse(
                parsed={
                    "status": "OK",
                    "source_name": "wifi",
                    "EQStat": "On" if state["peq"] else "Off",
                    "Name": state["peq"] or "",
                    "pluginURI": "http://moddevices.com/plugins/caps/EqNp",
                    "channelMode": "Stereo",
                    "EQBand": [param for letter in "abcdefghij" for param in PEQBand(letter).to_api_params()],
                },
                raw=None,
            )
        if "EQGetBand" in endpoint:
            return ApiResponse(
                parsed={
                    "status": "OK",
                    "source_name": "wifi",
                    "EQStat": "On" if state["graphic"] else "Off",
                    "Name": "" if state["graphic_custom"] else "Acoustic",
                    "pluginURI": "http://moddevices.com/plugins/caps/Eq10HP",
                },
                raw=None,
            )
        if "EQOff" in endpoint:
            state.update(peq=None, graphic=False)
        elif "EQOn" in endpoint or "EQLoad:" in endpoint:
            state.update(peq=None, graphic=True)
        return ApiResponse(parsed={"status": "OK"}, raw=None)

    client._request = AsyncMock(side_effect=response)
    callback = MagicMock()
    player = Player(client, on_state_changed=callback)
    player._status_model = PlayerStatus(source="wifi", eq_preset="0")
    player._state_mgr._set_eq_source("wifi")
    player._eq_presets = ["Acoustic"]
    await player.initialize_peq_presets()
    await player.refresh_eq_state()
    mock_coordinator.player = player
    graphic = WiiMEQPresetSelect(mock_coordinator, mock_config_entry)
    parametric = WiiMPEQPresetSelect(mock_coordinator, mock_config_entry)

    assert parametric.options == ["Off", *names]
    for name in names:
        await parametric.async_select_option(name)
        assert parametric.current_option == name
        assert graphic.current_option == "Off"

    await parametric.async_select_option("Off")
    assert parametric.current_option == "Off"
    assert graphic.current_option == "Off"
    await graphic.async_select_option("Acoustic")
    assert graphic.current_option == "Acoustic"
    assert parametric.current_option == "Off"
    assert callback.call_count == 5

    # The existing custom-band service must also reconcile both selectors.
    from custom_components.wiim.media_player import WiiMMediaPlayer

    await parametric.async_select_option(names[0])
    assert parametric.current_option == names[0]
    media_player = WiiMMediaPlayer(mock_coordinator, mock_config_entry)
    gains = list(range(-5, 5))
    await media_player.async_set_eq("custom", gains)
    assert [entry["param_name"] for entry in state["bands"]] == list(GEQ_BAND_NAMES)
    assert graphic.current_option == "Custom"
    assert parametric.current_option == "Off"
    assert callback.call_count == 7


class TestPEQPresetSelect:
    """Saved PEQ presets in Home Assistant."""

    @pytest.mark.asyncio
    async def test_options_state_and_selection(self, mock_coordinator, mock_config_entry):
        mock_coordinator.player.peq_presets = ["Low", "High"]
        mock_coordinator.player.peq_preset = "Low"
        mock_coordinator.player.peq_enabled = True
        entity = WiiMPEQPresetSelect(mock_coordinator, mock_config_entry)
        assert entity.unique_id == "test-uuid_peq_preset"
        assert entity.options == ["Off", "Low", "High"]
        assert entity.current_option == "Low"
        await entity.async_select_option("High")
        mock_coordinator.player.set_peq_preset.assert_awaited_once_with("High")
        mock_coordinator.player.peq_preset = None
        assert entity.current_option is None
        mock_coordinator.player.peq_enabled = False
        assert entity.current_option == "Off"

    @pytest.mark.asyncio
    async def test_selection_failure_is_reported(self, mock_coordinator, mock_config_entry):
        mock_coordinator.player.set_peq_preset.side_effect = WiiMError("failed")
        entity = WiiMPEQPresetSelect(mock_coordinator, mock_config_entry)
        with pytest.raises(HomeAssistantError):
            await entity.async_select_option("Low")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "supported,presets,created", [(True, ["Low"], True), (True, [], True), (False, [], False)]
    )
    async def test_setup_gates_entity(self, mock_coordinator, mock_config_entry, supported, presets, created):
        from custom_components.wiim.select import async_setup_entry

        mock_coordinator.player.client.capabilities = {"supports_peq": supported}
        mock_coordinator.player.peq_presets = presets
        hass = MagicMock()
        hass.data = {"wiim": {mock_config_entry.entry_id: {"coordinator": mock_coordinator}}}
        add_entities = MagicMock()
        await async_setup_entry(hass, mock_config_entry, add_entities)
        entities = add_entities.call_args.args[0]
        assert any(isinstance(entity, WiiMPEQPresetSelect) for entity in entities) is created
        assert mock_coordinator.player.initialize_peq_presets.await_count == int(supported)

    @pytest.mark.asyncio
    async def test_setup_logs_list_error_without_blocking_other_entities(
        self, mock_coordinator, mock_config_entry, caplog
    ):
        from custom_components.wiim.select import async_setup_entry

        mock_coordinator.player.client.capabilities = {"supports_peq": True}
        mock_coordinator.player.initialize_peq_presets.side_effect = WiiMError("device unavailable")
        hass = MagicMock()
        hass.data = {"wiim": {mock_config_entry.entry_id: {"coordinator": mock_coordinator}}}
        add_entities = MagicMock()
        await async_setup_entry(hass, mock_config_entry, add_entities)
        assert "Could not read parametric EQ presets" in caplog.text
        assert any(isinstance(entity, WiiMPEQPresetSelect) for entity in add_entities.call_args.args[0])


class TestWiiMOutputModeSelectBasic:
    """Test basic output mode select functionality."""

    def test_initialization(self, mock_coordinator, mock_config_entry):
        """Test output mode select initialization."""
        entity = WiiMOutputModeSelect(mock_coordinator, mock_config_entry)
        assert entity.unique_id == "test-uuid_output_mode"
        assert entity.name == "Audio Output Mode"

    def test_icon(self, mock_coordinator, mock_config_entry):
        """Test icon property."""
        entity = WiiMOutputModeSelect(mock_coordinator, mock_config_entry)
        assert entity.icon == "mdi:audio-video"

    def test_has_entity_name(self, mock_coordinator, mock_config_entry):
        """Test has_entity_name property."""
        entity = WiiMOutputModeSelect(mock_coordinator, mock_config_entry)
        assert entity._attr_has_entity_name is True


class TestWiiMOutputModeSelectOptions:
    """Test output mode options."""

    def test_options_returns_available_outputs(self, mock_coordinator, mock_config_entry):
        """Test options property returns available outputs from player."""
        mock_coordinator.player.available_outputs = ["Analog", "Optical", "BT: Speaker"]

        entity = WiiMOutputModeSelect(mock_coordinator, mock_config_entry)
        assert entity.options == ["Analog", "Optical", "BT: Speaker"]

    def test_options_returns_empty_when_no_player(self, mock_coordinator, mock_config_entry):
        """Test options returns empty list when available_outputs is None."""
        mock_coordinator.player.available_outputs = None

        entity = WiiMOutputModeSelect(mock_coordinator, mock_config_entry)
        assert entity.options == []

    def test_options_returns_empty_when_none(self, mock_coordinator, mock_config_entry):
        """Test options returns empty list when available_outputs is None."""
        mock_coordinator.player.available_outputs = None

        entity = WiiMOutputModeSelect(mock_coordinator, mock_config_entry)
        assert entity.options == []


class TestWiiMOutputModeSelectCurrentOption:
    """Test current option selection."""

    def test_current_option_returns_audio_output_mode(self, mock_coordinator, mock_config_entry):
        """Test current option returns audio output mode when not Bluetooth."""
        mock_coordinator.player.audio_output_mode = "Optical"
        mock_coordinator.player.available_outputs = ["Analog", "Optical"]
        mock_coordinator.player.is_bluetooth_output_active = False

        entity = WiiMOutputModeSelect(mock_coordinator, mock_config_entry)
        assert entity.current_option == "Optical"

    def test_current_option_returns_bt_device_when_active(self, mock_coordinator, mock_config_entry):
        """Test current option returns BT device when Bluetooth is active."""
        mock_coordinator.player.is_bluetooth_output_active = True
        # pywiim returns "Bluetooth Out" for audio_output_mode when BT is active
        mock_coordinator.player.audio_output_mode = "Bluetooth Out"
        mock_coordinator.player.bluetooth_output_devices = [{"name": "Speaker", "connected": True}]
        mock_coordinator.player.available_outputs = ["Analog", "BT: Speaker"]

        entity = WiiMOutputModeSelect(mock_coordinator, mock_config_entry)
        assert entity.current_option == "BT: Speaker"

    def test_current_option_returns_none_when_no_player(self, mock_coordinator, mock_config_entry):
        """Test current option returns None when available_outputs is None."""
        mock_coordinator.player.available_outputs = None

        entity = WiiMOutputModeSelect(mock_coordinator, mock_config_entry)
        assert entity.current_option is None

    def test_current_option_returns_none_when_no_outputs(self, mock_coordinator, mock_config_entry):
        """Test current option returns None when no outputs available."""
        mock_coordinator.player.available_outputs = []

        entity = WiiMOutputModeSelect(mock_coordinator, mock_config_entry)
        assert entity.current_option is None

    def test_current_option_case_insensitive_match(self, mock_coordinator, mock_config_entry):
        """Test current option matches case-insensitively."""
        mock_coordinator.player.audio_output_mode = "analog"  # lowercase
        mock_coordinator.player.available_outputs = ["Analog"]  # capitalized
        mock_coordinator.player.is_bluetooth_output_active = False

        entity = WiiMOutputModeSelect(mock_coordinator, mock_config_entry)
        assert entity.current_option == "Analog"


class TestWiiMOutputModeSelectSelectOption:
    """Test selecting output option."""

    async def test_select_option(self, mock_coordinator, mock_config_entry):
        """Test selecting an output option."""
        entity = WiiMOutputModeSelect(mock_coordinator, mock_config_entry)
        player = mock_coordinator.player

        await entity.async_select_option("Optical")

        player.audio.select_output.assert_called_once_with("Optical")

    async def test_select_option_raises_when_player_unavailable(self, mock_coordinator, mock_config_entry):
        """Test select option raises error when player raises error."""
        mock_coordinator.player.audio.select_output = AsyncMock(side_effect=WiiMError("Audio control unavailable"))

        entity = WiiMOutputModeSelect(mock_coordinator, mock_config_entry)

        with pytest.raises(HomeAssistantError):
            await entity.async_select_option("Optical")

    async def test_select_option_handles_connection_error(self, mock_coordinator, mock_config_entry):
        """Test select option handles connection errors."""
        mock_coordinator.player.audio.select_output = AsyncMock(side_effect=WiiMConnectionError("Connection lost"))
        mock_coordinator.player.name = "Test WiiM"

        entity = WiiMOutputModeSelect(mock_coordinator, mock_config_entry)

        with pytest.raises(HomeAssistantError, match="device unreachable"):
            await entity.async_select_option("Optical")

    async def test_select_option_handles_timeout_error(self, mock_coordinator, mock_config_entry):
        """Test select option handles timeout errors."""
        mock_coordinator.player.audio.select_output = AsyncMock(side_effect=WiiMTimeoutError("Timeout"))
        mock_coordinator.player.name = "Test WiiM"

        entity = WiiMOutputModeSelect(mock_coordinator, mock_config_entry)

        with pytest.raises(HomeAssistantError, match="device unreachable"):
            await entity.async_select_option("Optical")

    async def test_select_option_handles_bluetooth_error(self, mock_coordinator, mock_config_entry):
        """Test select option handles Bluetooth connection errors."""
        mock_coordinator.player.audio.select_output = AsyncMock(
            side_effect=WiiMError("Invalid JSON from connectbta2dp")
        )
        mock_coordinator.player.name = "Test WiiM"

        entity = WiiMOutputModeSelect(mock_coordinator, mock_config_entry)

        # Note: wiim_command wraps the error, but select.py has special handling for Bluetooth errors
        # that checks the error string. However, since wiim_command catches WiiMError first,
        # the Bluetooth-specific handling in select.py won't be reached.
        # The error will be wrapped by wiim_command with the generic message.
        with pytest.raises(HomeAssistantError, match="Failed to select audio output"):
            await entity.async_select_option("BT: Speaker")

    async def test_select_option_handles_other_errors(self, mock_coordinator, mock_config_entry):
        """Test select option handles other errors."""
        mock_coordinator.player.audio.select_output = AsyncMock(side_effect=WiiMError("Output error"))
        mock_coordinator.player.name = "Test WiiM"

        entity = WiiMOutputModeSelect(mock_coordinator, mock_config_entry)

        with pytest.raises(HomeAssistantError, match="Failed to select audio output"):
            await entity.async_select_option("Optical")


class TestWiiMOutputModeSelectPlatformSetup:
    """Test platform setup for select entities."""

    @pytest.mark.asyncio
    async def test_setup_with_audio_output_support(self, hass, mock_coordinator, mock_config_entry):
        """Test setup creates entity when device supports audio output."""
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.select import async_setup_entry

        # Mock capabilities on coordinator player
        mock_coordinator.player.supports_audio_output = True
        mock_config_entry.entry_id = "test-entry"

        # Register coordinator in hass.data
        hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = {
            "coordinator": mock_coordinator,
            "entry": mock_config_entry,
        }

        entities = []

        def add_entities(new_entities, update_before_add=False):
            entities.extend(new_entities)

        await async_setup_entry(hass, mock_config_entry, add_entities)

        assert len(entities) == 1
        assert isinstance(entities[0], WiiMOutputModeSelect)

    @pytest.mark.asyncio
    async def test_setup_without_audio_output_support(self, hass, mock_coordinator, mock_config_entry):
        """Test setup skips entity when device doesn't support audio output."""
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.select import async_setup_entry

        # Mock capabilities - no audio output support
        mock_coordinator.player.supports_audio_output = False
        mock_config_entry.entry_id = "test-entry"

        # Register coordinator in hass.data
        hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = {
            "coordinator": mock_coordinator,
            "entry": mock_config_entry,
        }

        add_entities = MagicMock()
        await async_setup_entry(hass, mock_config_entry, add_entities)

        add_entities.assert_called_once_with([])


class TestWiiMEQPresetSelectBasic:
    """Test basic EQ preset select functionality."""

    def test_initialization(self, mock_coordinator, mock_config_entry):
        """Test EQ preset select initialization."""
        entity = WiiMEQPresetSelect(mock_coordinator, mock_config_entry)
        assert entity.unique_id == "test-uuid_eq_preset"
        assert entity.name == "EQ Preset"

    def test_initialization_falls_back_to_host(self, mock_coordinator, mock_config_entry):
        """Test unique_id uses player host when config entry has no unique_id."""
        mock_config_entry.unique_id = None
        mock_coordinator.player.host = "192.168.1.48"
        entity = WiiMEQPresetSelect(mock_coordinator, mock_config_entry)
        assert entity.unique_id == "192.168.1.48_eq_preset"

    def test_icon(self, mock_coordinator, mock_config_entry):
        """Test icon property."""
        entity = WiiMEQPresetSelect(mock_coordinator, mock_config_entry)
        assert entity.icon == "mdi:equalizer"

    def test_has_entity_name(self, mock_coordinator, mock_config_entry):
        """Test has_entity_name property."""
        entity = WiiMEQPresetSelect(mock_coordinator, mock_config_entry)
        assert entity._attr_has_entity_name is True


class TestWiiMEQPresetSelectOptions:
    """Test EQ preset options."""

    def test_options_returns_presets(self, mock_coordinator, mock_config_entry):
        """Test options returns device presets when Off is already present."""
        entity = WiiMEQPresetSelect(mock_coordinator, mock_config_entry)
        assert entity.options == ["Off", "Flat", "Rock", "Jazz"]

    def test_options_prepends_off_when_missing(self, mock_coordinator, mock_config_entry):
        """Test options inserts Off when pywiim omits it."""
        mock_coordinator.player.eq_presets = ["Flat", "Rock"]
        entity = WiiMEQPresetSelect(mock_coordinator, mock_config_entry)
        assert entity.options == ["Off", "Flat", "Rock"]

    def test_options_returns_off_when_empty(self, mock_coordinator, mock_config_entry):
        """Test options returns Off when no presets are available."""
        mock_coordinator.player.eq_presets = []
        mock_coordinator.player.eq_preset = None
        entity = WiiMEQPresetSelect(mock_coordinator, mock_config_entry)
        assert entity.options == ["Off"]

    def test_options_returns_off_when_none(self, mock_coordinator, mock_config_entry):
        """Test options returns Off when eq_presets is None."""
        mock_coordinator.player.eq_presets = None
        mock_coordinator.player.eq_preset = None
        entity = WiiMEQPresetSelect(mock_coordinator, mock_config_entry)
        assert entity.options == ["Off"]


class TestWiiMEQPresetSelectCurrentOption:
    """Test current EQ preset option."""

    def test_current_option_returns_preset(self, mock_coordinator, mock_config_entry):
        """Test current option returns the active EQ preset."""
        mock_coordinator.player.eq_preset = "Rock"
        entity = WiiMEQPresetSelect(mock_coordinator, mock_config_entry)
        assert entity.current_option == "Rock"

    def test_current_option_returns_unknown_when_none(self, mock_coordinator, mock_config_entry):
        """An unavailable EQ state is unknown, not Off."""
        mock_coordinator.player.eq_preset = None
        entity = WiiMEQPresetSelect(mock_coordinator, mock_config_entry)
        assert entity.current_option is None

    def test_current_option_returns_unknown_when_empty(self, mock_coordinator, mock_config_entry):
        """An empty state does not prove that EQ is Off."""
        mock_coordinator.player.eq_preset = ""
        entity = WiiMEQPresetSelect(mock_coordinator, mock_config_entry)
        assert entity.current_option is None

    def test_current_option_case_insensitive_match(self, mock_coordinator, mock_config_entry):
        """Test current option matches preset labels case-insensitively."""
        mock_coordinator.player.eq_preset = "rock"
        entity = WiiMEQPresetSelect(mock_coordinator, mock_config_entry)
        assert entity.current_option == "Rock"

    def test_current_option_off_case_insensitive(self, mock_coordinator, mock_config_entry):
        """Test lowercase off matches the Off option."""
        mock_coordinator.player.eq_preset = "off"
        entity = WiiMEQPresetSelect(mock_coordinator, mock_config_entry)
        assert entity.current_option == "Off"

    def test_current_option_includes_unlisted_observed_name(self, mock_coordinator, mock_config_entry):
        """A device-reported name remains visible without a matching list entry."""
        mock_coordinator.player.eq_preset = "Unknown"
        entity = WiiMEQPresetSelect(mock_coordinator, mock_config_entry)
        assert entity.current_option == "Unknown"


class TestWiiMEQPresetSelectSelectOption:
    """Test selecting an EQ preset."""

    async def test_select_option(self, mock_coordinator, mock_config_entry):
        """Test selecting an EQ preset."""
        entity = WiiMEQPresetSelect(mock_coordinator, mock_config_entry)
        await entity.async_select_option("Rock")
        mock_coordinator.player.set_eq_preset.assert_called_once_with("Rock")

    async def test_select_option_off(self, mock_coordinator, mock_config_entry):
        """Test selecting Off disables EQ."""
        entity = WiiMEQPresetSelect(mock_coordinator, mock_config_entry)
        await entity.async_select_option("Off")
        mock_coordinator.player.set_eq_preset.assert_called_once_with("Off")

    async def test_select_option_handles_error(self, mock_coordinator, mock_config_entry):
        """Test select option wraps WiiMError."""
        mock_coordinator.player.set_eq_preset = AsyncMock(side_effect=WiiMError("EQ failed"))
        entity = WiiMEQPresetSelect(mock_coordinator, mock_config_entry)
        with pytest.raises(HomeAssistantError, match="Failed to select EQ preset"):
            await entity.async_select_option("Rock")

    async def test_select_option_handles_connection_error(self, mock_coordinator, mock_config_entry):
        """Test select option handles connection errors."""
        mock_coordinator.player.set_eq_preset = AsyncMock(side_effect=WiiMConnectionError("Connection lost"))
        entity = WiiMEQPresetSelect(mock_coordinator, mock_config_entry)
        with pytest.raises(HomeAssistantError, match="device unreachable"):
            await entity.async_select_option("Rock")

    async def test_select_option_handles_timeout_error(self, mock_coordinator, mock_config_entry):
        """Test select option handles timeout errors."""
        mock_coordinator.player.set_eq_preset = AsyncMock(side_effect=WiiMTimeoutError("Timeout"))
        entity = WiiMEQPresetSelect(mock_coordinator, mock_config_entry)
        with pytest.raises(HomeAssistantError, match="device unreachable"):
            await entity.async_select_option("Rock")


class TestWiiMEQPresetSelectPlatformSetup:
    """Test platform setup for EQ preset select entities."""

    @pytest.mark.asyncio
    async def test_setup_with_eq_support(self, hass, mock_coordinator, mock_config_entry):
        """Test setup creates EQ select when the device supports EQ."""
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.select import async_setup_entry

        mock_coordinator.player.supports_audio_output = False
        mock_coordinator.player.supports_eq = True
        mock_config_entry.entry_id = "test-entry"

        hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = {
            "coordinator": mock_coordinator,
            "entry": mock_config_entry,
        }

        entities = []

        def add_entities(new_entities, update_before_add=False):
            entities.extend(new_entities)

        await async_setup_entry(hass, mock_config_entry, add_entities)

        assert len(entities) == 1
        assert isinstance(entities[0], WiiMEQPresetSelect)

    @pytest.mark.asyncio
    async def test_setup_with_audio_output_and_eq(self, hass, mock_coordinator, mock_config_entry):
        """Test setup creates both select entities when both are supported."""
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.select import async_setup_entry

        mock_coordinator.player.supports_audio_output = True
        mock_coordinator.player.supports_eq = True
        mock_config_entry.entry_id = "test-entry"

        hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = {
            "coordinator": mock_coordinator,
            "entry": mock_config_entry,
        }

        entities = []

        def add_entities(new_entities, update_before_add=False):
            entities.extend(new_entities)

        await async_setup_entry(hass, mock_config_entry, add_entities)

        assert len(entities) == 2
        assert isinstance(entities[0], WiiMOutputModeSelect)
        assert isinstance(entities[1], WiiMEQPresetSelect)

    @pytest.mark.asyncio
    async def test_setup_without_eq_support(self, hass, mock_coordinator, mock_config_entry):
        """Test setup skips EQ select when the device does not support EQ."""
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.select import async_setup_entry

        mock_coordinator.player.supports_audio_output = True
        mock_coordinator.player.supports_eq = False
        mock_config_entry.entry_id = "test-entry"

        hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = {
            "coordinator": mock_coordinator,
            "entry": mock_config_entry,
        }

        entities = []

        def add_entities(new_entities, update_before_add=False):
            entities.extend(new_entities)

        await async_setup_entry(hass, mock_config_entry, add_entities)

        assert len(entities) == 1
        assert isinstance(entities[0], WiiMOutputModeSelect)


FILTERS = [
    "Sharp Roll-Off Filter",
    "Slow Roll-Off Filter",
    "Short Delay Sharp Roll-Off Filter",
]


class TestWiiMDACFilterSelect:
    """DAC filter select reads pywiim's cached names and sets by name."""

    def test_initialization(self, mock_coordinator, mock_config_entry):
        """Test unique id, name, and configuration category."""
        from homeassistant.const import EntityCategory

        from custom_components.wiim.select import WiiMDACFilterSelect

        entity = WiiMDACFilterSelect(mock_coordinator, mock_config_entry)
        assert entity.unique_id == "test-uuid_dac_filter"
        assert entity.name == "DAC Filter"
        assert entity.entity_category is EntityCategory.CONFIG
        assert entity.icon == "mdi:sine-wave"

    def test_options_and_current(self, mock_coordinator, mock_config_entry):
        """Options and the current value come from the cached player properties."""
        from custom_components.wiim.select import WiiMDACFilterSelect

        mock_coordinator.player.digital_filter_types = FILTERS
        mock_coordinator.player.digital_filter = "Slow Roll-Off Filter"
        entity = WiiMDACFilterSelect(mock_coordinator, mock_config_entry)
        assert entity.options == FILTERS
        assert entity.current_option == "Slow Roll-Off Filter"

    def test_current_option_unknown_is_none(self, mock_coordinator, mock_config_entry):
        """A missing or unmatched filter does not invent a selection."""
        from custom_components.wiim.select import WiiMDACFilterSelect

        mock_coordinator.player.digital_filter_types = FILTERS
        mock_coordinator.player.digital_filter = None
        entity = WiiMDACFilterSelect(mock_coordinator, mock_config_entry)
        assert entity.current_option is None

        mock_coordinator.player.digital_filter = "Not a filter"
        assert entity.current_option is None

    async def test_select_option(self, mock_coordinator, mock_config_entry):
        """Selecting a name calls set_digital_filter with that name."""
        from custom_components.wiim.select import WiiMDACFilterSelect

        entity = WiiMDACFilterSelect(mock_coordinator, mock_config_entry)
        await entity.async_select_option("Sharp Roll-Off Filter")
        mock_coordinator.player.set_digital_filter.assert_called_once_with("Sharp Roll-Off Filter")

    async def test_select_option_handles_error(self, mock_coordinator, mock_config_entry):
        """WiiMError from the setter becomes a Home Assistant error."""
        from custom_components.wiim.select import WiiMDACFilterSelect

        mock_coordinator.player.set_digital_filter = AsyncMock(side_effect=WiiMError("Filter failed"))
        entity = WiiMDACFilterSelect(mock_coordinator, mock_config_entry)
        with pytest.raises(HomeAssistantError, match="Failed to select DAC filter"):
            await entity.async_select_option("Sharp Roll-Off Filter")

    @pytest.mark.asyncio
    async def test_setup_creates_entity_when_supported(self, hass, mock_coordinator, mock_config_entry):
        """The select exists only when pywiim reports a filter list."""
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.select import WiiMDACFilterSelect, async_setup_entry

        mock_coordinator.player.supports_audio_output = False
        mock_coordinator.player.supports_eq = False
        mock_coordinator.player.supports_digital_filter = True
        mock_config_entry.entry_id = "test-entry"
        hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = {
            "coordinator": mock_coordinator,
            "entry": mock_config_entry,
        }
        entities = []

        def add_entities(new_entities, update_before_add=False):
            entities.extend(new_entities)

        await async_setup_entry(hass, mock_config_entry, add_entities)

        assert len(entities) == 1
        assert isinstance(entities[0], WiiMDACFilterSelect)

    @pytest.mark.asyncio
    async def test_setup_skips_entity_when_unsupported(self, hass, mock_coordinator, mock_config_entry):
        """No filter select when the support list was empty."""
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.select import async_setup_entry

        mock_coordinator.player.supports_audio_output = True
        mock_coordinator.player.supports_eq = True
        mock_coordinator.player.supports_digital_filter = False
        mock_config_entry.entry_id = "test-entry"
        hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = {
            "coordinator": mock_coordinator,
            "entry": mock_config_entry,
        }
        entities = []

        def add_entities(new_entities, update_before_add=False):
            entities.extend(new_entities)

        await async_setup_entry(hass, mock_config_entry, add_entities)

        assert len(entities) == 2


class TestWiiMRoomFitSelect:
    """RoomFit select follows the cached profile list and Off switch."""

    def test_init(self, mock_coordinator, mock_config_entry):
        """Unique id and name come from the config entry."""
        entity = WiiMRoomFitSelect(mock_coordinator, mock_config_entry)
        assert entity.unique_id == "test-uuid_room_fit"
        assert entity.name == "RoomFit"

    def test_options_include_off(self, mock_coordinator, mock_config_entry):
        """Options are Off plus the saved profile names."""
        mock_coordinator.player.room_correction_profiles = ["Bed", "Desk"]
        entity = WiiMRoomFitSelect(mock_coordinator, mock_config_entry)
        assert entity.options == ["Off", "Bed", "Desk"]

    def test_current_option_is_off_when_disabled(self, mock_coordinator, mock_config_entry):
        """The select shows Off while RoomFit is disabled."""
        mock_coordinator.player.room_correction_profiles = ["Bed", "Desk"]
        mock_coordinator.player.room_correction = "Off"
        entity = WiiMRoomFitSelect(mock_coordinator, mock_config_entry)
        assert entity.current_option == "Off"

    def test_current_option_is_selected_profile(self, mock_coordinator, mock_config_entry):
        """The select shows the profile name while RoomFit is on."""
        mock_coordinator.player.room_correction_profiles = ["Bed", "Desk"]
        mock_coordinator.player.room_correction = "Desk"
        entity = WiiMRoomFitSelect(mock_coordinator, mock_config_entry)
        assert entity.current_option == "Desk"

    def test_current_option_unknown_is_none(self, mock_coordinator, mock_config_entry):
        """A value that is not one of the options stays unknown."""
        mock_coordinator.player.room_correction_profiles = ["Bed", "Desk"]
        mock_coordinator.player.room_correction = None
        entity = WiiMRoomFitSelect(mock_coordinator, mock_config_entry)
        assert entity.current_option is None

    @pytest.mark.asyncio
    async def test_select_option_calls_setter(self, mock_coordinator, mock_config_entry):
        """Selecting a profile or Off calls set_room_correction."""
        entity = WiiMRoomFitSelect(mock_coordinator, mock_config_entry)
        await entity.async_select_option("Desk")
        mock_coordinator.player.set_room_correction.assert_awaited_once_with("Desk")

    @pytest.mark.asyncio
    async def test_select_option_wraps_wiim_error(self, mock_coordinator, mock_config_entry):
        """A device error becomes a Home Assistant error."""
        mock_coordinator.player.set_room_correction.side_effect = WiiMError("nope")
        entity = WiiMRoomFitSelect(mock_coordinator, mock_config_entry)
        with pytest.raises(HomeAssistantError, match="Failed to select RoomFit"):
            await entity.async_select_option("Desk")

    @pytest.mark.asyncio
    async def test_setup_creates_entity_when_profiles_exist(self, hass, mock_coordinator, mock_config_entry):
        """A saved profile list creates the RoomFit select."""
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.select import async_setup_entry

        mock_coordinator.player.supports_audio_output = False
        mock_coordinator.player.supports_eq = False
        mock_coordinator.player.supports_digital_filter = False
        mock_coordinator.player.room_correction_profiles = ["Bed", "Desk"]
        mock_config_entry.entry_id = "test-entry"
        hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = {
            "coordinator": mock_coordinator,
            "entry": mock_config_entry,
        }
        entities = []

        def add_entities(new_entities, update_before_add=False):
            entities.extend(new_entities)

        await async_setup_entry(hass, mock_config_entry, add_entities)

        assert len(entities) == 1
        assert isinstance(entities[0], WiiMRoomFitSelect)

    @pytest.mark.asyncio
    async def test_setup_skips_entity_when_no_profiles(self, hass, mock_coordinator, mock_config_entry):
        """An empty profile list does not create the select."""
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.select import async_setup_entry

        mock_coordinator.player.supports_audio_output = True
        mock_coordinator.player.supports_eq = False
        mock_coordinator.player.supports_digital_filter = False
        mock_coordinator.player.room_correction_profiles = []
        mock_config_entry.entry_id = "test-entry"
        hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = {
            "coordinator": mock_coordinator,
            "entry": mock_config_entry,
        }
        entities = []

        def add_entities(new_entities, update_before_add=False):
            entities.extend(new_entities)

        await async_setup_entry(hass, mock_config_entry, add_entities)

        assert len(entities) == 1
        assert not any(isinstance(entity, WiiMRoomFitSelect) for entity in entities)


class TestWiiMChannelSelect:
    """Channel select maps Stereo / Left / Right to pywiim's output channel."""

    def test_initialization(self, mock_coordinator, mock_config_entry):
        """Unique id, name, options and configuration category."""
        from homeassistant.const import EntityCategory

        entity = WiiMChannelSelect(mock_coordinator, mock_config_entry)
        assert entity.unique_id == "test-uuid_output_channel"
        assert entity.name == "Channel"
        assert entity.options == ["Stereo", "Left", "Right"]
        assert entity.entity_category is EntityCategory.CONFIG
        assert entity.icon == "mdi:surround-sound-2-0"

    @pytest.mark.parametrize(
        ("channel", "expected"),
        [("stereo", "Stereo"), ("left", "Left"), ("right", "Right"), (None, None), ("mono", None)],
    )
    def test_current_option(self, mock_coordinator, mock_config_entry, channel, expected):
        """The current option follows player.output_channel; unknown values stay None."""
        mock_coordinator.player.output_channel = channel
        entity = WiiMChannelSelect(mock_coordinator, mock_config_entry)
        assert entity.current_option == expected

    @pytest.mark.parametrize(("option", "expected"), [("Stereo", "stereo"), ("Left", "left"), ("Right", "right")])
    @pytest.mark.asyncio
    async def test_select_option_calls_setter(self, mock_coordinator, mock_config_entry, option, expected):
        """Selecting an option calls set_output_channel with the pywiim name."""
        entity = WiiMChannelSelect(mock_coordinator, mock_config_entry)
        await entity.async_select_option(option)
        mock_coordinator.player.set_output_channel.assert_awaited_once_with(expected)

    @pytest.mark.asyncio
    async def test_select_option_wraps_wiim_error(self, mock_coordinator, mock_config_entry):
        """A device error becomes a Home Assistant error."""
        mock_coordinator.player.set_output_channel.side_effect = WiiMError("nope")
        entity = WiiMChannelSelect(mock_coordinator, mock_config_entry)
        with pytest.raises(HomeAssistantError, match="Failed to select channel"):
            await entity.async_select_option("Left")

    @pytest.mark.parametrize(("supported", "created"), [(True, True), (False, False)])
    @pytest.mark.asyncio
    async def test_setup_follows_capability(self, hass, mock_coordinator, mock_config_entry, supported, created):
        """The channel select exists only when pywiim reports supports_output_channel."""
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.select import async_setup_entry

        mock_coordinator.player.supports_audio_output = False
        mock_coordinator.player.supports_eq = False
        mock_coordinator.player.supports_digital_filter = False
        mock_coordinator.player.room_correction_profiles = []
        mock_coordinator.player.supports_output_channel = supported
        mock_config_entry.entry_id = "test-entry"
        hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = {
            "coordinator": mock_coordinator,
            "entry": mock_config_entry,
        }
        entities = []

        def add_entities(new_entities, update_before_add=False):
            entities.extend(new_entities)

        await async_setup_entry(hass, mock_config_entry, add_entities)

        assert any(isinstance(entity, WiiMChannelSelect) for entity in entities) is created
        assert len(entities) == (1 if created else 0)
