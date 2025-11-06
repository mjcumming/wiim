"""Unit tests for WiiM sensor platform."""

from unittest.mock import MagicMock


class TestWiiMRoleSensor:
    """Test WiiM Role Sensor - most critical for multiroom functionality."""

    def test_role_sensor_creation(self):
        """Test role sensor entity creation."""
        from custom_components.wiim.sensor import WiiMRoleSensor

        # Create a mock speaker
        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.role = "solo"
        speaker.is_group_coordinator = False
        speaker.group_members = []

        sensor = WiiMRoleSensor(speaker)

        assert sensor.speaker is speaker
        assert sensor.unique_id == "test-speaker-uuid_multiroom_role"
        assert sensor.name == "Test WiiM Multiroom Role"

    def test_role_sensor_icon(self):
        """Test role sensor icon."""
        from custom_components.wiim.sensor import WiiMRoleSensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"

        sensor = WiiMRoleSensor(speaker)
        assert sensor.icon == "mdi:account-group"

    def test_role_sensor_state_class(self):
        """Test role sensor state class is None (categorical)."""
        from custom_components.wiim.sensor import WiiMRoleSensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"

        sensor = WiiMRoleSensor(speaker)
        assert sensor.state_class is None

    def test_role_sensor_solo_role(self):
        """Test role sensor with solo role."""
        from custom_components.wiim.sensor import WiiMRoleSensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.role = "solo"
        speaker.is_group_coordinator = False
        speaker.group_members = []

        sensor = WiiMRoleSensor(speaker)

        assert sensor.native_value == "Solo"
        assert sensor.extra_state_attributes["is_group_coordinator"] is False
        assert sensor.extra_state_attributes["group_members_count"] == 0

    def test_role_sensor_coordinator_role(self):
        """Test role sensor with coordinator role."""
        from custom_components.wiim.sensor import WiiMRoleSensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.role = "coordinator"
        speaker.is_group_coordinator = True
        speaker.group_members = [MagicMock(name="Slave 1"), MagicMock(name="Slave 2")]

        sensor = WiiMRoleSensor(speaker)

        assert sensor.native_value == "Coordinator"
        assert sensor.extra_state_attributes["is_group_coordinator"] is True
        assert sensor.extra_state_attributes["group_members_count"] == 2

    def test_role_sensor_slave_role(self):
        """Test role sensor with slave role."""
        from custom_components.wiim.sensor import WiiMRoleSensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.role = "slave"
        speaker.is_group_coordinator = False
        speaker.coordinator_speaker = MagicMock()
        speaker.coordinator_speaker.name = "Master WiiM"
        speaker.group_members = [MagicMock(name="Master"), MagicMock(name="Other Slave")]

        sensor = WiiMRoleSensor(speaker)

        assert sensor.native_value == "Slave"
        assert sensor.extra_state_attributes["coordinator_name"] == "Master WiiM"
        assert "group_member_names" in sensor.extra_state_attributes


class TestWiiMDiagnosticSensor:
    """Test WiiM Diagnostic Sensor - primary status sensor."""

    def test_diagnostic_sensor_creation(self):
        """Test diagnostic sensor entity creation."""
        from custom_components.wiim.sensor import WiiMDiagnosticSensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.status_model = MagicMock()
        speaker.device_model = MagicMock()
        speaker.coordinator = MagicMock()
        speaker.coordinator.data = {}
        speaker.available = True
        speaker.coordinator = MagicMock()
        speaker.coordinator.has_recent_command_failures = MagicMock(return_value=False)

        sensor = WiiMDiagnosticSensor(speaker)

        assert sensor.speaker is speaker
        assert sensor.unique_id == "test-speaker-uuid_diagnostic"
        assert sensor.name == "Device Status"
        assert sensor.entity_category == "diagnostic"

    def test_diagnostic_sensor_icon(self):
        """Test diagnostic sensor icon."""
        from custom_components.wiim.sensor import WiiMDiagnosticSensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"

        sensor = WiiMDiagnosticSensor(speaker)
        assert sensor.icon == "mdi:wifi"

    def test_diagnostic_sensor_wifi_rssi_value(self):
        """Test diagnostic sensor with WiFi RSSI value."""
        from custom_components.wiim.sensor import WiiMDiagnosticSensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.status_model = MagicMock()
        speaker.status_model.model_dump.return_value = {"wifi_rssi": "-45"}

        sensor = WiiMDiagnosticSensor(speaker)
        assert sensor.native_value == "Wi-Fi -45 dBm"

    def test_diagnostic_sensor_online_status(self):
        """Test diagnostic sensor online status."""
        from custom_components.wiim.sensor import WiiMDiagnosticSensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.status_model = MagicMock()
        speaker.status_model.model_dump.return_value = {"wifi_rssi": "unknown"}
        speaker.available = True
        speaker.coordinator = MagicMock()
        speaker.coordinator.has_recent_command_failures = MagicMock(return_value=False)

        sensor = WiiMDiagnosticSensor(speaker)
        assert sensor.native_value == "Online"

    def test_diagnostic_sensor_offline_status(self):
        """Test diagnostic sensor offline status."""
        from custom_components.wiim.sensor import WiiMDiagnosticSensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.status_model = MagicMock()
        speaker.status_model.model_dump.return_value = {"wifi_rssi": "unknown"}
        speaker.available = False
        speaker.coordinator = MagicMock()
        speaker.coordinator.has_recent_command_failures = MagicMock(return_value=False)

        sensor = WiiMDiagnosticSensor(speaker)
        assert sensor.native_value == "Offline"


