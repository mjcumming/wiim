"""Unit tests for WiiM Diagnostics - testing safe attribute access."""

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntry

from custom_components.wiim.diagnostics import async_get_device_diagnostics

# Use the same fixtures as other tests
pytest_plugins = "pytest_homeassistant_custom_component"


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
def mock_device_entry():
    """Create a mock device entry."""
    device = MagicMock(spec=DeviceEntry)
    device.id = "test_device_id"
    return device


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.data = {"player": MagicMock()}
    coordinator.last_update_success = True
    coordinator.player = MagicMock()
    coordinator.player.host = "192.168.1.100"
    coordinator.player.volume_level = 0.5
    coordinator.player.is_muted = False
    coordinator.player.play_state = "play"
    coordinator.player.source = "spotify"
    # UPnP client is on player, not coordinator
    coordinator.player._upnp_client = None
    return coordinator


@pytest.fixture
def mock_speaker(mock_coordinator, mock_config_entry):
    """Create a mock speaker."""
    speaker = MagicMock()
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


class TestDiagnosticsUPnP:
    """Test UPnP client access in diagnostics."""

    @pytest.mark.asyncio
    async def test_diagnostics_handles_missing_upnp_client(
        self, hass, mock_config_entry, mock_device_entry, mock_speaker
    ):
        """Test that diagnostics handles missing upnp_client gracefully (regression test)."""
        # Setup: coordinator without upnp_client attribute
        mock_speaker.coordinator.player._upnp_client = None

        # Mock the get_speaker_from_config_entry function
        with patch(
            "custom_components.wiim.diagnostics.get_speaker_from_config_entry",
            return_value=mock_speaker,
        ):
            result = await async_get_device_diagnostics(hass, mock_config_entry, mock_device_entry)

            # Should not raise AttributeError
            assert "error" not in result or "upnp_client" not in str(result.get("error", ""))
            assert "upnp_status" in result

    @pytest.mark.asyncio
    async def test_diagnostics_upnp_client_safe_access(self, hass, mock_config_entry, mock_device_entry, mock_speaker):
        """Test that diagnostics safely accesses upnp_client from player."""
        # Setup: player has _upnp_client
        mock_upnp_client = MagicMock()
        mock_upnp_client.description_url = "http://192.168.1.100/description.xml"
        mock_upnp_client.host = "192.168.1.100"
        mock_speaker.coordinator.player._upnp_client = mock_upnp_client

        with patch(
            "custom_components.wiim.diagnostics.get_speaker_from_config_entry",
            return_value=mock_speaker,
        ):
            result = await async_get_device_diagnostics(hass, mock_config_entry, mock_device_entry)

            assert "upnp_status" in result
            upnp_status = result["upnp_status"]
            assert upnp_status["has_upnp_client"] is True
            assert "upnp_client" in upnp_status

    @pytest.mark.asyncio
    async def test_diagnostics_upnp_client_missing_from_player(
        self, hass, mock_config_entry, mock_device_entry, mock_speaker
    ):
        """Test diagnostics when player doesn't have _upnp_client."""
        # Remove _upnp_client attribute
        if hasattr(mock_speaker.coordinator.player, "_upnp_client"):
            delattr(mock_speaker.coordinator.player, "_upnp_client")

        with patch(
            "custom_components.wiim.diagnostics.get_speaker_from_config_entry",
            return_value=mock_speaker,
        ):
            result = await async_get_device_diagnostics(hass, mock_config_entry, mock_device_entry)

            assert "upnp_status" in result
            upnp_status = result["upnp_status"]
            assert upnp_status["has_upnp_client"] is False

    @pytest.mark.asyncio
    async def test_diagnostics_handles_coordinator_none(self, hass, mock_config_entry, mock_device_entry, mock_speaker):
        """Test diagnostics when coordinator is None."""
        mock_speaker.coordinator = None

        with patch(
            "custom_components.wiim.diagnostics.get_speaker_from_config_entry",
            return_value=mock_speaker,
        ):
            result = await async_get_device_diagnostics(hass, mock_config_entry, mock_device_entry)

            # Should handle gracefully
            assert "error" in result or "upnp_status" in result


class TestConfigEntryDiagnostics:
    """Test config entry diagnostics."""

    @pytest.mark.asyncio
    async def test_config_entry_diagnostics_success(self, hass, mock_config_entry, mock_speaker):
        """Test config entry diagnostics with valid speaker."""
        from unittest.mock import patch

        from custom_components.wiim.diagnostics import async_get_config_entry_diagnostics

        with patch(
            "custom_components.wiim.diagnostics.get_speaker_from_config_entry",
            return_value=mock_speaker,
        ):
            with patch("custom_components.wiim.diagnostics.get_all_speakers", return_value=[mock_speaker]):
                result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

                assert "entry_data" in result
                assert "integration_info" in result
                assert "coordinator" in result
                assert "speaker_basic" in result
                assert result["integration_info"]["total_speakers"] == 1

    @pytest.mark.asyncio
    async def test_config_entry_diagnostics_speaker_not_found(self, hass, mock_config_entry):
        """Test config entry diagnostics when speaker not found."""
        from unittest.mock import patch

        from custom_components.wiim.diagnostics import async_get_config_entry_diagnostics

        with patch(
            "custom_components.wiim.diagnostics.get_speaker_from_config_entry",
            side_effect=RuntimeError("Speaker not found"),
        ):
            result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

            # Should handle exception and return error
            assert "error" in result or "entry_data" in result

    @pytest.mark.asyncio
    async def test_config_entry_diagnostics_with_group(self, hass, mock_config_entry, mock_speaker):
        """Test config entry diagnostics with group information."""
        from unittest.mock import MagicMock, patch

        from custom_components.wiim.diagnostics import async_get_config_entry_diagnostics

        # Setup master with group
        mock_speaker.coordinator.data = {"player": MagicMock()}
        player = mock_speaker.coordinator.data["player"]
        player.is_master = True
        player.is_solo = False
        player.group = MagicMock()
        player.group.all_players = [player, MagicMock()]  # Master + 1 slave

        with patch(
            "custom_components.wiim.diagnostics.get_speaker_from_config_entry",
            return_value=mock_speaker,
        ):
            with patch("custom_components.wiim.diagnostics.get_all_speakers", return_value=[mock_speaker]):
                result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

                assert result["speaker_basic"]["group_members_count"] == 1

    @pytest.mark.asyncio
    async def test_config_entry_diagnostics_handles_exception(self, hass, mock_config_entry):
        """Test config entry diagnostics handles exceptions."""
        from unittest.mock import patch

        from custom_components.wiim.diagnostics import async_get_config_entry_diagnostics

        with patch(
            "custom_components.wiim.diagnostics.get_speaker_from_config_entry",
            side_effect=Exception("Unexpected error"),
        ):
            result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

            assert "error" in result
            assert "Failed to generate diagnostics" in result["error"]


class TestDiagnosticsHelperFunctions:
    """Test diagnostics helper functions."""

    def test_get_pywiim_version(self):
        """Test _get_pywiim_version function."""
        from importlib.metadata import PackageNotFoundError
        from unittest.mock import patch

        from custom_components.wiim.diagnostics import _get_pywiim_version

        with patch("custom_components.wiim.diagnostics.metadata.version", return_value="1.0.0"):
            version = _get_pywiim_version()
            assert version == "1.0.0"

        with patch("custom_components.wiim.diagnostics.metadata.version", side_effect=PackageNotFoundError("pywiim")):
            version = _get_pywiim_version()
            assert version == "unknown"
