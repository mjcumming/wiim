"""Test Arylic LED support implementation."""

from unittest.mock import AsyncMock

import pytest

from .firmware_capabilities import get_led_command_format
from .models import DeviceInfo


def test_arylic_led_detection():
    """Test that Arylic devices are correctly identified for LED commands."""

    # Test Arylic devices
    arylic_devices = [
        DeviceInfo(model="Arylic Up2Stream Amp 2.0", name="Test Amp", uuid="test123"),
        DeviceInfo(model="Up2Stream Amp 2.1", name="Test Amp 2.1", uuid="test456"),
        DeviceInfo(model="Arylic S10+", name="Test S10+", uuid="test789"),
    ]

    for device in arylic_devices:
        assert get_led_command_format(device) == "arylic"

    # Test standard WiiM devices
    wiim_devices = [
        DeviceInfo(model="WiiM Mini", name="Test Mini", uuid="test101"),
        DeviceInfo(model="WiiM Pro", name="Test Pro", uuid="test102"),
        DeviceInfo(model="WiiM Amp", name="Test Amp", uuid="test103"),
    ]

    for device in wiim_devices:
        assert get_led_command_format(device) == "standard"

    # Test unknown devices default to standard
    unknown_device = DeviceInfo(model="Unknown Device", name="Test Unknown", uuid="test999")
    assert get_led_command_format(unknown_device) == "standard"


@pytest.mark.asyncio
async def test_arylic_led_commands():
    """Test that Arylic LED commands are sent correctly."""
    from .api_device import DeviceAPI

    # Mock client
    mock_client = AsyncMock()
    mock_client._request = AsyncMock()
    mock_client.host = "192.168.1.100"

    # Mock device info for Arylic device
    mock_device_info = DeviceInfo(model="Arylic Up2Stream Amp 2.0", name="Test Arylic", uuid="test123")
    mock_client.get_device_info_model = AsyncMock(return_value=mock_device_info)

    # Create API instance
    api = DeviceAPI()
    api._request = mock_client._request
    api.get_device_info_model = mock_client.get_device_info_model

    # Test LED on command
    await api.set_led(True)
    mock_client._request.assert_called_with("/httpapi.asp?command=MCU+PAS+RAKOIT:LED:1")

    # Test LED off command
    await api.set_led(False)
    mock_client._request.assert_called_with("/httpapi.asp?command=MCU+PAS+RAKOIT:LED:0")

    # Test LED brightness command
    await api.set_led_brightness(50)
    mock_client._request.assert_called_with("/httpapi.asp?command=MCU+PAS+RAKOIT:LEDBRIGHTNESS:50")


if __name__ == "__main__":
    # Run basic tests
    test_arylic_led_detection()
    print("✅ Arylic LED detection tests passed!")

    # Note: Async tests would need pytest-asyncio to run
    print("ℹ️  Run 'pytest test_arylic_led.py' for full test suite")
