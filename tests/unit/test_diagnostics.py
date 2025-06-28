"""Test WiiM diagnostics functionality."""

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from custom_components.wiim.diagnostics import (
    TO_REDACT,
    async_get_config_entry_diagnostics,
    async_get_device_diagnostics,
)


@pytest.fixture
def mock_speaker():
    """Create a mock speaker with all required attributes."""
    speaker = MagicMock()
    speaker.uuid = "test-uuid-123"
    speaker.name = "Test Speaker"
    speaker.model = "WiiM Pro"
    speaker.firmware = "1.2.3"
    speaker.role = "master"
    speaker.available = True
    speaker.ip_address = "192.168.1.100"
    speaker.mac_address = "AA:BB:CC:DD:EE:FF"
    speaker.group_members = []
    speaker.coordinator_speaker = None
    speaker.is_group_coordinator = True

    # Mock coordinator
    speaker.coordinator = MagicMock()
    speaker.coordinator.update_interval.total_seconds.return_value = 30.0
    speaker.coordinator.last_update_success = True
    speaker.coordinator.last_update_time.isoformat.return_value = "2024-01-01T12:00:00"
    speaker.coordinator.data = {"test": "data", "status_model": MagicMock()}
    speaker.coordinator.client.host = "192.168.1.100"

    # Mock media methods
    speaker.get_playback_state.return_value = "playing"
    speaker.get_volume_level.return_value = 0.5
    speaker.is_volume_muted.return_value = False
    speaker.get_current_source.return_value = "AirPlay"
    speaker.get_media_title.return_value = "Test Song"
    speaker.get_media_artist.return_value = "Test Artist"
    speaker.get_media_album.return_value = "Test Album"
    speaker.get_media_duration.return_value = 180
    speaker.get_media_position.return_value = 60
    speaker.get_shuffle_state.return_value = False
    speaker.get_repeat_mode.return_value = "off"
    speaker.get_sound_mode.return_value = "Music"

    # Mock Pydantic models
    status_model = MagicMock()
    status_model.model_dump.return_value = {"status": "test"}
    speaker.status_model = status_model

    device_model = MagicMock()
    device_model.model_dump.return_value = {"device": "test"}
    speaker.device_model = device_model

    return speaker


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.data = {"host": "192.168.1.100"}
    entry.options = {"update_rate": 30}
    entry.unique_id = "test-uuid-123"
    entry.title = "Test Speaker"
    return entry


@pytest.fixture
def mock_device_entry():
    """Create a mock device entry."""
    device = MagicMock(spec=DeviceEntry)
    device.id = "test-device-id"
    return device


class TestDiagnosticsRedaction:
    """Test data redaction functionality."""

    def test_redaction_list_comprehensive(self):
        """Test that our redaction list covers common sensitive fields."""
        expected_fields = [
            "MAC",
            "mac_address",
            "macaddress",
            "ip_address",
            "host",
            "SSID",
            "ssid",
            "bssid",
            "BSSID",
            "wifi_password",
            "password",
            "token",
            "auth",
            "serial",
            "serialnumber",
            "uuid",
            "deviceid",
            "device_id",
        ]

        for field in expected_fields:
            assert field in TO_REDACT, f"Field '{field}' should be in TO_REDACT list"

    def test_sensitive_data_redaction(self):
        """Test that sensitive data gets properly redacted."""
        sensitive_data = {
            "MAC": "AA:BB:CC:DD:EE:FF",
            "ip_address": "192.168.1.100",
            "SSID": "MyNetwork",
            "password": "secret123",
            "safe_field": "this_is_ok",
        }

        redacted = async_redact_data(sensitive_data, TO_REDACT)

        assert "**REDACTED**" in str(redacted["MAC"])
        assert "**REDACTED**" in str(redacted["ip_address"])
        assert "**REDACTED**" in str(redacted["SSID"])
        assert "**REDACTED**" in str(redacted["password"])
        assert redacted["safe_field"] == "this_is_ok"


