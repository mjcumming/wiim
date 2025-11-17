"""Unit tests for WiiM binary sensor platform."""

from unittest.mock import MagicMock, patch

import pytest


class TestBinarySensorConstants:
    """Test binary sensor platform constants."""

    async def test_conf_enable_network_monitoring(self):
        """Test network monitoring configuration constant."""
        from custom_components.wiim.const import CONF_ENABLE_NETWORK_MONITORING

        assert CONF_ENABLE_NETWORK_MONITORING == "enable_network_monitoring"

    def test_binary_sensor_device_class(self):
        """Test binary sensor device class constant."""
        from homeassistant.components.binary_sensor import BinarySensorDeviceClass

        assert BinarySensorDeviceClass.CONNECTIVITY == "connectivity"


class TestWiiMConnectivityBinarySensor:
    """Test WiiM Connectivity Binary Sensor."""

    def test_connectivity_sensor_creation(self):
        """Test connectivity binary sensor entity creation."""
        from custom_components.wiim.binary_sensor import WiiMConnectivityBinarySensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"

        sensor = WiiMConnectivityBinarySensor(speaker)

        assert sensor.speaker is speaker
        assert sensor.unique_id == "test-speaker-uuid_connected"
        assert sensor.name == "Connected"
        assert sensor.device_class == "connectivity"
        assert sensor.icon == "mdi:wifi"

    def test_connectivity_sensor_available(self):
        """Test connectivity sensor when speaker is available."""
        from custom_components.wiim.binary_sensor import WiiMConnectivityBinarySensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.ip = "192.168.1.100"
        speaker.available = True

        sensor = WiiMConnectivityBinarySensor(speaker)
        assert sensor.is_on is True

    def test_connectivity_sensor_unavailable(self):
        """Test connectivity sensor when speaker is unavailable."""
        from custom_components.wiim.binary_sensor import WiiMConnectivityBinarySensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.ip = "192.168.1.100"
        speaker.available = False

        sensor = WiiMConnectivityBinarySensor(speaker)
        assert sensor.is_on is False

    def test_connectivity_sensor_attributes_with_polling_info(self):
        """Test connectivity sensor attributes when polling info is available."""
        from custom_components.wiim.binary_sensor import WiiMConnectivityBinarySensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.ip = "192.168.1.100"
        speaker.available = True
        speaker.coordinator = MagicMock()
        speaker.coordinator.data = {
            "polling": {"is_playing": True, "interval": 5, "api_capabilities": {"statusex_supported": True}}
        }

        sensor = WiiMConnectivityBinarySensor(speaker)
        attrs = sensor.extra_state_attributes

        assert attrs["ip_address"] == "192.168.1.100"
        assert attrs["device_uuid"] == "test-speaker-uuid"
        assert attrs["is_playing"] is True
        assert attrs["polling_interval"] == 5
        assert attrs["api_capabilities"]["statusex_supported"] is True

    def test_connectivity_sensor_attributes_with_failure_count(self):
        """Test connectivity sensor attributes when failure count is available."""
        from custom_components.wiim.binary_sensor import WiiMConnectivityBinarySensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.ip = "192.168.1.100"
        speaker.available = False
        speaker.coordinator = MagicMock()
        speaker.coordinator.data = {}
        speaker.coordinator._consecutive_failures = 3

        sensor = WiiMConnectivityBinarySensor(speaker)
        attrs = sensor.extra_state_attributes

        assert attrs["ip_address"] == "192.168.1.100"
        assert attrs["device_uuid"] == "test-speaker-uuid"
        assert attrs["consecutive_failures"] == 3

    def test_connectivity_sensor_attributes_no_polling_info(self):
        """Test connectivity sensor attributes when no polling info is available."""
        from custom_components.wiim.binary_sensor import WiiMConnectivityBinarySensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.ip = "192.168.1.100"
        speaker.available = True
        speaker.coordinator = MagicMock()
        speaker.coordinator.data = {}

        sensor = WiiMConnectivityBinarySensor(speaker)
        attrs = sensor.extra_state_attributes

        assert attrs["ip_address"] == "192.168.1.100"
        assert attrs["device_uuid"] == "test-speaker-uuid"
        assert "is_playing" not in attrs
        assert "polling_interval" not in attrs
        assert "api_capabilities" not in attrs


