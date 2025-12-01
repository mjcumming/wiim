"""Unit tests for WiiM System Health - testing health check functionality."""

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.wiim.system_health import system_health_info


class TestSystemHealth:
    """Test system health functionality."""

    @pytest.mark.asyncio
    async def test_system_health_info(self, hass: HomeAssistant):
        """Test system health info callback."""
        # Mock config entries and speakers
        mock_entry = MagicMock()
        mock_entry.domain = "wiim"

        with patch.object(hass.config_entries, "async_entries", return_value=[mock_entry]):
            with patch("custom_components.wiim.system_health.get_all_speakers", return_value=[]):
                # Call the system health info function
                health_info = await system_health_info(hass)

                # Should return health information dictionary
                assert isinstance(health_info, dict)

                # Should contain relevant health information
                assert "configured_devices" in health_info
                assert "reachable_devices" in health_info
                assert "pywiim_version" in health_info

    @pytest.mark.asyncio
    async def test_system_health_with_speakers(self, hass: HomeAssistant):
        """Test system health with actual speakers."""
        from unittest.mock import MagicMock, patch

        from custom_components.wiim.system_health import system_health_info

        # Create mock speakers
        mock_speaker1 = MagicMock()
        mock_speaker1.available = True
        mock_speaker1.coordinator = MagicMock()
        mock_speaker1.coordinator.data = {"player": MagicMock()}
        mock_speaker1.coordinator.data["player"].is_master = True
        mock_speaker1.coordinator.data["player"].is_slave = False

        mock_speaker2 = MagicMock()
        mock_speaker2.available = False
        mock_speaker2.coordinator = MagicMock()
        mock_speaker2.coordinator.data = {"player": MagicMock()}
        mock_speaker2.coordinator.data["player"].is_master = False
        mock_speaker2.coordinator.data["player"].is_slave = True

        mock_entry = MagicMock()
        mock_entry.domain = "wiim"

        with patch.object(hass.config_entries, "async_entries", return_value=[mock_entry]):
            with patch(
                "custom_components.wiim.system_health.get_all_speakers", return_value=[mock_speaker1, mock_speaker2]
            ):
                health_info = await system_health_info(hass)

                assert health_info["configured_devices"] == 1
                assert health_info["reachable_devices"] == "1/2"
                assert health_info["multiroom_masters"] == 1
                assert health_info["multiroom_slaves"] == 1

    @pytest.mark.asyncio
    async def test_system_health_device_health_check(self, hass: HomeAssistant):
        """Test system health device health check."""
        from unittest.mock import AsyncMock, MagicMock

        from custom_components.wiim.system_health import _check_device_health

        mock_speaker = MagicMock()
        mock_speaker.coordinator = MagicMock()
        mock_speaker.coordinator.player = MagicMock()
        mock_speaker.coordinator.player.get_device_info = AsyncMock()
        mock_speaker.coordinator.update_interval = MagicMock()
        mock_speaker.coordinator.update_interval.total_seconds = MagicMock(return_value=5.0)

        health = await _check_device_health(mock_speaker)

        assert "OK" in health
        assert "polling" in health
        mock_speaker.coordinator.player.get_device_info.assert_called_once()

    @pytest.mark.asyncio
    async def test_system_health_device_health_check_error(self, hass: HomeAssistant):
        """Test system health device health check with error."""
        from unittest.mock import AsyncMock, MagicMock

        from custom_components.wiim.system_health import _check_device_health

        mock_speaker = MagicMock()
        mock_speaker.coordinator = MagicMock()
        mock_speaker.coordinator.player = MagicMock()
        mock_speaker.coordinator.player.get_device_info = AsyncMock(side_effect=Exception("Connection error"))

        health = await _check_device_health(mock_speaker)

        assert "Error" in health
        assert "Connection error" in health

    @pytest.mark.asyncio
    async def test_system_health_pywiim_version(self, hass: HomeAssistant):
        """Test system health includes pywiim version."""
        from unittest.mock import MagicMock, patch

        from custom_components.wiim.system_health import system_health_info

        mock_entry = MagicMock()
        mock_entry.domain = "wiim"

        with patch.object(hass.config_entries, "async_entries", return_value=[mock_entry]):
            with patch("custom_components.wiim.system_health.get_all_speakers", return_value=[]):
                with patch("importlib.metadata.version", return_value="1.0.0"):
                    health_info = await system_health_info(hass)

                    assert health_info["pywiim_version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_system_health_pywiim_version_not_found(self, hass: HomeAssistant):
        """Test system health handles missing pywiim version."""
        from importlib.metadata import PackageNotFoundError
        from unittest.mock import MagicMock, patch

        from custom_components.wiim.system_health import system_health_info

        mock_entry = MagicMock()
        mock_entry.domain = "wiim"

        with patch.object(hass.config_entries, "async_entries", return_value=[mock_entry]):
            with patch("custom_components.wiim.system_health.get_all_speakers", return_value=[]):
                with patch("importlib.metadata.version", side_effect=PackageNotFoundError("pywiim")):
                    health_info = await system_health_info(hass)

                    assert health_info["pywiim_version"] == "unknown"
