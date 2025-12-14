"""Unit tests for WiiM Select Entity - testing output mode selection."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError
from pywiim.exceptions import WiiMConnectionError, WiiMError, WiiMTimeoutError

from custom_components.wiim.select import WiiMOutputModeSelect


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.unique_id = "test-uuid"
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
    return coordinator


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

        entities = []

        async def add_entities(new_entities):
            entities.extend(new_entities)

        await async_setup_entry(hass, mock_config_entry, add_entities)

        assert len(entities) == 0
