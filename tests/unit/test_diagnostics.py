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


class TestDiagnosticsUPnP:
    """Test UPnP client access in diagnostics."""

    @pytest.mark.asyncio
    async def test_diagnostics_handles_missing_upnp_client(
        self, hass, mock_config_entry, mock_device_entry, mock_coordinator
    ):
        """Test that diagnostics handles missing upnp_client gracefully (regression test)."""
        from custom_components.wiim.const import DOMAIN

        # Setup: coordinator without upnp_client attribute
        mock_coordinator.player._upnp_client = None

        # Set up hass.data
        hass.data = {
            DOMAIN: {mock_config_entry.entry_id: {"coordinator": mock_coordinator, "entry": mock_config_entry}}
        }

        result = await async_get_device_diagnostics(hass, mock_config_entry, mock_device_entry)

        # Should not raise AttributeError
        assert "error" not in result or "upnp_client" not in str(result.get("error", ""))
        assert "upnp_status" in result

    @pytest.mark.asyncio
    async def test_diagnostics_upnp_client_safe_access(
        self, hass, mock_config_entry, mock_device_entry, mock_coordinator
    ):
        """Test that diagnostics safely accesses upnp_client from player."""
        from custom_components.wiim.const import DOMAIN

        # Setup: player has _upnp_client
        mock_upnp_client = MagicMock()
        mock_upnp_client.description_url = "http://192.168.1.100/description.xml"
        mock_upnp_client.host = "192.168.1.100"
        mock_coordinator.player._upnp_client = mock_upnp_client

        # Set up hass.data
        hass.data = {
            DOMAIN: {mock_config_entry.entry_id: {"coordinator": mock_coordinator, "entry": mock_config_entry}}
        }

        result = await async_get_device_diagnostics(hass, mock_config_entry, mock_device_entry)

        assert "upnp_status" in result
        upnp_status = result["upnp_status"]
        assert upnp_status["has_upnp_client"] is True
        assert "upnp_client" in upnp_status

    @pytest.mark.asyncio
    async def test_diagnostics_upnp_client_missing_from_player(
        self, hass, mock_config_entry, mock_device_entry, mock_coordinator
    ):
        """Test diagnostics when player doesn't have _upnp_client."""
        from custom_components.wiim.const import DOMAIN

        # Remove _upnp_client attribute
        if hasattr(mock_coordinator.player, "_upnp_client"):
            delattr(mock_coordinator.player, "_upnp_client")

        # Set up hass.data
        hass.data = {
            DOMAIN: {mock_config_entry.entry_id: {"coordinator": mock_coordinator, "entry": mock_config_entry}}
        }

        result = await async_get_device_diagnostics(hass, mock_config_entry, mock_device_entry)

        assert "upnp_status" in result
        upnp_status = result["upnp_status"]
        assert upnp_status["has_upnp_client"] is False

    @pytest.mark.asyncio
    async def test_diagnostics_handles_coordinator_none(self, hass, mock_config_entry, mock_device_entry):
        """Test diagnostics when coordinator is None."""
        from custom_components.wiim.const import DOMAIN

        # Set up hass.data with None coordinator
        hass.data = {DOMAIN: {mock_config_entry.entry_id: {"coordinator": None, "entry": mock_config_entry}}}

        result = await async_get_device_diagnostics(hass, mock_config_entry, mock_device_entry)

        # Should handle gracefully
        assert "error" in result or "upnp_status" in result


class TestConfigEntryDiagnostics:
    """Test config entry diagnostics."""

    @pytest.mark.asyncio
    async def test_config_entry_diagnostics_success(self, hass, mock_config_entry, mock_coordinator):
        """Test config entry diagnostics with valid coordinator."""
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.diagnostics import async_get_config_entry_diagnostics

        # Ensure mock_coordinator has player with required attributes
        mock_coordinator.player.name = "Test WiiM"
        mock_coordinator.player.model = "WiiM Mini"
        mock_coordinator.player.firmware = "1.0.0"
        mock_coordinator.player.role = "solo"
        mock_coordinator.player.is_solo = True
        mock_coordinator.player.is_master = False
        mock_coordinator.player.is_slave = False
        mock_coordinator.player.available = True

        # Set up hass.data
        hass.data = {
            DOMAIN: {mock_config_entry.entry_id: {"coordinator": mock_coordinator, "entry": mock_config_entry}}
        }

        # Mock config_entries.async_entries to return our mock entry
        with patch.object(hass.config_entries, "async_entries", return_value=[mock_config_entry]):
            result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

            assert "entry_data" in result
            assert "integration_info" in result
            assert "coordinator" in result
            assert "device_basic" in result
            assert result["integration_info"]["total_speakers"] >= 1

    @pytest.mark.asyncio
    async def test_config_entry_diagnostics_speaker_not_found(self, hass, mock_config_entry):
        """Test config entry diagnostics when coordinator not found."""
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.diagnostics import async_get_config_entry_diagnostics

        # Set up hass.data without the entry
        hass.data = {DOMAIN: {}}

        result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

        # Should handle exception and return error
        assert "error" in result or "entry_data" in result

    @pytest.mark.asyncio
    async def test_config_entry_diagnostics_with_group(self, hass, mock_config_entry, mock_coordinator):
        """Test config entry diagnostics with group information."""
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.diagnostics import async_get_config_entry_diagnostics

        # Setup master with group
        player = MagicMock()
        player.name = "Test WiiM"
        player.model = "WiiM Mini"
        player.firmware = "1.0.0"
        player.role = "master"
        player.is_master = True
        player.is_solo = False
        player.is_slave = False
        player.available = True
        player.group = MagicMock()
        player.group.all_players = [player, MagicMock()]  # Master + 1 slave
        mock_coordinator.player = player

        # Set up hass.data
        hass.data = {
            DOMAIN: {mock_config_entry.entry_id: {"coordinator": mock_coordinator, "entry": mock_config_entry}}
        }

        result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

        assert result["device_basic"]["group_members_count"] == 1

    @pytest.mark.asyncio
    async def test_config_entry_diagnostics_handles_exception(self, hass, mock_config_entry, mock_coordinator):
        """Test config entry diagnostics handles exceptions."""
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.diagnostics import async_get_config_entry_diagnostics

        # Set up hass.data with a coordinator that will raise an error
        mock_coordinator.player = None  # This might cause issues
        hass.data = {
            DOMAIN: {mock_config_entry.entry_id: {"coordinator": mock_coordinator, "entry": mock_config_entry}}
        }

        result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

        # Should handle gracefully - might have error or partial data
        assert "error" in result or "entry_data" in result


class TestDiagnosticsHelperFunctions:
    """Test diagnostics helper functions."""

    def test_get_pywiim_version(self):
        """Test _get_pywiim_version function."""
        from importlib.metadata import PackageNotFoundError

        from custom_components.wiim.diagnostics import _get_pywiim_version

        with patch("custom_components.wiim.diagnostics.metadata.version", return_value="1.0.0"):
            version = _get_pywiim_version()
            assert version == "1.0.0"

        with patch("custom_components.wiim.diagnostics.metadata.version", side_effect=PackageNotFoundError("pywiim")):
            version = _get_pywiim_version()
            assert version == "unknown"
