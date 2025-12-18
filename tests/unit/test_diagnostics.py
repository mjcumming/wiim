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
    entry.title = "Test WiiM"
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
def mock_player():
    """Create a properly mocked player with all expected attributes."""
    player = MagicMock()
    # Basic device info
    player.name = "Test WiiM"
    player.model = "WiiM Mini"
    player.firmware = "1.0.0"
    player.host = "192.168.1.100"
    player.port = 443
    player.timeout = 10
    player.uuid = "test-uuid"

    # Availability & state
    player.available = True
    player.wifi_rssi = -55

    # Group/role
    player.role = "solo"
    player.is_solo = True
    player.is_master = False
    player.is_slave = False
    player.group = None

    # Playback state
    player.play_state = "play"
    player.is_playing = True
    player.is_paused = False
    player.is_buffering = False
    player.source = "spotify"
    player.volume_level = 0.5
    player.is_muted = False
    player.shuffle = False
    player.repeat = "off"

    # Media info
    player.media_title = "Test Song"
    player.media_artist = "Test Artist"
    player.media_album = "Test Album"
    player.media_duration = 180
    player.media_position = 60
    player.media_image_url = "http://example.com/image.jpg"

    # Audio quality
    player.sample_rate = 44100
    player.bit_depth = 16
    player.bit_rate = 320
    player.audio_quality = "CD Quality"

    # Available options
    player.available_sources = ["spotify", "line-in", "optical"]
    player.eq_presets = ["flat", "rock", "jazz", "pop"]
    player.eq_preset = "flat"
    player.available_outputs = ["speaker", "bluetooth"]
    player.audio_output = "speaker"
    player.presets = None
    player.presets_full_data = None
    player.input_list = ["line-in", "optical"]

    # Capabilities
    player.supports_eq = True
    player.supports_presets = True
    player.supports_audio_output = True
    player.supports_queue_browse = True
    player.supports_queue_add = True
    player.supports_upnp = True
    player.supports_alarms = True
    player.supports_sleep_timer = True
    player.supports_led_control = True
    player.supports_firmware_install = True
    player.supports_enhanced_grouping = False
    player.supports_next_track = True
    player.supports_metadata = True

    # Firmware
    player.firmware_update_available = False
    player.latest_firmware_version = "1.0.0"

    # Device info (nested)
    player.device_info = MagicMock()
    player.device_info.mac = "AA:BB:CC:DD:EE:FF"
    player.device_info.firmware = "1.0.0"
    player.device_info.model_dump = MagicMock(return_value={"model": "WiiM Mini", "firmware": "1.0.0"})

    # UPnP
    player._upnp_client = None

    return player


@pytest.fixture
def mock_coordinator(mock_player):
    """Create a mock coordinator with properly mocked player."""
    coordinator = MagicMock()
    coordinator.data = {"player": mock_player}
    coordinator.last_update_success = True
    coordinator.update_interval = MagicMock()
    coordinator.update_interval.total_seconds.return_value = 5.0
    coordinator.player = mock_player
    return coordinator


