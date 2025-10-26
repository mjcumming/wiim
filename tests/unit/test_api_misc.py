"""Tests for WiiM Miscellaneous API."""

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.wiim.api import WiiMClient
from custom_components.wiim.api_base import WiiMError


class TestMiscAPI:
    """Test cases for Miscellaneous API functionality."""

    @pytest.mark.asyncio
    async def test_set_buttons_enabled_success(self):
        """Test successful button enable."""
        client = WiiMClient("192.168.1.100")

        with patch.object(client, "_request", new_callable=AsyncMock, return_value="OK") as mock_request:
            await client.set_buttons_enabled(True)
            mock_request.assert_called_once_with("/httpapi.asp?command=Button_Enable_SET:1")
            await client.close()

    @pytest.mark.asyncio
    async def test_set_buttons_disabled_success(self):
        """Test successful button disable."""
        client = WiiMClient("192.168.1.100")

        with patch.object(client, "_request", new_callable=AsyncMock, return_value="OK") as mock_request:
            await client.set_buttons_enabled(False)
            mock_request.assert_called_once_with("/httpapi.asp?command=Button_Enable_SET:0")
            await client.close()

    @pytest.mark.asyncio
    async def test_enable_touch_buttons(self):
        """Test enable touch buttons helper."""
        client = WiiMClient("192.168.1.100")

        with patch.object(client, "set_buttons_enabled", new_callable=AsyncMock) as mock_set_buttons:
            await client.enable_touch_buttons()
            mock_set_buttons.assert_called_once_with(True)
            await client.close()

    @pytest.mark.asyncio
    async def test_disable_touch_buttons(self):
        """Test disable touch buttons helper."""
        client = WiiMClient("192.168.1.100")

        with patch.object(client, "set_buttons_enabled", new_callable=AsyncMock) as mock_set_buttons:
            await client.disable_touch_buttons()
            mock_set_buttons.assert_called_once_with(False)
            await client.close()

    @pytest.mark.asyncio
    async def test_set_led_switch_success(self):
        """Test alternative LED control success."""
        client = WiiMClient("192.168.1.100")

        with patch.object(client, "_request", new_callable=AsyncMock, return_value="OK") as mock_request:
            await client.set_led_switch(True)
            mock_request.assert_called_once_with("/httpapi.asp?command=LED_SWITCH_SET:1")
            await client.close()

    @pytest.mark.asyncio
    async def test_set_led_switch_disabled(self):
        """Test alternative LED control disabled."""
        client = WiiMClient("192.168.1.100")

        with patch.object(client, "_request", new_callable=AsyncMock, return_value="OK") as mock_request:
            await client.set_led_switch(False)
            mock_request.assert_called_once_with("/httpapi.asp?command=LED_SWITCH_SET:0")
            await client.close()

    @pytest.mark.asyncio
    async def test_are_touch_buttons_enabled(self):
        """Test checking if touch buttons are enabled."""
        client = WiiMClient("192.168.1.100")

        # Test enabled (API succeeds)
        with patch.object(client, "enable_touch_buttons", new_callable=AsyncMock):
            result = await client.are_touch_buttons_enabled()
            assert result is True
            await client.close()

        # Test disabled (API fails)
        client = WiiMClient("192.168.1.100")
        with patch.object(client, "enable_touch_buttons", new_callable=AsyncMock, side_effect=WiiMError("API Error")):
            result = await client.are_touch_buttons_enabled()
            assert result is False
            await client.close()

    @pytest.mark.asyncio
    async def test_get_device_capabilities(self):
        """Test device capabilities detection."""
        client = WiiMClient("192.168.1.100")

        # Mock all API calls to succeed
        with (
            patch.object(client, "set_buttons_enabled", new_callable=AsyncMock),
            patch.object(client, "set_led_switch", new_callable=AsyncMock),
        ):
            result = await client.get_device_capabilities()

            assert result["touch_buttons"] is True
            assert result["alternative_led"] is True
            # Other capabilities should be False since we didn't mock them

            await client.close()

    @pytest.mark.asyncio
    async def test_get_device_capabilities_all_fail(self):
        """Test device capabilities when all APIs fail."""
        client = WiiMClient("192.168.1.100")

        # Mock all API calls to fail
        with (
            patch.object(client, "set_buttons_enabled", new_callable=AsyncMock, side_effect=WiiMError("Buttons Error")),
            patch.object(client, "set_led_switch", new_callable=AsyncMock, side_effect=WiiMError("LED Error")),
        ):
            result = await client.get_device_capabilities()

            assert result["touch_buttons"] is False
            assert result["alternative_led"] is False

            await client.close()

    @pytest.mark.asyncio
    async def test_test_misc_functionality(self):
        """Test miscellaneous functionality testing."""
        client = WiiMClient("192.168.1.100")

        # Mock APIs to succeed
        with (
            patch.object(client, "set_buttons_enabled", new_callable=AsyncMock),
            patch.object(client, "set_led_switch", new_callable=AsyncMock),
        ):
            result = await client.test_misc_functionality()

            assert result["touch_buttons"] is True
            assert result["alternative_led"] is True

            await client.close()

    @pytest.mark.asyncio
    async def test_test_misc_functionality_all_fail(self):
        """Test miscellaneous functionality when all fail."""
        client = WiiMClient("192.168.1.100")

        # Mock APIs to fail
        with (
            patch.object(client, "set_buttons_enabled", new_callable=AsyncMock, side_effect=WiiMError("Buttons Error")),
            patch.object(client, "set_led_switch", new_callable=AsyncMock, side_effect=WiiMError("LED Error")),
        ):
            result = await client.test_misc_functionality()

            assert result["touch_buttons"] is False
            assert result["alternative_led"] is False

            await client.close()

    @pytest.mark.asyncio
    async def test_misc_error_handling(self):
        """Test miscellaneous API error handling."""
        client = WiiMClient("192.168.1.100")

        # Test button control error
        with patch.object(client, "_request", new_callable=AsyncMock, side_effect=WiiMError("Button API Error")):
            with pytest.raises(WiiMError):
                await client.set_buttons_enabled(True)
            await client.close()

        # Test LED switch error
        client = WiiMClient("192.168.1.100")
        with patch.object(client, "_request", new_callable=AsyncMock, side_effect=WiiMError("LED API Error")):
            with pytest.raises(WiiMError):
                await client.set_led_switch(True)
            await client.close()

    @pytest.mark.asyncio
    async def test_device_capabilities_error_handling(self):
        """Test device capabilities with mixed success/failure."""
        client = WiiMClient("192.168.1.100")

        # Mock buttons to succeed, LED to fail
        with (
            patch.object(client, "set_buttons_enabled", new_callable=AsyncMock),
            patch.object(client, "set_led_switch", new_callable=AsyncMock, side_effect=WiiMError("LED Error")),
        ):
            result = await client.get_device_capabilities()

            assert result["touch_buttons"] is True
            assert result["alternative_led"] is False

            await client.close()

    @pytest.mark.asyncio
    async def test_misc_functionality_comprehensive_test(self):
        """Test comprehensive miscellaneous functionality."""
        client = WiiMClient("192.168.1.100")

        # Test buttons work but LED fails
        with (
            patch.object(client, "set_buttons_enabled", new_callable=AsyncMock),
            patch.object(client, "set_led_switch", new_callable=AsyncMock, side_effect=WiiMError("LED Error")),
        ):
            result = await client.test_misc_functionality()

            assert result["touch_buttons"] is True
            assert result["alternative_led"] is False

            await client.close()
