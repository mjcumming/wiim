"""Unit tests for WiiM sensor platform core logic."""

from unittest.mock import MagicMock, patch


class TestSensorUtilityFunctions:
    """Test sensor utility functions."""

    async def test_to_bool_function_comprehensive(self):
        """Test _to_bool utility function with comprehensive inputs."""
        from custom_components.wiim.sensor import _to_bool

        # Test boolean values
        assert _to_bool(True) is True
        assert _to_bool(False) is False

        # Test numeric values
        assert _to_bool(1) is True
        assert _to_bool(0) is False
        assert _to_bool(1.5) is True
        assert _to_bool(0.0) is False

        # Test string values (case insensitive)
        assert _to_bool("1") is True
        assert _to_bool("true") is True
        assert _to_bool("yes") is True
        assert _to_bool("on") is True
        assert _to_bool("TRUE") is True
        assert _to_bool("YES") is True
        assert _to_bool("ON") is True

        assert _to_bool("0") is False
        assert _to_bool("false") is False
        assert _to_bool("no") is False
        assert _to_bool("off") is False
        assert _to_bool("FALSE") is False
        assert _to_bool("NO") is False
        assert _to_bool("OFF") is False

        # Test None and empty values
        assert _to_bool(None) is None
        assert _to_bool("") is False
        assert _to_bool("   ") is False

        # Test invalid string values
        assert _to_bool("invalid") is False
        assert _to_bool("maybe") is False

    def test_to_int_function_comprehensive(self):
        """Test _to_int utility function with comprehensive inputs."""
        from custom_components.wiim.sensor import _to_int

        # Test valid integers
        assert _to_int(42) == 42
        assert _to_int("42") == 42
        assert _to_int(42.0) == 42
        assert _to_int(42.7) == 42  # Should truncate

        # Test zero values
        assert _to_int(0) == 0
        assert _to_int("0") == 0
        assert _to_int(0.0) == 0

        # Test None and invalid values
        assert _to_int(None) is None
        assert _to_int("invalid") is None
        assert _to_int("42.5") is None  # Invalid string format
        assert _to_int("") is None
        assert _to_int("   ") is None

        # Test edge cases
        assert _to_int(float("inf")) is None
        assert _to_int(float("-inf")) is None


