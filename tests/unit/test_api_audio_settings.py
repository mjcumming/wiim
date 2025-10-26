"""Tests for WiiM Audio Settings API."""

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.wiim.api import WiiMClient
from custom_components.wiim.api_base import WiiMError


class TestAudioSettingsAPI:
    """Test cases for Audio Settings API functionality."""

    @pytest.mark.asyncio
    async def test_get_spdif_sample_rate_success(self):
        """Test successful SPDIF sample rate retrieval."""
        client = WiiMClient("192.168.1.100")

        with patch.object(client, "_request", new_callable=AsyncMock, return_value="48000") as mock_request:
            result = await client.get_spdif_sample_rate()
            assert result == "48000"
            mock_request.assert_called_once_with("/httpapi.asp?command=getSpdifOutSampleRate")
            await client.close()

    @pytest.mark.asyncio
    async def test_get_spdif_sample_rate_empty_response(self):
        """Test SPDIF sample rate with empty response."""
        client = WiiMClient("192.168.1.100")

        with patch.object(client, "_request", new_callable=AsyncMock, return_value=""):
            result = await client.get_spdif_sample_rate()
            assert result == ""
            await client.close()

    @pytest.mark.asyncio
    async def test_get_spdif_sample_rate_error(self):
        """Test SPDIF sample rate API error."""
        client = WiiMClient("192.168.1.100")

        with patch.object(client, "_request", new_callable=AsyncMock, side_effect=WiiMError("API Error")):
            result = await client.get_spdif_sample_rate()
            assert result == ""
            await client.close()

    @pytest.mark.asyncio
    async def test_set_spdif_switch_delay_success(self):
        """Test successful SPDIF switch delay setting."""
        client = WiiMClient("192.168.1.100")

        with patch.object(client, "_request", new_callable=AsyncMock, return_value="OK") as mock_request:
            await client.set_spdif_switch_delay(800)
            mock_request.assert_called_once_with("/httpapi.asp?command=setSpdifOutSwitchDelayMs:800")
            await client.close()

    @pytest.mark.asyncio
    async def test_set_spdif_switch_delay_invalid_range(self):
        """Test SPDIF switch delay with invalid range."""
        client = WiiMClient("192.168.1.100")

        # Test negative value
        with pytest.raises(ValueError, match="SPDIF switch delay must be between 0 and 3000 milliseconds"):
            await client.set_spdif_switch_delay(-1)

        # Test too high value
        with pytest.raises(ValueError, match="SPDIF switch delay must be between 0 and 3000 milliseconds"):
            await client.set_spdif_switch_delay(4000)

        await client.close()

    @pytest.mark.asyncio
    async def test_get_channel_balance_success(self):
        """Test successful channel balance retrieval."""
        client = WiiMClient("192.168.1.100")

        with patch.object(client, "_request", new_callable=AsyncMock, return_value="0.5") as mock_request:
            result = await client.get_channel_balance()
            assert result == 0.5
            mock_request.assert_called_once_with("/httpapi.asp?command=getChannelBalance")
            await client.close()

    @pytest.mark.asyncio
    async def test_get_channel_balance_numeric_response(self):
        """Test channel balance with numeric response."""
        client = WiiMClient("192.168.1.100")

        with patch.object(client, "_request", new_callable=AsyncMock, return_value=0.3):
            result = await client.get_channel_balance()
            assert result == 0.3
            await client.close()

    @pytest.mark.asyncio
    async def test_get_channel_balance_error(self):
        """Test channel balance API error."""
        client = WiiMClient("192.168.1.100")

        with patch.object(client, "_request", new_callable=AsyncMock, side_effect=WiiMError("API Error")):
            result = await client.get_channel_balance()
            assert result == 0.0  # Default on error
            await client.close()

    @pytest.mark.asyncio
    async def test_set_channel_balance_success(self):
        """Test successful channel balance setting."""
        client = WiiMClient("192.168.1.100")

        with patch.object(client, "_request", new_callable=AsyncMock, return_value="OK") as mock_request:
            await client.set_channel_balance(0.7)
            mock_request.assert_called_once_with("/httpapi.asp?command=setChannelBalance:0.7")
            await client.close()

    @pytest.mark.asyncio
    async def test_set_channel_balance_formatting(self):
        """Test channel balance value formatting."""
        client = WiiMClient("192.168.1.100")

        with patch.object(client, "_request", new_callable=AsyncMock, return_value="OK") as mock_request:
            # Test integer value
            await client.set_channel_balance(1.0)
            mock_request.assert_called_with("/httpapi.asp?command=setChannelBalance:1")

            # Test negative value
            await client.set_channel_balance(-0.5)
            mock_request.assert_called_with("/httpapi.asp?command=setChannelBalance:-0.5")

            await client.close()

    @pytest.mark.asyncio
    async def test_set_channel_balance_invalid_range(self):
        """Test channel balance with invalid range."""
        client = WiiMClient("192.168.1.100")

        # Test too low
        with pytest.raises(ValueError, match="Channel balance must be between -1.0 and 1.0"):
            await client.set_channel_balance(-1.1)

        # Test too high
        with pytest.raises(ValueError, match="Channel balance must be between -1.0 and 1.0"):
            await client.set_channel_balance(1.1)

        await client.close()

    @pytest.mark.asyncio
    async def test_center_channel_balance(self):
        """Test center channel balance helper."""
        client = WiiMClient("192.168.1.100")

        with patch.object(client, "set_channel_balance", new_callable=AsyncMock) as mock_set_balance:
            await client.center_channel_balance()
            mock_set_balance.assert_called_once_with(0.0)
            await client.close()

    @pytest.mark.asyncio
    async def test_get_spdif_sample_rate_int_success(self):
        """Test SPDIF sample rate integer conversion."""
        client = WiiMClient("192.168.1.100")

        with patch.object(
            client, "get_spdif_sample_rate", new_callable=AsyncMock, return_value="96000"
        ):
            result = await client.get_spdif_sample_rate_int()
            assert result == 96000
            await client.close()

    @pytest.mark.asyncio
    async def test_get_spdif_sample_rate_int_invalid(self):
        """Test SPDIF sample rate with invalid string."""
        client = WiiMClient("192.168.1.100")

        with patch.object(
            client, "get_spdif_sample_rate", new_callable=AsyncMock, return_value="invalid"
        ):
            result = await client.get_spdif_sample_rate_int()
            assert result == 0
            await client.close()

    @pytest.mark.asyncio
    async def test_is_spdif_output_active(self):
        """Test SPDIF output active detection."""
        client = WiiMClient("192.168.1.100")

        # Test active (rate > 0)
        with patch.object(
            client, "get_spdif_sample_rate_int", new_callable=AsyncMock, return_value=48000
        ):
            result = await client.is_spdif_output_active()
            assert result is True
            await client.close()

        # Test inactive (rate = 0)
        client = WiiMClient("192.168.1.100")
        with patch.object(client, "get_spdif_sample_rate_int", new_callable=AsyncMock, return_value=0):
            result = await client.is_spdif_output_active()
            assert result is False
            await client.close()

    @pytest.mark.asyncio
    async def test_get_audio_settings_status(self):
        """Test comprehensive audio settings status."""
        client = WiiMClient("192.168.1.100")

        with (
            patch.object(client, "get_spdif_sample_rate", new_callable=AsyncMock, return_value="48000"),
            patch.object(client, "get_channel_balance", new_callable=AsyncMock, return_value=0.2),
            patch.object(client, "is_spdif_output_active", new_callable=AsyncMock, return_value=True),
        ):
            result = await client.get_audio_settings_status()

            assert result["spdif_sample_rate"] == "48000"
            assert result["channel_balance"] == 0.2
            assert result["spdif_active"] is True

            await client.close()

    @pytest.mark.asyncio
    async def test_get_audio_settings_status_error(self):
        """Test audio settings status with errors."""
        client = WiiMClient("192.168.1.100")

        with patch.object(client, "get_spdif_sample_rate", new_callable=AsyncMock, side_effect=WiiMError("API Error")):
            result = await client.get_audio_settings_status()

            assert result["spdif_sample_rate"] == ""
            assert result["channel_balance"] == 0.0
            assert result["spdif_active"] is False

            await client.close()

    @pytest.mark.asyncio
    async def test_audio_settings_error_handling(self):
        """Test audio settings API error handling."""
        client = WiiMClient("192.168.1.100")

        # Test SPDIF delay API error
        with patch.object(client, "_request", new_callable=AsyncMock, side_effect=WiiMError("SPDIF API Error")):
            with pytest.raises(WiiMError):
                await client.set_spdif_switch_delay(800)
            await client.close()

        # Test channel balance API error
        client = WiiMClient("192.168.1.100")
        with patch.object(client, "_request", new_callable=AsyncMock, side_effect=WiiMError("Balance API Error")):
            with pytest.raises(WiiMError):
                await client.set_channel_balance(0.5)
            await client.close()