class TestConfigEntryDiagnostics:
    """Test config entry diagnostics functionality."""

    @patch("custom_components.wiim.diagnostics.get_speaker_from_config_entry")
    @patch("custom_components.wiim.diagnostics.get_all_speakers")
    async def test_config_entry_diagnostics_success(
        self, mock_get_all_speakers, mock_get_speaker, mock_speaker, mock_config_entry
    ):
        """Test successful config entry diagnostics generation."""
        hass = MagicMock(spec=HomeAssistant)

        # Setup mocks
        mock_get_speaker.return_value = mock_speaker
        mock_get_all_speakers.return_value = [mock_speaker]

        # Run diagnostics
        result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

        # Verify structure
        assert "entry_data" in result
        assert "entry_options" in result
        assert "integration_info" in result
        assert "coordinator" in result
        assert "speaker_basic" in result

        # Verify integration info
        integration_info = result["integration_info"]
        assert integration_info["total_speakers"] == 1
        assert integration_info["available_speakers"] == 1
        assert "master" in integration_info["roles"]
        assert integration_info["models"] == ["WiiM Pro"]

        # Verify coordinator info
        coordinator = result["coordinator"]
        assert coordinator["update_interval"] == 30.0
        assert coordinator["last_update_success"] is True
        assert coordinator["client_host"] == "192.168.1.100"

        # Verify speaker basic info
        speaker_basic = result["speaker_basic"]
        assert speaker_basic["name"] == "Test Speaker"
        assert speaker_basic["model"] == "WiiM Pro"
        assert speaker_basic["role"] == "master"
        assert speaker_basic["available"] is True

    @patch("custom_components.wiim.diagnostics.get_speaker_from_config_entry")
    async def test_config_entry_diagnostics_no_speaker(self, mock_get_speaker, mock_config_entry):
        """Test config entry diagnostics when speaker not found."""
        hass = MagicMock(spec=HomeAssistant)
        mock_get_speaker.return_value = None

        result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

        assert "error" in result
        assert result["error"] == "Speaker not found for config entry"
        assert "entry_data" in result
        assert "entry_options" in result

    @patch("custom_components.wiim.diagnostics.get_speaker_from_config_entry")
    async def test_config_entry_diagnostics_exception(self, mock_get_speaker, mock_config_entry):
        """Test config entry diagnostics with exception handling."""
        hass = MagicMock(spec=HomeAssistant)
        mock_get_speaker.side_effect = Exception("Test error")

        result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

        assert "error" in result
        assert "Failed to generate diagnostics: Test error" in result["error"]
        assert "entry_data" in result


class TestDeviceDiagnostics:
    """Test device diagnostics functionality."""

    @patch("custom_components.wiim.diagnostics.get_speaker_from_config_entry")
    async def test_device_diagnostics_success(
        self, mock_get_speaker, mock_speaker, mock_config_entry, mock_device_entry
    ):
        """Test successful device diagnostics generation."""
        hass = MagicMock(spec=HomeAssistant)
        mock_get_speaker.return_value = mock_speaker

        result = await async_get_device_diagnostics(hass, mock_config_entry, mock_device_entry)

        # Verify main sections
        assert "device_info" in result
        assert "group_info" in result
        assert "media_info" in result
        assert "api_status" in result
        assert "model_data" in result
        assert "raw_coordinator_data" in result

        # Verify device info
        device_info = result["device_info"]
        assert device_info["speaker_uuid"] == "test-uuid-123"
        assert device_info["name"] == "Test Speaker"
        assert device_info["model"] == "WiiM Pro"
        assert device_info["role"] == "master"
        assert device_info["available"] is True
        # IP and MAC should be redacted
        assert "ip" in device_info["ip_address"]
        assert "mac" in device_info["mac_address"]

        # Verify group info
        group_info = result["group_info"]
        assert group_info["role"] == "master"
        assert group_info["is_group_coordinator"] is True
        assert group_info["group_members_count"] == 0

        # Verify media info
        media_info = result["media_info"]
        assert media_info["playback_state"] == "playing"
        assert media_info["volume_level"] == 0.5
        assert media_info["media_title"] == "Test Song"
        assert media_info["current_source"] == "AirPlay"

        # Verify model data
        model_data = result["model_data"]
        assert "status_model" in model_data
        assert "device_model" in model_data

    @patch("custom_components.wiim.diagnostics.get_speaker_from_config_entry")
    async def test_device_diagnostics_no_speaker(self, mock_get_speaker, mock_config_entry, mock_device_entry):
        """Test device diagnostics when speaker not found."""
        hass = MagicMock(spec=HomeAssistant)
        mock_get_speaker.return_value = None

        result = await async_get_device_diagnostics(hass, mock_config_entry, mock_device_entry)

        assert "error" in result
        assert result["error"] == "Speaker not found for device"

    @patch("custom_components.wiim.diagnostics.get_speaker_from_config_entry")
    async def test_device_diagnostics_exception(self, mock_get_speaker, mock_config_entry, mock_device_entry):
        """Test device diagnostics with exception handling."""
        hass = MagicMock(spec=HomeAssistant)
        mock_get_speaker.side_effect = Exception("Test error")

        result = await async_get_device_diagnostics(hass, mock_config_entry, mock_device_entry)

        assert "error" in result
        assert "Failed to generate device diagnostics: Test error" in result["error"]
        assert result["device_id"] == "test-device-id"