class TestDiagnosticsUPnP:
    """Test UPnP client access in diagnostics."""

    @pytest.mark.asyncio
    async def test_diagnostics_handles_missing_upnp_client(
        self, hass, mock_config_entry, mock_device_entry, mock_coordinator
    ):
        """Test that diagnostics handles missing upnp_client gracefully."""
        from custom_components.wiim.const import DOMAIN

        # Setup: coordinator without upnp_client attribute
        mock_coordinator.player._upnp_client = None

        hass.data = {
            DOMAIN: {mock_config_entry.entry_id: {"coordinator": mock_coordinator, "entry": mock_config_entry}}
        }

        result = await async_get_device_diagnostics(hass, mock_config_entry, mock_device_entry)

        # Should not raise AttributeError
        assert "error" not in result or "upnp_client" not in str(result.get("error", ""))
        # UPnP info is now in connection_info
        assert "connection_info" in result
        assert result["connection_info"]["upnp_available"] is False

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

        hass.data = {
            DOMAIN: {mock_config_entry.entry_id: {"coordinator": mock_coordinator, "entry": mock_config_entry}}
        }

        result = await async_get_device_diagnostics(hass, mock_config_entry, mock_device_entry)

        assert "connection_info" in result
        assert result["connection_info"]["upnp_available"] is True

    @pytest.mark.asyncio
    async def test_diagnostics_upnp_client_missing_from_player(
        self, hass, mock_config_entry, mock_device_entry, mock_coordinator
    ):
        """Test diagnostics when player doesn't have _upnp_client."""
        from custom_components.wiim.const import DOMAIN

        # Remove _upnp_client attribute
        if hasattr(mock_coordinator.player, "_upnp_client"):
            delattr(mock_coordinator.player, "_upnp_client")

        hass.data = {
            DOMAIN: {mock_config_entry.entry_id: {"coordinator": mock_coordinator, "entry": mock_config_entry}}
        }

        result = await async_get_device_diagnostics(hass, mock_config_entry, mock_device_entry)

        assert "connection_info" in result
        assert result["connection_info"]["upnp_available"] is False

    @pytest.mark.asyncio
    async def test_diagnostics_handles_coordinator_none(self, hass, mock_config_entry, mock_device_entry):
        """Test diagnostics when coordinator is None."""
        from custom_components.wiim.const import DOMAIN

        # Set up hass.data with None coordinator
        hass.data = {DOMAIN: {mock_config_entry.entry_id: {"coordinator": None, "entry": mock_config_entry}}}

        result = await async_get_device_diagnostics(hass, mock_config_entry, mock_device_entry)

        # Should handle gracefully and return error
        assert "error" in result


class TestConfigEntryDiagnostics:
    """Test config entry diagnostics."""

    @pytest.mark.asyncio
    async def test_config_entry_diagnostics_success(self, hass, mock_config_entry, mock_coordinator):
        """Test config entry diagnostics with valid coordinator."""
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.diagnostics import async_get_config_entry_diagnostics

        hass.data = {
            DOMAIN: {mock_config_entry.entry_id: {"coordinator": mock_coordinator, "entry": mock_config_entry}}
        }

        with patch.object(hass.config_entries, "async_entries", return_value=[mock_config_entry]):
            result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

            assert "entry_data" in result
            assert "integration_overview" in result
            assert "coordinator" in result
            assert "this_device" in result
            assert "pywiim_version" in result
            assert result["integration_overview"]["total_devices"] >= 1

    @pytest.mark.asyncio
    async def test_config_entry_diagnostics_speaker_not_found(self, hass, mock_config_entry):
        """Test config entry diagnostics when coordinator not found."""
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.diagnostics import async_get_config_entry_diagnostics

        hass.data = {DOMAIN: {}}

        result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

        assert "error" in result or "entry_data" in result

    @pytest.mark.asyncio
    async def test_config_entry_diagnostics_coordinator_none(self, hass, mock_config_entry):
        """Test config entry diagnostics when coordinator is None (explicit)."""
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.diagnostics import async_get_config_entry_diagnostics

        # Coordinator exists but is None
        hass.data = {DOMAIN: {mock_config_entry.entry_id: {"coordinator": None, "entry": mock_config_entry}}}

        result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

        assert "error" in result
        assert result["error"] == "Coordinator not found for config entry"
        assert "entry_data" in result

    @pytest.mark.asyncio
    async def test_config_entry_diagnostics_with_group(self, hass, mock_config_entry, mock_coordinator):
        """Test config entry diagnostics with group information."""
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.diagnostics import async_get_config_entry_diagnostics

        # Setup master with group
        mock_coordinator.player.role = "master"
        mock_coordinator.player.is_master = True
        mock_coordinator.player.is_solo = False
        mock_coordinator.player.is_slave = False
        mock_coordinator.player.group = MagicMock()
        mock_coordinator.player.group.all_players = [mock_coordinator.player, MagicMock()]

        hass.data = {
            DOMAIN: {mock_config_entry.entry_id: {"coordinator": mock_coordinator, "entry": mock_config_entry}}
        }

        result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

        assert result["this_device"]["role"] == "master"

    @pytest.mark.asyncio
    async def test_config_entry_diagnostics_handles_exception(self, hass, mock_config_entry, mock_coordinator):
        """Test config entry diagnostics handles exceptions."""
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.diagnostics import async_get_config_entry_diagnostics

        mock_coordinator.player = None
        hass.data = {
            DOMAIN: {mock_config_entry.entry_id: {"coordinator": mock_coordinator, "entry": mock_config_entry}}
        }

        result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

        assert "error" in result or "entry_data" in result


