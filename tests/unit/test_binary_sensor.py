"""Unit tests for WiiM binary sensor platform."""

from unittest.mock import MagicMock, patch

import pytest


class TestBinarySensorConstants:
    """Test binary sensor configuration constants."""

    def test_conf_enable_network_monitoring(self):
        """Test network monitoring configuration constant."""
        from custom_components.wiim.const import CONF_ENABLE_NETWORK_MONITORING

        assert CONF_ENABLE_NETWORK_MONITORING == "enable_network_monitoring"


class TestWiiMConnectivityBinarySensor:
    """Test WiiM connectivity binary sensor entity."""

    def test_connectivity_sensor_creation(self):
        """Test connectivity binary sensor entity creation."""
        from custom_components.wiim.binary_sensor import WiiMConnectivityBinarySensor

        speaker = MagicMock()
        speaker.uuid = "test-uuid"
        speaker.available = True
        speaker.ip = "192.168.1.100"

        sensor = WiiMConnectivityBinarySensor(speaker)

        assert sensor._attr_unique_id == "test-uuid_connected"
        assert sensor._attr_name == "Connected"
        assert sensor._attr_device_class.value == "connectivity"
        assert sensor._attr_icon == "mdi:wifi"

    def test_connectivity_sensor_available(self):
        """Test connectivity sensor when speaker is available."""
        from custom_components.wiim.binary_sensor import WiiMConnectivityBinarySensor

        speaker = MagicMock()
        speaker.uuid = "test-uuid"
        speaker.available = True

        sensor = WiiMConnectivityBinarySensor(speaker)

        assert sensor.is_on is True

    def test_connectivity_sensor_unavailable(self):
        """Test connectivity sensor when speaker is unavailable."""
        from custom_components.wiim.binary_sensor import WiiMConnectivityBinarySensor

        speaker = MagicMock()
        speaker.uuid = "test-uuid"
        speaker.available = False

        sensor = WiiMConnectivityBinarySensor(speaker)

        assert sensor.is_on is False

    def test_connectivity_sensor_attributes_with_polling_info(self):
        """Test connectivity sensor attributes when polling info is available."""
        from datetime import timedelta

        from custom_components.wiim.binary_sensor import WiiMConnectivityBinarySensor

        speaker = MagicMock()
        speaker.uuid = "test-uuid"
        speaker.ip = "192.168.1.100"
        speaker.available = True

        coordinator = MagicMock()
        coordinator.data = {"player": None}
        coordinator.update_interval = timedelta(seconds=30)
        coordinator._consecutive_failures = 0

        speaker.coordinator = coordinator

        sensor = WiiMConnectivityBinarySensor(speaker)
        attrs = sensor.extra_state_attributes

        assert attrs["ip_address"] == "192.168.1.100"
        assert attrs["device_uuid"] == "test-uuid"
        assert attrs["polling_interval"] == 30

    def test_connectivity_sensor_attributes_with_failure_count(self):
        """Test connectivity sensor attributes when failure count is available."""
        from custom_components.wiim.binary_sensor import WiiMConnectivityBinarySensor

        speaker = MagicMock()
        speaker.uuid = "test-uuid"
        speaker.ip = "192.168.1.100"
        speaker.available = True

        player = MagicMock()
        player.play_state = "play"

        coordinator = MagicMock()
        coordinator.data = {"player": player}
        coordinator.update_interval = None
        coordinator._consecutive_failures = 3

        speaker.coordinator = coordinator

        sensor = WiiMConnectivityBinarySensor(speaker)
        attrs = sensor.extra_state_attributes

        assert attrs["ip_address"] == "192.168.1.100"
        assert attrs["device_uuid"] == "test-uuid"
        assert attrs["is_playing"] is True
        assert attrs["consecutive_failures"] == 3

    def test_connectivity_sensor_attributes_no_polling_info(self):
        """Test connectivity sensor attributes when no polling info is available."""
        from custom_components.wiim.binary_sensor import WiiMConnectivityBinarySensor

        # Use a simple object instead of MagicMock to avoid auto-created attributes
        class SimpleCoordinator:
            def __init__(self):
                self.data = {}
                self.update_interval = None

        speaker = MagicMock()
        speaker.uuid = "test-uuid"
        speaker.ip = "192.168.1.100"
        speaker.available = True
        speaker.coordinator = SimpleCoordinator()

        sensor = WiiMConnectivityBinarySensor(speaker)
        attrs = sensor.extra_state_attributes

        assert attrs["ip_address"] == "192.168.1.100"
        assert attrs["device_uuid"] == "test-uuid"
        assert "polling_interval" not in attrs
        assert "consecutive_failures" not in attrs


class TestBinarySensorPlatformSetup:
    """Test binary sensor platform setup functionality."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_returns_empty_list(self):
        """Test binary sensor platform setup returns empty entity list."""
        from custom_components.wiim.binary_sensor import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry"
        config_entry.data = {"host": "192.168.1.100"}
        config_entry.options = {}  # Network monitoring disabled by default

        async_add_entities = MagicMock()

        await async_setup_entry(hass, config_entry, async_add_entities)

        # Verify entities were created (should be empty list)
        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]

        # Should create no binary sensors
        assert len(entities) == 0

    @pytest.mark.asyncio
    async def test_async_setup_entry_network_monitoring_enabled(self):
        """Test binary sensor platform setup when network monitoring is enabled."""
        from custom_components.wiim.binary_sensor import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry"
        config_entry.data = {"host": "192.168.1.100"}

        # Mock speaker
        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-uuid"

        # Mock entry data with speaker and network monitoring enabled
        with patch("custom_components.wiim.data.get_speaker_from_config_entry", return_value=speaker):
            config_entry.options = {"enable_network_monitoring": True}

            entities = []
            async_add_entities = MagicMock()

            await async_setup_entry(hass, config_entry, async_add_entities)

            # Verify entities were created
            async_add_entities.assert_called_once()
            entities = async_add_entities.call_args[0][0]

            # Should create connectivity binary sensor
            assert len(entities) == 1
            assert entities[0]._attr_unique_id == "test-uuid_connected"

    @pytest.mark.asyncio
    async def test_async_setup_entry_direct_data_access(self):
        """Test binary sensor platform setup with direct hass.data access."""
        from custom_components.wiim.binary_sensor import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry"
        config_entry.data = {"host": "192.168.1.100"}

        # Mock speaker
        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-uuid"

        # Mock the direct data access pattern used in the code
        with patch("custom_components.wiim.data.get_speaker_from_config_entry", return_value=speaker):
            # Mock entry data with network monitoring enabled (direct access)
            config_entry.options = {"enable_network_monitoring": True}

            entities = []
            async_add_entities = MagicMock()

            await async_setup_entry(hass, config_entry, async_add_entities)

            # Verify entities were created
            async_add_entities.assert_called_once()
            entities = async_add_entities.call_args[0][0]

            # Should create connectivity binary sensor
            assert len(entities) == 1
            assert entities[0]._attr_unique_id == "test-uuid_connected"