class TestDiagnosticsIntegration:
    """Test diagnostics integration with real-world scenarios."""

    @patch("custom_components.wiim.diagnostics.get_speaker_from_config_entry")
    @patch("custom_components.wiim.diagnostics.get_all_speakers")
    async def test_multiroom_diagnostics(self, mock_get_all_speakers, mock_get_speaker, mock_config_entry):
        """Test diagnostics with multiroom setup."""
        hass = MagicMock(spec=HomeAssistant)

        # Create master and slave speakers
        master = MagicMock()
        master.role = "master"
        master.available = True
        master.model = "WiiM Pro"
        master.coordinator = MagicMock()
        master.coordinator.update_interval.total_seconds.return_value = 30.0
        master.coordinator.last_update_success = True
        master.coordinator.data = {}
        master.coordinator.client.host = "192.168.1.100"

        slave = MagicMock()
        slave.role = "slave"
        slave.available = True
        slave.model = "WiiM Mini"

        mock_get_speaker.return_value = master
        mock_get_all_speakers.return_value = [master, slave]

        result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

        integration_info = result["integration_info"]
        assert integration_info["total_speakers"] == 2
        assert integration_info["available_speakers"] == 2
        assert integration_info["roles"]["master"] == 1
        assert integration_info["roles"]["slave"] == 1
        assert "WiiM Pro" in integration_info["models"]
        assert "WiiM Mini" in integration_info["models"]


class TestArtworkDiagnostics:
    """Test artwork-specific diagnostics for older LinkPlay device compatibility."""

    @patch("custom_components.wiim.diagnostics.get_speaker_from_config_entry")
    async def test_artwork_diagnostics_working(
        self, mock_get_speaker, mock_speaker, mock_config_entry, mock_device_entry
    ):
        """Test artwork diagnostics when artwork is working."""
        hass = MagicMock(spec=HomeAssistant)

        # Mock speaker with working artwork
        mock_speaker.get_media_image_url.return_value = "http://example.com/art.jpg"
        mock_get_speaker.return_value = mock_speaker

        result = await async_get_device_diagnostics(hass, mock_config_entry, mock_device_entry)

        # Verify artwork is included in media_info
        media_info = result["media_info"]
        assert media_info["media_image_url"] == "http://example.com/art.jpg"

    @patch("custom_components.wiim.diagnostics.get_speaker_from_config_entry")
    async def test_artwork_diagnostics_older_device(
        self, mock_get_speaker, mock_speaker, mock_config_entry, mock_device_entry
    ):
        """Test artwork diagnostics for older LinkPlay device (GitHub issue #40)."""
        hass = MagicMock(spec=HomeAssistant)

        # Mock speaker for older device without artwork
        mock_speaker.get_media_image_url.return_value = None
        mock_get_speaker.return_value = mock_speaker

        result = await async_get_device_diagnostics(hass, mock_config_entry, mock_device_entry)

        # Verify no artwork in media_info
        media_info = result["media_info"]
        assert media_info["media_image_url"] is None
