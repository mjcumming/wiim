"""Unit tests for WiiM Select Entity - testing output mode selection."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError
from pywiim.exceptions import WiiMConnectionError, WiiMError, WiiMTimeoutError

from custom_components.wiim.data import Speaker
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
    return coordinator


@pytest.fixture
def mock_speaker(mock_coordinator, mock_config_entry):
    """Create a mock speaker."""
    speaker = MagicMock(spec=Speaker)
    speaker.coordinator = mock_coordinator
    speaker.config_entry = mock_config_entry
    speaker.uuid = "test-uuid"
    speaker.name = "Test WiiM"
    speaker.available = True
    speaker.model = "WiiM Mini"
    speaker.firmware = "1.0.0"
    speaker.role = "solo"
    speaker.ip_address = "192.168.1.100"
    speaker.mac_address = "AA:BB:CC:DD:EE:FF"
    speaker.input_list = ["spotify", "bluetooth"]
    speaker.device_model = None
    return speaker


class TestWiiMOutputModeSelectBasic:
    """Test basic output mode select functionality."""

    def test_initialization(self, mock_speaker):
        """Test output mode select initialization."""
        entity = WiiMOutputModeSelect(mock_speaker)
        assert entity.unique_id == "test-uuid_output_mode"
        assert entity.name == "Audio Output Mode"
        assert entity.speaker == mock_speaker

    def test_icon(self, mock_speaker):
        """Test icon property."""
        entity = WiiMOutputModeSelect(mock_speaker)
        assert entity.icon == "mdi:audio-video"

    def test_has_entity_name(self, mock_speaker):
        """Test has_entity_name property."""
        entity = WiiMOutputModeSelect(mock_speaker)
        assert entity._attr_has_entity_name is True


class TestWiiMOutputModeSelectOptions:
    """Test output mode options."""

    def test_options_returns_available_outputs(self, mock_speaker, mock_coordinator):
        """Test options property returns available outputs from player."""
        mock_coordinator.data["player"].available_outputs = ["Analog", "Optical", "BT: Speaker"]

        entity = WiiMOutputModeSelect(mock_speaker)
        assert entity.options == ["Analog", "Optical", "BT: Speaker"]

    def test_options_returns_empty_when_no_player(self, mock_speaker):
        """Test options returns empty list when player not available."""
        mock_speaker.coordinator.data = {}

        entity = WiiMOutputModeSelect(mock_speaker)
        assert entity.options == []

    def test_options_returns_empty_when_none(self, mock_speaker, mock_coordinator):
        """Test options returns empty list when available_outputs is None."""
        mock_coordinator.data["player"].available_outputs = None

        entity = WiiMOutputModeSelect(mock_speaker)
        assert entity.options == []


class TestWiiMOutputModeSelectCurrentOption:
    """Test current option selection."""

    def test_current_option_returns_audio_output_mode(self, mock_speaker, mock_coordinator):
        """Test current option returns audio output mode when not Bluetooth."""
        mock_coordinator.data["player"].audio_output_mode = "Optical"
        mock_coordinator.data["player"].available_outputs = ["Analog", "Optical"]
        mock_coordinator.data["player"].is_bluetooth_output_active = False

        entity = WiiMOutputModeSelect(mock_speaker)
        assert entity.current_option == "Optical"

    def test_current_option_returns_bt_device_when_active(self, mock_speaker, mock_coordinator):
        """Test current option returns BT device when Bluetooth is active."""
        mock_coordinator.data["player"].is_bluetooth_output_active = True
        mock_coordinator.data["player"].bluetooth_output_devices = [{"name": "Speaker", "connected": True}]
        mock_coordinator.data["player"].available_outputs = ["Analog", "BT: Speaker"]

        entity = WiiMOutputModeSelect(mock_speaker)
        assert entity.current_option == "BT: Speaker"

    def test_current_option_returns_none_when_no_player(self, mock_speaker):
        """Test current option returns None when player not available."""
        mock_speaker.coordinator.data = {}

        entity = WiiMOutputModeSelect(mock_speaker)
        assert entity.current_option is None

    def test_current_option_returns_none_when_no_outputs(self, mock_speaker, mock_coordinator):
        """Test current option returns None when no outputs available."""
        mock_coordinator.data["player"].available_outputs = []

        entity = WiiMOutputModeSelect(mock_speaker)
        assert entity.current_option is None

    def test_current_option_case_insensitive_match(self, mock_speaker, mock_coordinator):
        """Test current option matches case-insensitively."""
        mock_coordinator.data["player"].audio_output_mode = "analog"  # lowercase
        mock_coordinator.data["player"].available_outputs = ["Analog"]  # capitalized
        mock_coordinator.data["player"].is_bluetooth_output_active = False

        entity = WiiMOutputModeSelect(mock_speaker)
        assert entity.current_option == "Analog"


class TestWiiMOutputModeSelectSelectOption:
    """Test selecting output option."""

    async def test_select_option(self, mock_speaker, mock_coordinator):
        """Test selecting an output option."""
        entity = WiiMOutputModeSelect(mock_speaker)
        player = mock_coordinator.data["player"]
        # Ensure audio.select_output is an AsyncMock
        player.audio = MagicMock()
        player.audio.select_output = AsyncMock(return_value=True)

        await entity.async_select_option("Optical")

        player.audio.select_output.assert_called_once_with("Optical")

    async def test_select_option_raises_when_player_unavailable(self, mock_speaker):
        """Test select option raises error when player unavailable."""
        mock_speaker.coordinator.data = {}

        entity = WiiMOutputModeSelect(mock_speaker)

        with pytest.raises(HomeAssistantError, match="Player is not available"):
            await entity.async_select_option("Optical")

    async def test_select_option_handles_connection_error(self, mock_speaker, mock_coordinator):
        """Test select option handles connection errors."""
        mock_coordinator.data["player"].audio.select_output = AsyncMock(
            side_effect=WiiMConnectionError("Connection lost")
        )

        entity = WiiMOutputModeSelect(mock_speaker)

        with pytest.raises(HomeAssistantError, match="temporarily unreachable"):
            await entity.async_select_option("Optical")

    async def test_select_option_handles_timeout_error(self, mock_speaker, mock_coordinator):
        """Test select option handles timeout errors."""
        mock_coordinator.data["player"].audio.select_output = AsyncMock(side_effect=WiiMTimeoutError("Timeout"))

        entity = WiiMOutputModeSelect(mock_speaker)

        with pytest.raises(HomeAssistantError, match="temporarily unreachable"):
            await entity.async_select_option("Optical")

    async def test_select_option_handles_bluetooth_error(self, mock_speaker, mock_coordinator):
        """Test select option handles Bluetooth connection errors."""
        mock_coordinator.data["player"].audio.select_output = AsyncMock(
            side_effect=WiiMError("Invalid JSON from connectbta2dp")
        )

        entity = WiiMOutputModeSelect(mock_speaker)

        with pytest.raises(HomeAssistantError, match="Bluetooth device"):
            await entity.async_select_option("BT: Speaker")

    async def test_select_option_handles_other_errors(self, mock_speaker, mock_coordinator):
        """Test select option handles other errors."""
        mock_coordinator.data["player"].audio.select_output = AsyncMock(side_effect=WiiMError("Output error"))

        entity = WiiMOutputModeSelect(mock_speaker)

        with pytest.raises(HomeAssistantError, match="Failed to select audio output"):
            await entity.async_select_option("Optical")


class TestWiiMOutputModeSelectPlatformSetup:
    """Test platform setup for select entities."""

    @pytest.mark.asyncio
    async def test_setup_with_audio_output_support(self, hass, mock_speaker, mock_coordinator):
        """Test setup creates entity when device supports audio output."""
        from custom_components.wiim.select import async_setup_entry

        # Mock capabilities on coordinator client (must be a dict, not MagicMock)
        mock_speaker.coordinator.client = MagicMock()
        # Set capabilities as a dict attribute (not a MagicMock)
        type(mock_speaker.coordinator.client).capabilities = {"supports_audio_output": True}
        mock_speaker.config_entry = MagicMock()
        mock_speaker.config_entry.entry_id = "test-entry"

        entities = []

        def add_entities(new_entities, update_before_add=False):
            entities.extend(new_entities)

        with patch("custom_components.wiim.select.get_speaker_from_config_entry", return_value=mock_speaker):
            await async_setup_entry(hass, mock_speaker.config_entry, add_entities)

        assert len(entities) == 1
        assert isinstance(entities[0], WiiMOutputModeSelect)

    @pytest.mark.asyncio
    async def test_setup_without_audio_output_support(self, hass, mock_speaker):
        """Test setup skips entity when device doesn't support audio output."""
        from custom_components.wiim.select import async_setup_entry

        # Mock capabilities - no audio output support
        mock_speaker.coordinator.client = MagicMock()
        mock_speaker.coordinator.client.capabilities = {"supports_audio_output": False}

        entities = []

        async def add_entities(new_entities):
            entities.extend(new_entities)

        with patch("custom_components.wiim.select.get_speaker_from_config_entry", return_value=mock_speaker):
            await async_setup_entry(hass, mock_speaker.config_entry, add_entities)

        assert len(entities) == 0