class TestDeviceDiagnosticsContent:
    """Test device diagnostics content structure."""

    @pytest.mark.asyncio
    async def test_device_diagnostics_has_all_sections(
        self, hass, mock_config_entry, mock_device_entry, mock_coordinator
    ):
        """Test that device diagnostics includes all expected sections."""
        from custom_components.wiim.const import DOMAIN

        hass.data = {
            DOMAIN: {mock_config_entry.entry_id: {"coordinator": mock_coordinator, "entry": mock_config_entry}}
        }

        result = await async_get_device_diagnostics(hass, mock_config_entry, mock_device_entry)

        # Check all major sections exist
        expected_sections = [
            "pywiim_version",
            "device_info",
            "capabilities",
            "available_options",
            "group_info",
            "playback_state",
            "media_info",
            "audio_quality",
            "firmware_update",
            "connection_info",
            "coordinator_info",
            "raw_device_info",
        ]
        for section in expected_sections:
            assert section in result, f"Missing section: {section}"

    @pytest.mark.asyncio
    async def test_device_diagnostics_available_options(
        self, hass, mock_config_entry, mock_device_entry, mock_coordinator
    ):
        """Test that available_options section contains sources and EQ presets."""
        from custom_components.wiim.const import DOMAIN

        hass.data = {
            DOMAIN: {mock_config_entry.entry_id: {"coordinator": mock_coordinator, "entry": mock_config_entry}}
        }

        result = await async_get_device_diagnostics(hass, mock_config_entry, mock_device_entry)

        available_options = result["available_options"]
        assert "available_sources_raw" in available_options
        assert "available_sources_display" in available_options
        assert "eq_presets" in available_options
        assert "available_outputs" in available_options
        assert "current_eq_preset" in available_options

        # Check actual values
        assert available_options["available_sources_raw"] == ["spotify", "line-in", "optical"]
        assert available_options["eq_presets"] == ["flat", "rock", "jazz", "pop"]
        assert available_options["current_eq_preset"] == "flat"

    @pytest.mark.asyncio
    async def test_device_diagnostics_capabilities(self, hass, mock_config_entry, mock_device_entry, mock_coordinator):
        """Test that capabilities section has all expected flags."""
        from custom_components.wiim.const import DOMAIN

        hass.data = {
            DOMAIN: {mock_config_entry.entry_id: {"coordinator": mock_coordinator, "entry": mock_config_entry}}
        }

        result = await async_get_device_diagnostics(hass, mock_config_entry, mock_device_entry)

        capabilities = result["capabilities"]
        expected_capabilities = [
            "supports_eq",
            "supports_presets",
            "supports_audio_output",
            "supports_queue_browse",
            "supports_queue_add",
            "supports_upnp",
            "supports_alarms",
            "supports_sleep_timer",
            "supports_led_control",
            "supports_firmware_install",
            "supports_enhanced_grouping",
            "supports_next_track",
            "supports_metadata",
        ]
        for cap in expected_capabilities:
            assert cap in capabilities, f"Missing capability: {cap}"

    @pytest.mark.asyncio
    async def test_device_diagnostics_audio_quality(self, hass, mock_config_entry, mock_device_entry, mock_coordinator):
        """Test that audio_quality section is populated."""
        from custom_components.wiim.const import DOMAIN

        hass.data = {
            DOMAIN: {mock_config_entry.entry_id: {"coordinator": mock_coordinator, "entry": mock_config_entry}}
        }

        result = await async_get_device_diagnostics(hass, mock_config_entry, mock_device_entry)

        audio_quality = result["audio_quality"]
        assert audio_quality["sample_rate"] == 44100
        assert audio_quality["bit_depth"] == 16
        assert audio_quality["bit_rate"] == 320
        assert audio_quality["audio_quality"] == "CD Quality"