class TestWiiMInputSensor:
    """Test WiiM Input Sensor."""

    def test_input_sensor_creation(self):
        """Test input sensor entity creation."""
        from custom_components.wiim.sensor import WiiMInputSensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"

        sensor = WiiMInputSensor(speaker)

        assert sensor.speaker is speaker
        assert sensor.unique_id == "test-speaker-uuid_current_input"
        assert sensor.name == "Current Input"

    def test_input_sensor_icon(self):
        """Test input sensor icon."""
        from custom_components.wiim.sensor import WiiMInputSensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"

        sensor = WiiMInputSensor(speaker)
        assert sensor.icon == "mdi:import"

    def test_input_sensor_value(self):
        """Test input sensor native value."""
        from custom_components.wiim.sensor import WiiMInputSensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.get_current_source = MagicMock(return_value="Amazon Music")

        sensor = WiiMInputSensor(speaker)
        assert sensor.native_value == "Amazon Music"


class TestWiiMBluetoothOutputSensor:
    """Test WiiM Bluetooth Output Sensor."""

    def test_bluetooth_sensor_creation(self):
        """Test Bluetooth sensor entity creation."""
        from custom_components.wiim.sensor import WiiMBluetoothOutputSensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"

        sensor = WiiMBluetoothOutputSensor(speaker)

        assert sensor.speaker is speaker
        assert sensor.unique_id == "test-speaker-uuid_bluetooth_output"
        assert sensor.name == "Bluetooth Output"
        assert sensor.entity_category == "diagnostic"

    def test_bluetooth_sensor_icon(self):
        """Test Bluetooth sensor icon."""
        from custom_components.wiim.sensor import WiiMBluetoothOutputSensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"

        sensor = WiiMBluetoothOutputSensor(speaker)
        assert sensor.icon == "mdi:bluetooth"

    def test_bluetooth_sensor_on(self):
        """Test Bluetooth sensor when output is active."""
        from custom_components.wiim.sensor import WiiMBluetoothOutputSensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.is_bluetooth_output_active = MagicMock(return_value=True)

        sensor = WiiMBluetoothOutputSensor(speaker)
        assert sensor.native_value == "on"

    def test_bluetooth_sensor_off(self):
        """Test Bluetooth sensor when output is inactive."""
        from custom_components.wiim.sensor import WiiMBluetoothOutputSensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.is_bluetooth_output_active = MagicMock(return_value=False)

        sensor = WiiMBluetoothOutputSensor(speaker)
        assert sensor.native_value == "off"

    def test_bluetooth_sensor_unavailable(self):
        """Test Bluetooth sensor when device communication fails."""
        from custom_components.wiim.sensor import WiiMBluetoothOutputSensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.coordinator = MagicMock()
        speaker.coordinator._device_info_working = False

        sensor = WiiMBluetoothOutputSensor(speaker)
        assert sensor.native_value == "unavailable"


class TestWiiMAudioQualitySensors:
    """Test WiiM Audio Quality Sensors."""

    def test_audio_quality_sensor_creation(self):
        """Test audio quality sensor entity creation."""
        from custom_components.wiim.sensor import WiiMAudioQualitySensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"

        sensor = WiiMAudioQualitySensor(speaker)

        assert sensor.speaker is speaker
        assert sensor.unique_id == "test-speaker-uuid_audio_quality"
        assert sensor.name == "Audio Quality"
        assert sensor.entity_category == "diagnostic"

    def test_audio_quality_sensor_complete_metadata(self):
        """Test audio quality sensor with complete metadata."""
        from custom_components.wiim.sensor import WiiMAudioQualitySensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.coordinator = MagicMock()
        speaker.coordinator.data = {"metadata": {"sample_rate": 44100, "bit_depth": 16, "bit_rate": 320}}

        sensor = WiiMAudioQualitySensor(speaker)
        assert sensor.native_value == "44100Hz / 16bit / 320kbps"

    def test_audio_quality_sensor_no_metadata(self):
        """Test audio quality sensor with no metadata."""
        from custom_components.wiim.sensor import WiiMAudioQualitySensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.coordinator = MagicMock()
        speaker.coordinator.data = {"metadata": {}}

        sensor = WiiMAudioQualitySensor(speaker)
        assert sensor.native_value == "Unknown"

    def test_sample_rate_sensor_creation(self):
        """Test sample rate sensor entity creation."""
        from custom_components.wiim.sensor import WiiMSampleRateSensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"

        sensor = WiiMSampleRateSensor(speaker)

        assert sensor.speaker is speaker
        assert sensor.unique_id == "test-speaker-uuid_sample_rate"
        assert sensor.name == "Sample Rate"
        assert sensor.native_unit_of_measurement == "Hz"

    def test_bit_depth_sensor_creation(self):
        """Test bit depth sensor entity creation."""
        from custom_components.wiim.sensor import WiiMBitDepthSensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"

        sensor = WiiMBitDepthSensor(speaker)

        assert sensor.speaker is speaker
        assert sensor.unique_id == "test-speaker-uuid_bit_depth"
        assert sensor.name == "Bit Depth"
        assert sensor.native_unit_of_measurement == "bit"

    def test_bit_rate_sensor_creation(self):
        """Test bit rate sensor entity creation."""
        from custom_components.wiim.sensor import WiiMBitRateSensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"

        sensor = WiiMBitRateSensor(speaker)

        assert sensor.speaker is speaker
        assert sensor.unique_id == "test-speaker-uuid_bit_rate"
        assert sensor.name == "Bit Rate"
        assert sensor.native_unit_of_measurement == "kbps"