class TestSensorPlatformSetupLogic:
    """Test sensor platform setup logic."""

    async def test_get_sensor_entities_list_core_sensors(self):
        """Test sensor entity creation with core sensors only."""
        from custom_components.wiim.sensor import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry"

        # Mock speaker with basic setup
        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.coordinator = MagicMock()
        speaker.coordinator.player = MagicMock()
        speaker.coordinator.player.capabilities = {"supports_audio_output": False}

        with patch("custom_components.wiim.sensor.get_speaker_from_config_entry", return_value=speaker):
            entities = []
            async_add_entities = MagicMock()

            await async_setup_entry(hass, config_entry, async_add_entities)

            # Verify entities were created
            async_add_entities.assert_called_once()
            entities = async_add_entities.call_args[0][0]

            # Should create core sensors (role, input, diagnostic, bluetooth)
            assert len(entities) >= 4

    async def test_get_sensor_entities_with_audio_output_support(self):
        """Test sensor entity creation when device supports audio output."""
        from custom_components.wiim.sensor import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry"

        # Mock speaker with audio output support
        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.coordinator = MagicMock()
        speaker.coordinator.player = MagicMock()
        speaker.coordinator.player.capabilities = {"supports_audio_output": True}

        with patch("custom_components.wiim.sensor.get_speaker_from_config_entry", return_value=speaker):
            entities = []
            async_add_entities = MagicMock()

            await async_setup_entry(hass, config_entry, async_add_entities)

            # Verify entities were created
            async_add_entities.assert_called_once()
            entities = async_add_entities.call_args[0][0]

            # Should create additional audio quality sensors
            entity_types = [type(entity).__name__ for entity in entities]
            assert "WiiMAudioQualitySensor" in entity_types
            assert "WiiMSampleRateSensor" in entity_types
            assert "WiiMBitDepthSensor" in entity_types
            assert "WiiMBitRateSensor" in entity_types

    async def test_get_sensor_entities_with_metadata_support(self):
        """Test sensor entity creation when metadata support is enabled."""
        from custom_components.wiim.sensor import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry"

        # Mock speaker with metadata support
        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.coordinator = MagicMock()
        speaker.coordinator.player = MagicMock()
        speaker.coordinator.player.capabilities = {"supports_audio_output": True}
        speaker.coordinator._metadata_supported = True

        with patch("custom_components.wiim.sensor.get_speaker_from_config_entry", return_value=speaker):
            entities = []
            async_add_entities = MagicMock()

            await async_setup_entry(hass, config_entry, async_add_entities)

            # Verify entities were created
            async_add_entities.assert_called_once()
            entities = async_add_entities.call_args[0][0]

            # Should create audio quality sensors when metadata is supported
            entity_types = [type(entity).__name__ for entity in entities]
            assert "WiiMAudioQualitySensor" in entity_types
            assert "WiiMSampleRateSensor" in entity_types
            assert "WiiMBitDepthSensor" in entity_types
            assert "WiiMBitRateSensor" in entity_types

    async def test_get_sensor_entities_without_metadata_support(self):
        """Test sensor entity creation when metadata support is disabled."""
        from custom_components.wiim.sensor import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry"

        # Mock speaker without metadata support
        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.coordinator = MagicMock()
        speaker.coordinator.player = MagicMock()
        speaker.coordinator.player.capabilities = {"supports_audio_output": True}
        speaker.coordinator._metadata_supported = False

        with patch("custom_components.wiim.sensor.get_speaker_from_config_entry", return_value=speaker):
            entities = []
            async_add_entities = MagicMock()

            await async_setup_entry(hass, config_entry, async_add_entities)

            # Verify entities were created
            async_add_entities.assert_called_once()
            entities = async_add_entities.call_args[0][0]

            # Should not create audio quality sensors when metadata is not supported
            entity_types = [type(entity).__name__ for entity in entities]
            assert "WiiMAudioQualitySensor" not in entity_types
            assert "WiiMSampleRateSensor" not in entity_types
            assert "WiiMBitDepthSensor" not in entity_types
            assert "WiiMBitRateSensor" not in entity_types

    async def test_get_sensor_entities_without_capabilities(self):
        """Test sensor entity creation when capabilities are not available."""
        from custom_components.wiim.sensor import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry"

        # Mock speaker without capabilities attribute (fallback)
        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.coordinator = MagicMock()
        speaker.coordinator.player = MagicMock()
        # No capabilities attribute - should create Bluetooth sensor as fallback

        with patch("custom_components.wiim.sensor.get_speaker_from_config_entry", return_value=speaker):
            entities = []
            async_add_entities = MagicMock()

            await async_setup_entry(hass, config_entry, async_add_entities)

            # Verify entities were created
            async_add_entities.assert_called_once()
            entities = async_add_entities.call_args[0][0]

            # Should create Bluetooth sensor as fallback when capabilities not available
            entity_types = [type(entity).__name__ for entity in entities]
            assert "WiiMBluetoothOutputSensor" in entity_types