class TestConfigEntryRoleCounting:
    """Test role counting in config entry diagnostics."""

    @pytest.mark.asyncio
    async def test_config_entry_counts_master_role(self, hass, mock_config_entry, mock_coordinator):
        """Test that config entry diagnostics correctly counts master role."""
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.diagnostics import async_get_config_entry_diagnostics

        # Setup master
        mock_coordinator.player.role = "master"
        mock_coordinator.player.is_master = True
        mock_coordinator.player.is_solo = False
        mock_coordinator.player.is_slave = False

        hass.data = {
            DOMAIN: {mock_config_entry.entry_id: {"coordinator": mock_coordinator, "entry": mock_config_entry}}
        }

        # Mock async_entries to return our entry so get_all_coordinators works
        with patch.object(hass.config_entries, "async_entries", return_value=[mock_config_entry]):
            result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

        assert result["integration_overview"]["roles"]["master"] == 1
        assert result["integration_overview"]["roles"]["solo"] == 0

    @pytest.mark.asyncio
    async def test_config_entry_counts_slave_role(self, hass, mock_config_entry, mock_coordinator):
        """Test that config entry diagnostics correctly counts slave role."""
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.diagnostics import async_get_config_entry_diagnostics

        # Setup slave
        mock_coordinator.player.role = "slave"
        mock_coordinator.player.is_master = False
        mock_coordinator.player.is_solo = False
        mock_coordinator.player.is_slave = True

        hass.data = {
            DOMAIN: {mock_config_entry.entry_id: {"coordinator": mock_coordinator, "entry": mock_config_entry}}
        }

        # Mock async_entries to return our entry so get_all_coordinators works
        with patch.object(hass.config_entries, "async_entries", return_value=[mock_config_entry]):
            result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

        assert result["integration_overview"]["roles"]["slave"] == 1
        assert result["integration_overview"]["roles"]["solo"] == 0


class TestDeviceDiagnosticsPresets:
    """Test presets handling in device diagnostics."""

    @pytest.mark.asyncio
    async def test_device_diagnostics_with_presets(self, hass, mock_config_entry, mock_device_entry, mock_coordinator):
        """Test that presets are properly included in diagnostics."""
        from custom_components.wiim.const import DOMAIN

        # Create mock presets
        preset1 = MagicMock()
        preset1.key = 1
        preset1.name = "My Preset"
        preset1.url = "http://example.com/stream"

        preset2 = MagicMock()
        preset2.key = 2
        preset2.name = "Another Preset"
        # No URL attribute

        mock_coordinator.player.presets = [preset1, preset2]

        hass.data = {
            DOMAIN: {mock_config_entry.entry_id: {"coordinator": mock_coordinator, "entry": mock_config_entry}}
        }

        result = await async_get_device_diagnostics(hass, mock_config_entry, mock_device_entry)

        presets = result["available_options"]["presets"]
        assert len(presets) == 2
        assert presets[0]["key"] == 1
        assert presets[0]["name"] == "My Preset"
        assert presets[0]["url"] == "***redacted***"  # URL should be redacted
        assert presets[1]["key"] == 2
        assert presets[1]["name"] == "Another Preset"