class TestBinarySensorPlatformSetup:
    """Test binary sensor platform setup functionality."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_network_monitoring_enabled(self):
        """Test binary sensor platform setup when network monitoring is enabled."""
        from custom_components.wiim.binary_sensor import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry"

        # Mock speaker
        speaker = MagicMock()
        speaker.name = "Test WiiM"

        # Mock entry data with speaker and network monitoring enabled
        hass.data = {
            "wiim": {
                "test-entry": {"speaker": speaker, "entry": MagicMock(options={"enable_network_monitoring": True})}
            }
        }

        entities = []
        async_add_entities = MagicMock()

        await async_setup_entry(hass, config_entry, async_add_entities)

        # Verify entities were created
        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]

        # Should create connectivity binary sensor
        assert len(entities) == 1
        assert entities[0].__class__.__name__ == "WiiMConnectivityBinarySensor"

    @pytest.mark.asyncio
    async def test_async_setup_entry_network_monitoring_disabled(self):
        """Test binary sensor platform setup when network monitoring is disabled."""
        from custom_components.wiim.binary_sensor import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry"

        # Mock speaker
        speaker = MagicMock()
        speaker.name = "Test WiiM"

        with patch("custom_components.wiim.data.get_speaker_from_config_entry", return_value=speaker):
            # Mock entry data without network monitoring enabled
            hass.data = {
                "wiim": {
                    "test-entry": {"entry": MagicMock(options={"enable_network_monitoring": False}), "speaker": speaker}
                }
            }

            entities = []
            async_add_entities = MagicMock()

            await async_setup_entry(hass, config_entry, async_add_entities)

            # Verify entities were created
            async_add_entities.assert_called_once()
            entities = async_add_entities.call_args[0][0]

            # Should create no binary sensors
            assert len(entities) == 0

    @pytest.mark.asyncio
    async def test_async_setup_entry_no_options(self):
        """Test binary sensor platform setup with no options configured."""
        from custom_components.wiim.binary_sensor import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry"

        # Mock speaker
        speaker = MagicMock()
        speaker.name = "Test WiiM"

        with patch("custom_components.wiim.data.get_speaker_from_config_entry", return_value=speaker):
            # Mock entry data with no options
            hass.data = {"wiim": {"test-entry": {"entry": MagicMock(options={}), "speaker": speaker}}}

            entities = []
            async_add_entities = MagicMock()

            await async_setup_entry(hass, config_entry, async_add_entities)

            # Verify entities were created
            async_add_entities.assert_called_once()
            entities = async_add_entities.call_args[0][0]

            # Should create no binary sensors
            assert len(entities) == 0

    @pytest.mark.asyncio
    async def test_async_setup_entry_direct_data_access(self):
        """Test binary sensor platform setup with direct hass.data access."""
        from custom_components.wiim.binary_sensor import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry"

        # Mock speaker
        speaker = MagicMock()
        speaker.name = "Test WiiM"

        # Mock the direct data access pattern used in the code
        with patch("custom_components.wiim.data.get_speaker_from_config_entry", return_value=speaker):
            # Mock entry data with network monitoring enabled (direct access)
            hass.data = {
                "wiim": {
                    "test-entry": {"speaker": speaker, "entry": MagicMock(options={"enable_network_monitoring": True})}
                }
            }

            entities = []
            async_add_entities = MagicMock()

            await async_setup_entry(hass, config_entry, async_add_entities)

            # Verify entities were created
            async_add_entities.assert_called_once()
            entities = async_add_entities.call_args[0][0]

            # Should create connectivity binary sensor
            assert len(entities) == 1
            assert entities[0].__class__.__name__ == "WiiMConnectivityBinarySensor"
