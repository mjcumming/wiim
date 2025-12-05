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
        from homeassistant.config_entries import ConfigEntry
        from custom_components.wiim.binary_sensor import WiiMConnectivityBinarySensor

        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.host = "192.168.1.100"
        coordinator.last_update_success = True

        config_entry = MagicMock(spec=ConfigEntry)
        config_entry.unique_id = "test-uuid"
        config_entry.entry_id = "test-entry"

        sensor = WiiMConnectivityBinarySensor(coordinator, config_entry)

        assert sensor._attr_unique_id == "test-uuid_connected"
        assert sensor._attr_name == "Connected"
        assert sensor._attr_device_class.value == "connectivity"
        assert sensor._attr_icon == "mdi:wifi"

    def test_connectivity_sensor_available(self):
        """Test connectivity sensor when coordinator is available."""
        from homeassistant.config_entries import ConfigEntry
        from custom_components.wiim.binary_sensor import WiiMConnectivityBinarySensor

        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.host = "192.168.1.100"
        coordinator.last_update_success = True

        config_entry = MagicMock(spec=ConfigEntry)
        config_entry.unique_id = "test-uuid"
        config_entry.entry_id = "test-entry"

        sensor = WiiMConnectivityBinarySensor(coordinator, config_entry)

        assert sensor.is_on is True

    def test_connectivity_sensor_unavailable(self):
        """Test connectivity sensor when coordinator is unavailable."""
        from homeassistant.config_entries import ConfigEntry
        from custom_components.wiim.binary_sensor import WiiMConnectivityBinarySensor

        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.host = "192.168.1.100"
        coordinator.last_update_success = False

        config_entry = MagicMock(spec=ConfigEntry)
        config_entry.unique_id = "test-uuid"
        config_entry.entry_id = "test-entry"

        sensor = WiiMConnectivityBinarySensor(coordinator, config_entry)

        assert sensor.is_on is False

    def test_connectivity_sensor_attributes_with_polling_info(self):
        """Test connectivity sensor attributes when polling info is available."""
        from datetime import timedelta
        from homeassistant.config_entries import ConfigEntry
        from custom_components.wiim.binary_sensor import WiiMConnectivityBinarySensor

        player = MagicMock()
        player.host = "192.168.1.100"
        player.is_playing = False

        coordinator = MagicMock()
        coordinator.player = player
        coordinator.update_interval = timedelta(seconds=30)
        coordinator.last_update_success = True

        config_entry = MagicMock(spec=ConfigEntry)
        config_entry.unique_id = "test-uuid"
        config_entry.entry_id = "test-entry"

        sensor = WiiMConnectivityBinarySensor(coordinator, config_entry)
        attrs = sensor.extra_state_attributes

        assert attrs["ip_address"] == "192.168.1.100"
        assert attrs["device_uuid"] == "test-uuid"
        assert attrs["polling_interval"] == 30

    def test_connectivity_sensor_attributes_with_failure_count(self):
        """Test connectivity sensor attributes when is_playing is true."""
        from homeassistant.config_entries import ConfigEntry
        from custom_components.wiim.binary_sensor import WiiMConnectivityBinarySensor

        player = MagicMock()
        player.host = "192.168.1.100"
        player.is_playing = True

        coordinator = MagicMock()
        coordinator.player = player
        coordinator.update_interval = None
        coordinator.last_update_success = True

        config_entry = MagicMock(spec=ConfigEntry)
        config_entry.unique_id = "test-uuid"
        config_entry.entry_id = "test-entry"

        sensor = WiiMConnectivityBinarySensor(coordinator, config_entry)
        attrs = sensor.extra_state_attributes

        assert attrs["ip_address"] == "192.168.1.100"
        assert attrs["device_uuid"] == "test-uuid"
        assert attrs["is_playing"] is True

    def test_connectivity_sensor_attributes_no_polling_info(self):
        """Test connectivity sensor attributes when no polling info is available."""
        from homeassistant.config_entries import ConfigEntry
        from custom_components.wiim.binary_sensor import WiiMConnectivityBinarySensor

        player = MagicMock()
        player.host = "192.168.1.100"
        player.is_playing = False

        coordinator = MagicMock()
        coordinator.player = player
        coordinator.update_interval = None
        coordinator.last_update_success = True

        config_entry = MagicMock(spec=ConfigEntry)
        config_entry.unique_id = "test-uuid"
        config_entry.entry_id = "test-entry"

        sensor = WiiMConnectivityBinarySensor(coordinator, config_entry)
        attrs = sensor.extra_state_attributes

        assert attrs["ip_address"] == "192.168.1.100"
        assert attrs["device_uuid"] == "test-uuid"
        assert "polling_interval" not in attrs


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
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.binary_sensor import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry"
        config_entry.unique_id = "test-uuid"
        config_entry.data = {"host": "192.168.1.100"}
        config_entry.options = {"enable_network_monitoring": True}

        # Mock coordinator
        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.host = "192.168.1.100"
        coordinator.player.name = "Test WiiM"

        # Set up hass.data structure
        hass.data = {DOMAIN: {config_entry.entry_id: {"coordinator": coordinator, "entry": config_entry}}}

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
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.binary_sensor import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry"
        config_entry.unique_id = "test-uuid"
        config_entry.data = {"host": "192.168.1.100"}
        config_entry.options = {"enable_network_monitoring": True}

        # Mock coordinator
        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.host = "192.168.1.100"
        coordinator.player.name = "Test WiiM"

        # Set up hass.data structure (direct access pattern)
        hass.data = {DOMAIN: {config_entry.entry_id: {"coordinator": coordinator, "entry": config_entry}}}

        entities = []
        async_add_entities = MagicMock()

        await async_setup_entry(hass, config_entry, async_add_entities)

        # Verify entities were created
        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]

        # Should create connectivity binary sensor
        assert len(entities) == 1
        assert entities[0]._attr_unique_id == "test-uuid_connected"