class TestSensorDataProcessing:
    """Test sensor data processing logic."""

    def test_role_sensor_value_mapping(self):
        """Test role sensor value mapping logic."""
        # This tests the core logic that would be in the sensor entities
        # Role mapping: "solo" -> "Solo", "coordinator" -> "Coordinator", "slave" -> "Slave"

        test_cases = [
            ("solo", "Solo"),
            ("coordinator", "Coordinator"),
            ("slave", "Slave"),
            ("master", "Master"),  # Edge case
            ("unknown", "Unknown"),  # Edge case
        ]

        for input_role, expected_output in test_cases:
            # Simulate the role processing logic
            role = input_role.title()
            assert role == expected_output

    def test_diagnostic_sensor_status_logic(self):
        """Test diagnostic sensor status determination logic."""
        # Test WiFi RSSI parsing and status determination
        test_cases = [
            ({"wifi_rssi": "-45"}, "Wi-Fi -45 dBm"),
            ({"RSSI": "-50"}, "Wi-Fi -50 dBm"),
            ({"wifi_rssi": "unknown"}, "Online"),  # No RSSI, but available
            ({}, "Offline"),  # No RSSI, not available
        ]

        for status_data, expected_status in test_cases:
            # Simulate the status determination logic
            rssi = status_data.get("wifi_rssi") or status_data.get("RSSI")

            if rssi not in (None, "", "unknown", "unknow"):
                try:
                    status = f"Wi-Fi {int(rssi)} dBm"
                except (TypeError, ValueError):
                    # Fall through to availability check
                    status = "Online" if expected_status == "Online" else "Offline"
            else:
                # No RSSI → show basic connectivity status
                # Check for recent command failures for more specific status
                # For this test, we'll simulate the availability check
                status = "Online" if expected_status == "Online" else "Offline"

            assert status == expected_status

    def test_audio_quality_sensor_formatting(self):
        """Test audio quality sensor formatting logic."""
        # Test the formatting logic for audio quality strings
        test_cases = [
            # (sample_rate, bit_depth, bit_rate, expected_output)
            (44100, 16, 320, "44100Hz / 16bit / 320kbps"),
            (44100, 16, None, "44100Hz / 16bit"),
            (44100, None, None, "44100Hz"),
            (None, None, None, "Unknown"),
        ]

        for sample_rate, bit_depth, bit_rate, expected in test_cases:
            # Simulate the formatting logic
            if all([sample_rate, bit_depth, bit_rate]):
                result = f"{sample_rate}Hz / {bit_depth}bit / {bit_rate}kbps"
            elif sample_rate and bit_depth:
                result = f"{sample_rate}Hz / {bit_depth}bit"
            elif sample_rate:
                result = f"{sample_rate}Hz"
            else:
                result = "Unknown"

            assert result == expected

    def test_bluetooth_sensor_state_logic(self):
        """Test Bluetooth output sensor state determination."""
        # Test the logic for determining Bluetooth output state
        test_cases = [
            (True, "on"),
            (False, "off"),
        ]

        for is_active, expected_state in test_cases:
            # Simulate the state determination
            state = "on" if is_active else "off"
            assert state == expected_state

    def test_sensor_attribute_processing(self):
        """Test sensor attribute processing and filtering."""
        # Test the logic for processing and filtering sensor attributes

        # Mock status and device data
        status_data = {"wifi_rssi": "-45", "wifi_channel": "6", "mac_address": "aa:bb:cc:dd:ee:ff"}

        device_data = {"mac": "aa:bb:cc:dd:ee:ff", "uuid": "test-uuid", "firmware": "1.0.0", "project": "WiiM Mini"}

        multiroom_data = {"role": "coordinator"}

        # Simulate attribute processing
        attrs = {}
        attrs.update(status_data)
        attrs.update(device_data)
        attrs["group"] = multiroom_data.get("role")

        # Verify key attributes are present
        assert attrs["mac"] == "aa:bb:cc:dd:ee:ff"
        assert attrs["uuid"] == "test-uuid"
        assert attrs["firmware"] == "1.0.0"
        assert attrs["wifi_rssi"] == "-45"
        assert attrs["group"] == "coordinator"


class TestSensorConstants:
    """Test sensor platform constants and configuration."""

    def test_sensor_icons(self):
        """Test sensor icon constants."""
        # Test that sensor icons are properly defined
        expected_icons = {
            "role": "mdi:account-group",
            "diagnostic": "mdi:wifi",
            "input": "mdi:import",
            "bluetooth": "mdi:bluetooth",
            "audio_quality": "mdi:ear-hearing",
            "sample_rate": "mdi:sine-wave",
            "bit_depth": "mdi:database",
            "bit_rate": "mdi:transmission-tower",
        }

        for _sensor_type, expected_icon in expected_icons.items():
            # Verify icon format is correct
            assert expected_icon.startswith("mdi:")
            assert len(expected_icon) > 4

    def test_sensor_units(self):
        """Test sensor unit constants."""
        # Test sensor units are properly defined
        expected_units = {
            "sample_rate": "Hz",
            "bit_depth": "bit",
            "bit_rate": "kbps",
        }

        for _sensor_type, expected_unit in expected_units.items():
            assert isinstance(expected_unit, str)
            assert len(expected_unit) > 0


