"""Test coordinator normalise helpers."""

import pytest

from custom_components.wiim.coordinator_normalise import normalise_device_info
from custom_components.wiim.models import DeviceInfo
from custom_components.wiim.const import (
    DSP_VERSION_KEY,
    FIRMWARE_DATE_KEY,
    FIRMWARE_KEY,
    HARDWARE_KEY,
    LATEST_VERSION_KEY,
    MCU_VERSION_KEY,
    PRESET_SLOTS_KEY,
    PROJECT_KEY,
    UPDATE_AVAILABLE_KEY,
    WMRM_VERSION_KEY,
)


def test_normalise_device_info_basic():
    """Test basic device info normalisation."""
    device_info = DeviceInfo.model_validate(
        {
            "uuid": "test-uuid-123",
            "DeviceName": "Test Device",
            "project": "WiiMu-A31",
            "firmware": "1.2.3",
            "MAC": "AA:BB:CC:DD:EE:FF",
        }
    )

    result = normalise_device_info(device_info)

    assert result[FIRMWARE_KEY] == "1.2.3"
    assert result[PROJECT_KEY] == "WiiMu-A31"


def test_normalise_device_info_complete():
    """Test complete device info normalisation with all fields."""
    device_info = DeviceInfo.model_validate(
        {
            "uuid": "test-uuid-123",
            "DeviceName": "Test Device",
            "project": "WiiMu-A31",
            "firmware": "1.2.3",
            "Release": "2024-01-15",
            "hardware": "v2.1",
            "wmrm_version": "4.2",
            "mcu_ver": 100,
            "dsp_ver": 200,
            "preset_key": 6,
            "VersionUpdate": "1",
            "NewVer": "1.2.4",
        }
    )

    result = normalise_device_info(device_info)

    # Test all normalised fields
    assert result[FIRMWARE_KEY] == "1.2.3"
    assert result[FIRMWARE_DATE_KEY] == "2024-01-15"
    assert result[HARDWARE_KEY] == "v2.1"
    assert result[PROJECT_KEY] == "WiiMu-A31"
    assert result[MCU_VERSION_KEY] == "100"
    assert result[DSP_VERSION_KEY] == "200"
    assert result[PRESET_SLOTS_KEY] == 6
    assert result[WMRM_VERSION_KEY] == "4.2"
    assert result[UPDATE_AVAILABLE_KEY] is True
    assert result[LATEST_VERSION_KEY] == "1.2.4"


def test_normalise_device_info_missing_fields():
    """Test device info normalisation with missing fields."""
    device_info = DeviceInfo.model_validate({"uuid": "test-uuid-123", "DeviceName": "Test Device"})

    result = normalise_device_info(device_info)

    # Should return empty dict for missing fields
    assert len(result) == 0


def test_normalise_device_info_version_update_flags():
    """Test version update flag normalisation."""
    # Test update available
    device_info = DeviceInfo.model_validate({"VersionUpdate": "1"})
    result = normalise_device_info(device_info)
    assert result[UPDATE_AVAILABLE_KEY] is True

    # Test no update available
    device_info = DeviceInfo.model_validate({"VersionUpdate": "0"})
    result = normalise_device_info(device_info)
    assert result[UPDATE_AVAILABLE_KEY] is False

    # Test invalid update flag
    device_info = DeviceInfo.model_validate({"VersionUpdate": "invalid"})
    result = normalise_device_info(device_info)
    assert result[UPDATE_AVAILABLE_KEY] is False


def test_normalise_device_info_version_conversion():
    """Test MCU/DSP version conversion to strings."""
    device_info = DeviceInfo.model_validate({"mcu_ver": 12345, "dsp_ver": 67890})

    result = normalise_device_info(device_info)

    assert result[MCU_VERSION_KEY] == "12345"
    assert result[DSP_VERSION_KEY] == "67890"


def test_normalise_device_info_preset_key_conversion():
    """Test preset key conversion to integer."""
    # Valid integer conversion
    device_info = DeviceInfo.model_validate({"preset_key": 4})
    result = normalise_device_info(device_info)
    assert result[PRESET_SLOTS_KEY] == 4

    # Invalid conversion should be skipped
    device_info = DeviceInfo.model_validate({})
    # Manually set an invalid preset_key to test error handling
    device_info.preset_key = "invalid"
    result = normalise_device_info(device_info)
    assert PRESET_SLOTS_KEY not in result


def test_normalise_device_info_empty_values():
    """Test device info normalisation with empty/null values."""
    device_info = DeviceInfo.model_validate({"firmware": "", "project": None, "hardware": "", "wmrm_version": None})

    result = normalise_device_info(device_info)

    # Empty strings should not be included
    assert len(result) == 0


def test_normalise_device_info_preserves_original():
    """Test that normalisation doesn't modify the original device info."""
    original_data = {"uuid": "test-uuid-123", "DeviceName": "Test Device", "firmware": "1.2.3"}

    device_info = DeviceInfo.model_validate(original_data)
    original_firmware = device_info.firmware

    result = normalise_device_info(device_info)

    # Original should be unchanged
    assert device_info.firmware == original_firmware
    # Result should contain normalised data
    assert result[FIRMWARE_KEY] == "1.2.3"


def test_normalise_device_info_all_none():
    """Test device info normalisation with all None values."""
    device_info = DeviceInfo.model_validate({})

    result = normalise_device_info(device_info)

    # Should return empty dict
    assert result == {}