class TestSensorUtilityFunctions:
    """Test sensor utility functions."""

    def test_to_bool_function(self):
        """Test the _to_bool utility function."""
        from custom_components.wiim.sensor import _to_bool

        # Test various boolean conversions
        assert _to_bool(True) is True
        assert _to_bool(False) is False
        assert _to_bool(1) is True
        assert _to_bool(0) is False
        assert _to_bool("1") is True
        assert _to_bool("true") is True
        assert _to_bool("yes") is True
        assert _to_bool("on") is True
        assert _to_bool("0") is False
        assert _to_bool("false") is False
        assert _to_bool("no") is False
        assert _to_bool("off") is False
        assert _to_bool(None) is None
        assert _to_bool("") is False

    def test_to_int_function(self):
        """Test the _to_int utility function."""
        from custom_components.wiim.sensor import _to_int

        # Test various integer conversions
        assert _to_int(42) == 42
        assert _to_int("42") == 42
        assert _to_int(42.0) == 42
        assert _to_int(None) is None
        assert _to_int("invalid") is None

    def test_role_sensor_creation(self):
        """Test role sensor entity creation."""
        from custom_components.wiim.sensor import WiiMRoleSensor

        # Create a mock speaker
        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.role = "solo"
        speaker.is_group_coordinator = False
        speaker.group_members = []

        sensor = WiiMRoleSensor(speaker)

        assert sensor.speaker is speaker
        assert sensor.unique_id == "test-speaker-uuid_multiroom_role"
        assert sensor.name == "Test WiiM Multiroom Role"

    def test_role_sensor_icon(self):
        """Test role sensor icon."""
        from custom_components.wiim.sensor import WiiMRoleSensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"

        sensor = WiiMRoleSensor(speaker)
        assert sensor.icon == "mdi:account-group"

    def test_role_sensor_state_class(self):
        """Test role sensor state class is None (categorical)."""
        from custom_components.wiim.sensor import WiiMRoleSensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"

        sensor = WiiMRoleSensor(speaker)
        assert sensor.state_class is None

    def test_role_sensor_solo_role(self):
        """Test role sensor with solo role."""
        from custom_components.wiim.sensor import WiiMRoleSensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.role = "solo"
        speaker.is_group_coordinator = False
        speaker.group_members = []

        sensor = WiiMRoleSensor(speaker)

        assert sensor.native_value == "Solo"
        assert sensor.extra_state_attributes["is_group_coordinator"] is False
        assert sensor.extra_state_attributes["group_members_count"] == 0

    def test_role_sensor_coordinator_role(self):
        """Test role sensor with coordinator role."""
        from custom_components.wiim.sensor import WiiMRoleSensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.role = "coordinator"
        speaker.is_group_coordinator = True
        speaker.group_members = [MagicMock(name="Slave 1"), MagicMock(name="Slave 2")]

        sensor = WiiMRoleSensor(speaker)

        assert sensor.native_value == "Coordinator"
        assert sensor.extra_state_attributes["is_group_coordinator"] is True
        assert sensor.extra_state_attributes["group_members_count"] == 2

    def test_role_sensor_slave_role(self):
        """Test role sensor with slave role."""
        from custom_components.wiim.sensor import WiiMRoleSensor

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.role = "slave"
        speaker.is_group_coordinator = False
        speaker.coordinator_speaker = MagicMock()
        speaker.coordinator_speaker.name = "Master WiiM"
        speaker.group_members = [MagicMock(name="Master"), MagicMock(name="Other Slave")]

        sensor = WiiMRoleSensor(speaker)

        assert sensor.native_value == "Slave"
        assert sensor.extra_state_attributes["coordinator_name"] == "Master WiiM"
        assert "group_member_names" in sensor.extra_state_attributes