class TestDeviceDiagnosticsGroupInfo:
    """Test group info in device diagnostics."""

    @pytest.mark.asyncio
    async def test_device_diagnostics_slave_with_master(self, hass, mock_config_entry, mock_device_entry, mock_coordinator):
        """Test that slave device shows master name in group info."""
        from custom_components.wiim.const import DOMAIN

        # Setup slave with group
        mock_coordinator.player.role = "slave"
        mock_coordinator.player.is_slave = True
        mock_coordinator.player.is_master = False
        mock_coordinator.player.is_solo = False

        # Create group with master
        mock_master = MagicMock()
        mock_master.name = "Living Room Master"
        mock_master.uuid = "master-uuid"

        mock_coordinator.player.group = MagicMock()
        mock_coordinator.player.group.all_players = [mock_master, mock_coordinator.player]
        mock_coordinator.player.group.master = mock_master

        hass.data = {
            DOMAIN: {mock_config_entry.entry_id: {"coordinator": mock_coordinator, "entry": mock_config_entry}}
        }

        result = await async_get_device_diagnostics(hass, mock_config_entry, mock_device_entry)

        group_info = result["group_info"]
        assert group_info["is_slave"] is True
        assert group_info["master_name"] == "Living Room Master"
        assert group_info["group_size"] == 2


class TestDeviceDiagnosticsConnectionType:
    """Test connection type detection in device diagnostics."""

    @pytest.mark.asyncio
    async def test_device_diagnostics_http_port(self, hass, mock_config_entry, mock_device_entry, mock_coordinator):
        """Test that port 80 is detected as HTTP."""
        from custom_components.wiim.const import DOMAIN

        mock_coordinator.player.port = 80

        hass.data = {
            DOMAIN: {mock_config_entry.entry_id: {"coordinator": mock_coordinator, "entry": mock_config_entry}}
        }

        result = await async_get_device_diagnostics(hass, mock_config_entry, mock_device_entry)

        assert result["connection_info"]["connection_type"] == "HTTP"

    @pytest.mark.asyncio
    async def test_device_diagnostics_custom_port(self, hass, mock_config_entry, mock_device_entry, mock_coordinator):
        """Test that non-standard port is shown as 'Port N'."""
        from custom_components.wiim.const import DOMAIN

        mock_coordinator.player.port = 8080

        hass.data = {
            DOMAIN: {mock_config_entry.entry_id: {"coordinator": mock_coordinator, "entry": mock_config_entry}}
        }

        result = await async_get_device_diagnostics(hass, mock_config_entry, mock_device_entry)

        assert result["connection_info"]["connection_type"] == "Port 8080"


class TestDeviceDiagnosticsErrorHandling:
    """Test error handling in device diagnostics."""

    @pytest.mark.asyncio
    async def test_device_diagnostics_device_info_serialization_error(
        self, hass, mock_config_entry, mock_device_entry, mock_coordinator
    ):
        """Test that device_info serialization errors are handled gracefully."""
        from custom_components.wiim.const import DOMAIN

        # Make model_dump raise an exception
        mock_coordinator.player.device_info.model_dump.side_effect = Exception("Serialization failed")

        hass.data = {
            DOMAIN: {mock_config_entry.entry_id: {"coordinator": mock_coordinator, "entry": mock_config_entry}}
        }

        result = await async_get_device_diagnostics(hass, mock_config_entry, mock_device_entry)

        # Should still succeed but with error message in raw_device_info
        assert "error" not in result
        assert result["raw_device_info"] == "Failed to serialize device_info"

    @pytest.mark.asyncio
    async def test_device_diagnostics_general_exception(self, hass, mock_config_entry, mock_device_entry):
        """Test that general exceptions are caught and return error."""
        from custom_components.wiim.const import DOMAIN

        # Create a coordinator that will cause an exception
        bad_coordinator = MagicMock()
        bad_coordinator.player = None  # This will cause AttributeError

        hass.data = {
            DOMAIN: {mock_config_entry.entry_id: {"coordinator": bad_coordinator, "entry": mock_config_entry}}
        }

        result = await async_get_device_diagnostics(hass, mock_config_entry, mock_device_entry)

        assert "error" in result
        assert "device_id" in result


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
