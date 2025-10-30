"""Tests for WiiM Bluetooth API."""

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.wiim.api import WiiMClient
from custom_components.wiim.api_base import WiiMError


class TestBluetoothAPI:
    """Test cases for Bluetooth API functionality."""

    @pytest.mark.asyncio
    async def test_start_bluetooth_discovery_success(self):
        """Test successful Bluetooth discovery start."""
        client = WiiMClient("192.168.1.100")

        # Mock the _request method
        with patch.object(client, "_request", new_callable=AsyncMock, return_value="OK") as mock_request:
            await client.start_bluetooth_discovery(5)
            mock_request.assert_called_once_with("/httpapi.asp?command=startbtdiscovery:5")
            await client.close()

    @pytest.mark.asyncio
    async def test_start_bluetooth_discovery_invalid_duration(self):
        """Test Bluetooth discovery with invalid duration."""
        client = WiiMClient("192.168.1.100")

        # Test too short duration
        with pytest.raises(ValueError, match="Duration must be between 1 and 60 seconds"):
            await client.start_bluetooth_discovery(0)

        # Test too long duration
        with pytest.raises(ValueError, match="Duration must be between 1 and 60 seconds"):
            await client.start_bluetooth_discovery(70)

        await client.close()

    @pytest.mark.asyncio
    async def test_get_bluetooth_discovery_result_success(self):
        """Test successful Bluetooth discovery result retrieval."""
        client = WiiMClient("192.168.1.100")

        mock_result = {
            "num": 2,
            "scan_status": 3,
            "bt_device": [
                {"name": "iPhone", "mac": "AA:BB:CC:DD:EE:FF", "rssi": -45},
                {"name": "Bluetooth Speaker", "mac": "11:22:33:44:55:66", "rssi": -60},
            ],
        }

        with patch.object(client, "_request", new_callable=AsyncMock, return_value=mock_result) as mock_request:
            result = await client.get_bluetooth_discovery_result()
            assert result == mock_result
            mock_request.assert_called_once_with("/httpapi.asp?command=getbtdiscoveryresult")
            await client.close()

    @pytest.mark.asyncio
    async def test_scan_for_bluetooth_devices_success(self):
        """Test complete Bluetooth device scan."""
        client = WiiMClient("192.168.1.100")

        # Mock the discovery start
        with patch.object(client, "_request", new_callable=AsyncMock, return_value="OK") as mock_request:
            # Mock the discovery result (simulating scan completion)
            def mock_get_result(*args, **kwargs):
                if args[0] == "/httpapi.asp?command=startbtdiscovery:3":
                    return "OK"
                elif args[0] == "/httpapi.asp?command=getbtdiscoveryresult":
                    return {
                        "num": 1,
                        "scan_status": 3,  # Complete
                        "bt_device": [{"name": "Test Device", "mac": "AA:BB:CC:DD:EE:FF", "rssi": -50}],
                    }
                return None

            mock_request.side_effect = mock_get_result

            # Mock asyncio.sleep to speed up test
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await client.scan_for_bluetooth_devices(3)

                assert len(result) == 1
                assert result[0]["name"] == "Test Device"
                assert result[0]["mac"] == "AA:BB:CC:DD:EE:FF"
                assert result[0]["rssi"] == -50

            await client.close()

    @pytest.mark.asyncio
    async def test_scan_for_bluetooth_devices_scan_failed(self):
        """Test Bluetooth scan when discovery fails."""
        client = WiiMClient("192.168.1.100")

        # Mock discovery start to succeed but result to fail
        def mock_get_result(*args, **kwargs):
            if args[0] == "/httpapi.asp?command=startbtdiscovery:3":
                return "OK"
            elif args[0] == "/httpapi.asp?command=getbtdiscoveryresult":
                # Simulate API returning error string instead of dict
                return "Failed"
            return None

        with patch.object(client, "_request", new_callable=AsyncMock, side_effect=mock_get_result):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await client.scan_for_bluetooth_devices(3)
                assert result == []  # Should return empty list on failure
                await client.close()

    @pytest.mark.asyncio
    async def test_is_bluetooth_scan_in_progress(self):
        """Test checking if Bluetooth scan is in progress."""
        client = WiiMClient("192.168.1.100")

        # Test scan in progress (status 1 or 2)
        with patch.object(client, "_request", new_callable=AsyncMock, return_value={"scan_status": 2}):
            result = await client.is_bluetooth_scan_in_progress()
            assert result is True
            await client.close()

        # Test scan not in progress (status 0 or 3)
        client = WiiMClient("192.168.1.100")
        with patch.object(client, "_request", new_callable=AsyncMock, return_value={"scan_status": 3}):
            result = await client.is_bluetooth_scan_in_progress()
            assert result is False
            await client.close()

    @pytest.mark.asyncio
    async def test_get_bluetooth_device_count(self):
        """Test getting Bluetooth device count."""
        client = WiiMClient("192.168.1.100")

        with patch.object(client, "_request", new_callable=AsyncMock, return_value={"num": 3}):
            result = await client.get_bluetooth_device_count()
            assert result == 3
            await client.close()

        # Test error case
        client = WiiMClient("192.168.1.100")
        with patch.object(client, "_request", new_callable=AsyncMock, side_effect=WiiMError("API Error")):
            result = await client.get_bluetooth_device_count()
            assert result == 0
            await client.close()

    @pytest.mark.asyncio
    async def test_get_last_bluetooth_scan_status(self):
        """Test getting human-readable scan status."""
        client = WiiMClient("192.168.1.100")

        # Test different status codes
        status_tests = [(0, "Not started"), (1, "Initializing"), (2, "Scanning"), (3, "Complete"), (-1, "Unknown")]

        for status_code, expected_status in status_tests:
            with patch.object(
                client, "_request", new_callable=AsyncMock, return_value={"scan_status": status_code}
            ):
                result = await client.get_last_bluetooth_scan_status()
                assert result == expected_status

            await client.close()
            client = WiiMClient("192.168.1.100")

        # Test error case
        with patch.object(client, "_request", new_callable=AsyncMock, side_effect=WiiMError("API Error")):
            result = await client.get_last_bluetooth_scan_status()
            assert result == "Unknown"
            await client.close()

    @pytest.mark.asyncio
    async def test_bluetooth_error_handling(self):
        """Test Bluetooth API error handling."""
        client = WiiMClient("192.168.1.100")

        # Test API error
        with patch.object(client, "_request", new_callable=AsyncMock, side_effect=WiiMError("Bluetooth API Error")):
            with pytest.raises(WiiMError):
                await client.start_bluetooth_discovery(3)
            await client.close()

    @pytest.mark.asyncio
    async def test_bluetooth_default_parameters(self):
        """Test Bluetooth API with default parameters."""
        client = WiiMClient("192.168.1.100")

        # Test default duration
        with patch.object(client, "_request", new_callable=AsyncMock, return_value="OK") as mock_request:
            await client.start_bluetooth_discovery()  # No duration specified
            mock_request.assert_called_once_with("/httpapi.asp?command=startbtdiscovery:3")
            await client.close()
