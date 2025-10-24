"""Unit tests for WiiM system health."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestSystemHealthRegistration:
    """Test system health registration functionality."""

    def test_async_register_function(self):
        """Test async_register callback function."""
        from custom_components.wiim.system_health import async_register

        # Mock system health registration
        mock_register = MagicMock()
        mock_hass = MagicMock()

        # Call the registration function
        async_register(mock_hass, mock_register)

        # Verify that the info function was registered
        mock_register.async_register_info.assert_called_once()
        registered_func = mock_register.async_register_info.call_args[0][0]
        assert registered_func.__name__ == "system_health_info"


class TestSystemHealthInfo:
    """Test system health info functionality."""

    @pytest.mark.asyncio
    async def test_system_health_info_no_entries(self):
        """Test system health info when no config entries exist."""
        from custom_components.wiim.system_health import system_health_info

        # Mock Home Assistant with no entries
        hass = MagicMock()
        hass.config_entries.async_entries.return_value = []

        with patch("custom_components.wiim.system_health.get_all_speakers", return_value=[]):
            result = await system_health_info(hass)

            expected = {
                "configured_devices": 0,
                "reachable_devices": "0/0",
                "multiroom_masters": 0,
                "multiroom_slaves": 0,
                "first_device_api": None,
                "integration_version": "2.0.0",
            }
            assert result == expected

    @pytest.mark.asyncio
    async def test_system_health_info_with_entries_and_speakers(self):
        """Test system health info with config entries and speakers."""
        from custom_components.wiim.system_health import system_health_info

        # Mock config entries
        mock_entry1 = MagicMock()
        mock_entry1.entry_id = "entry1"
        mock_entry2 = MagicMock()
        mock_entry2.entry_id = "entry2"

        hass = MagicMock()
        hass.config_entries.async_entries.return_value = [mock_entry1, mock_entry2]

        # Mock speakers
        mock_speaker1 = MagicMock()
        mock_speaker1.available = True
        mock_speaker1.role = "master"
        mock_speaker1.coordinator = MagicMock()
        mock_speaker1.coordinator.client = MagicMock()
        mock_speaker1.coordinator.client.get_device_info = AsyncMock()
        mock_speaker1.coordinator.update_interval = MagicMock()
        mock_speaker1.coordinator.update_interval.total_seconds.return_value = 5.0

        mock_speaker2 = MagicMock()
        mock_speaker2.available = False
        mock_speaker2.role = "slave"

        mock_speaker3 = MagicMock()
        mock_speaker3.available = True
        mock_speaker3.role = "solo"

        with patch(
            "custom_components.wiim.system_health.get_all_speakers",
            return_value=[mock_speaker1, mock_speaker2, mock_speaker3],
        ):
            result = await system_health_info(hass)

            expected = {
                "configured_devices": 2,
                "reachable_devices": "2/3",  # 2 out of 3 speakers are available
                "multiroom_masters": 1,
                "multiroom_slaves": 1,
                "first_device_api": "OK (polling: 5.0s)",  # First device health check succeeds
                "integration_version": "2.0.0",
            }
            assert result == expected

    @pytest.mark.asyncio
    async def test_system_health_info_with_device_health_check(self):
        """Test system health info with device health check."""
        from custom_components.wiim.system_health import system_health_info

        # Mock config entry and speaker
        mock_entry = MagicMock()
        mock_entry.entry_id = "entry1"

        hass = MagicMock()
        hass.config_entries.async_entries.return_value = [mock_entry]

        # Mock speaker with successful API call
        mock_speaker = MagicMock()
        mock_speaker.available = True
        mock_speaker.role = "solo"
        mock_speaker.coordinator = MagicMock()
        mock_speaker.coordinator.client = MagicMock()
        mock_speaker.coordinator.client.get_device_info = AsyncMock()
        mock_speaker.coordinator.update_interval = MagicMock()
        mock_speaker.coordinator.update_interval.total_seconds.return_value = 5.0

        with patch("custom_components.wiim.system_health.get_all_speakers", return_value=[mock_speaker]):
            result = await system_health_info(hass)

            # Verify API call was made
            mock_speaker.coordinator.client.get_device_info.assert_called_once()

            # Check that first device API health is included
            assert "first_device_api" in result
            assert result["first_device_api"] == "OK (polling: 5.0s)"

    @pytest.mark.asyncio
    async def test_system_health_info_with_device_health_error(self):
        """Test system health info when device health check fails."""
        from custom_components.wiim.system_health import system_health_info

        # Mock config entry and speaker
        mock_entry = MagicMock()
        mock_entry.entry_id = "entry1"

        hass = MagicMock()
        hass.config_entries.async_entries.return_value = [mock_entry]

        # Mock speaker with API error
        mock_speaker = MagicMock()
        mock_speaker.available = True
        mock_speaker.role = "solo"
        mock_speaker.coordinator = MagicMock()
        mock_speaker.coordinator.client = MagicMock()
        mock_speaker.coordinator.client.get_device_info = AsyncMock(side_effect=Exception("Connection timeout"))

        with patch("custom_components.wiim.system_health.get_all_speakers", return_value=[mock_speaker]):
            result = await system_health_info(hass)

            # Verify API call was attempted
            mock_speaker.coordinator.client.get_device_info.assert_called_once()

            # Check that error is reported
            assert "first_device_api" in result
            assert "Error:" in result["first_device_api"]
            assert "Connection timeout" in result["first_device_api"]


class TestDeviceHealthCheck:
    """Test device health check functionality."""

    @pytest.mark.asyncio
    async def test_check_device_health_success(self):
        """Test device health check with successful API call."""
        from custom_components.wiim.system_health import _check_device_health

        # Mock speaker with successful API
        mock_speaker = MagicMock()
        mock_speaker.coordinator = MagicMock()
        mock_speaker.coordinator.client = MagicMock()
        mock_speaker.coordinator.client.get_device_info = AsyncMock()
        mock_speaker.coordinator.update_interval = MagicMock()
        mock_speaker.coordinator.update_interval.total_seconds.return_value = 10.0

        result = await _check_device_health(mock_speaker)

        # Should return success message with polling interval
        assert result == "OK (polling: 10.0s)"

    @pytest.mark.asyncio
    async def test_check_device_health_api_error(self):
        """Test device health check with API error."""
        from custom_components.wiim.system_health import _check_device_health

        # Mock speaker with API error
        mock_speaker = MagicMock()
        mock_speaker.coordinator = MagicMock()
        mock_speaker.coordinator.client = MagicMock()
        mock_speaker.coordinator.client.get_device_info = AsyncMock(side_effect=Exception("Network unreachable"))

        result = await _check_device_health(mock_speaker)

        # Should return error message (truncated to 50 chars)
        assert result == "Error: Network unreachable"

    @pytest.mark.asyncio
    async def test_check_device_health_long_error_message(self):
        """Test device health check with long error message."""
        from custom_components.wiim.system_health import _check_device_health

        # Mock speaker with long error message
        long_error = "This is a very long error message that should be truncated to 50 characters"
        mock_speaker = MagicMock()
        mock_speaker.coordinator = MagicMock()
        mock_speaker.coordinator.client = MagicMock()
        mock_speaker.coordinator.client.get_device_info = AsyncMock(side_effect=Exception(long_error))

        result = await _check_device_health(mock_speaker)

        # Should truncate error message to 50 characters
        assert result == f"Error: {long_error[:50]}"


class TestSystemHealthIntegration:
    """Test system health integration with Home Assistant."""

    def test_system_health_registration_with_hass(self):
        """Test system health registration with Home Assistant instance."""
        from custom_components.wiim.system_health import async_register

        # Mock Home Assistant and system health
        mock_hass = MagicMock()
        mock_register = MagicMock()

        # Register the system health info
        async_register(mock_hass, mock_register)

        # Verify registration was called
        mock_register.async_register_info.assert_called_once()

        # Verify the registered function is our system_health_info
        registered_func = mock_register.async_register_info.call_args[0][0]
        assert registered_func.__name__ == "system_health_info"

    def test_system_health_info_function_signature(self):
        """Test system health info function signature."""
        from custom_components.wiim.system_health import system_health_info

        # Check that the function is async and has correct signature
        import inspect

        sig = inspect.signature(system_health_info)
        params = list(sig.parameters.keys())

        assert "hass" in params
        # Check that return annotation is a dict type (string representation may vary)
        assert "dict" in str(sig.return_annotation)