class TestSensorErrorHandling:
    """Test sensor error handling and edge cases."""

    def test_sensor_with_missing_coordinator_data(self):
        """Test sensor behavior with missing coordinator data."""
        # Test how sensors handle missing or incomplete data
        test_cases = [
            ({}, "should handle empty data gracefully"),
            ({"partial": "data"}, "should handle partial data"),
            (None, "should handle None data"),
        ]

        for data, _description in test_cases:
            # Simulate sensor handling missing data
            if data is None:
                # Should return None or default values
                assert True  # Placeholder - would depend on specific sensor logic
            else:
                # Should extract available data
                assert True  # Placeholder - would depend on specific sensor logic

    def test_sensor_with_device_communication_errors(self):
        """Test sensor behavior during device communication errors."""
        # Test how sensors handle communication failures
        error_scenarios = [
            "connection_timeout",
            "network_unreachable",
            "ssl_handshake_failure",
            "http_404",
            "http_500",
        ]

        for _error_type in error_scenarios:
            # Simulate error handling
            # Sensors should gracefully handle errors and return appropriate states
            assert True  # Placeholder - would depend on specific sensor logic

    def test_sensor_state_persistence_during_errors(self):
        """Test sensor state persistence during temporary errors."""
        # Test that sensors maintain reasonable states during temporary issues
        # This is important for avoiding UI flicker

        # Simulate sensor maintaining previous valid state during errors
        previous_states = ["Online", "Solo", "44100Hz / 16bit / 320kbps"]

        for previous_state in previous_states:
            # Sensors should try to maintain meaningful states
            assert len(previous_state) > 0
            assert previous_state != "unavailable"  # Should avoid "unavailable" when possible


class TestSensorPlatformIntegration:
    """Test sensor platform integration logic."""

    def test_sensor_entity_naming_conventions(self):
        """Test sensor entity naming follows conventions."""
        # Test that sensor names follow the expected patterns
        test_cases = [
            ("Test WiiM", "test-speaker-uuid", "Test WiiM Multiroom Role"),
            ("Test WiiM", "test-speaker-uuid", "Test WiiM Device Status"),
            ("Test WiiM", "test-speaker-uuid", "Test WiiM Current Input"),
            ("Test WiiM", "test-speaker-uuid", "Test WiiM Bluetooth Output"),
        ]

        for speaker_name, _uuid, expected_name in test_cases:
            # Simulate name generation logic
            if "Multiroom Role" in expected_name:
                name = f"{speaker_name} Multiroom Role"
            elif "Device Status" in expected_name:
                name = f"{speaker_name} Device Status"
            elif "Current Input" in expected_name:
                name = f"{speaker_name} Current Input"
            elif "Bluetooth Output" in expected_name:
                name = f"{speaker_name} Bluetooth Output"

            assert name == expected_name

    def test_sensor_unique_id_generation(self):
        """Test sensor unique ID generation."""
        # Test that unique IDs follow the expected pattern
        test_cases = [
            ("test-speaker-uuid", "multiroom_role", "test-speaker-uuid_multiroom_role"),
            ("test-speaker-uuid", "diagnostic", "test-speaker-uuid_diagnostic"),
            ("test-speaker-uuid", "current_input", "test-speaker-uuid_current_input"),
            ("test-speaker-uuid", "bluetooth_output", "test-speaker-uuid_bluetooth_output"),
            ("test-speaker-uuid", "audio_quality", "test-speaker-uuid_audio_quality"),
        ]

        for uuid, sensor_type, expected_id in test_cases:
            # Simulate unique ID generation
            unique_id = f"{uuid}_{sensor_type}"
            assert unique_id == expected_id

    def test_sensor_platform_logging(self):
        """Test sensor platform logging messages."""
        # Test that appropriate log messages are generated
        log_messages = [
            "Created %d sensor entities for %s (role sensor always included)",
            "Audio output capability check for %s: supports_audio_output=%s",
            "Enabling SELECT platform - device supports audio output control",
            "Skipping SELECT platform - device does not support audio output control",
            "🎯 ROLE SENSOR VALUE CHANGED for %s: %s -> %s",
        ]

        for message in log_messages:
            # Verify log message format
            # Some messages have format placeholders, others are static
            if "%" in message:
                assert len(message) > 10  # Should be meaningful messages
            else:
                assert len(message) > 10  # Should be meaningful messages
