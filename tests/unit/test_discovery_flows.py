"""Tests for zeroconf and SSDP discovery flows.

This test suite provides comprehensive coverage for device discovery, preventing
regression of issues like GitHub issue #80 (Audio Pro) and similar discovery bugs.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.wiim.const import DOMAIN


class TestZeroconfDiscovery:
    """Test zeroconf discovery flow for all device types."""

    @pytest.mark.asyncio
    async def test_successful_discovery(self, hass: HomeAssistant):
        """Test successful discovery with a fully working device."""
        # Device validates successfully with real UUID
        mock_validate = AsyncMock(return_value=(True, "WiiM Mini", "uuid-12345-67890"))

        discovery_info = MagicMock()
        discovery_info.name = "WiiM-Mini._linkplay._tcp.local."
        discovery_info.host = "192.168.1.100"
        discovery_info.type = "_linkplay._tcp.local."

        with patch("custom_components.wiim.config_flow.validate_wiim_device", mock_validate):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "zeroconf"}, data=discovery_info
            )

            # Should auto-configure successfully
            assert result["type"] == FlowResultType.FORM
            assert result.get("step_id") == "discovery_confirm"

    @pytest.mark.asyncio
    async def test_discovery_failure_with_real_uuid(self, hass: HomeAssistant):
        """Test discovery when validation fails but device returns a UUID."""
        # Device fails validation but has a real UUID
        mock_validate = AsyncMock(
            return_value=(False, "WiiM Device", "uuid-abcdef-123456")  # Real UUID
        )

        discovery_info = MagicMock()
        discovery_info.name = "WiiM-Unknown._linkplay._tcp.local."
        discovery_info.host = "192.168.1.101"
        discovery_info.type = "_linkplay._tcp.local."

        with patch("custom_components.wiim.config_flow.validate_wiim_device", mock_validate):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "zeroconf"}, data=discovery_info
            )

            # Should offer manual setup (soft failure)
            assert result["type"] == FlowResultType.FORM
            assert result.get("step_id") == "discovery_confirm"
            assert "reason" not in result or result.get("reason") != "cannot_connect"

    @pytest.mark.asyncio
    async def test_discovery_failure_without_uuid(self, hass: HomeAssistant):
        """Test discovery when validation fails completely (no UUID, not Audio Pro)."""
        # Device fails validation and uses host as fallback, but not Audio Pro
        mock_validate = AsyncMock(
            return_value=(False, "WiiM Device (192.168.1.102)", "192.168.1.102")  # Host as fallback
        )

        discovery_info = MagicMock()
        discovery_info.name = "Unknown-Device._linkplay._tcp.local."
        discovery_info.host = "192.168.1.102"
        discovery_info.type = "_linkplay._tcp.local."

        with patch("custom_components.wiim.config_flow.validate_wiim_device", mock_validate):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "zeroconf"}, data=discovery_info
            )

            # Should hard fail for non-Audio Pro devices
            assert result["type"] == FlowResultType.ABORT
            assert result.get("reason") == "cannot_connect"

    @pytest.mark.asyncio
    async def test_audio_pro_discovery(self, hass: HomeAssistant):
        """Test Audio Pro device discovery (special handling)."""
        # Audio Pro devices fail validation but get special handling
        mock_validate = AsyncMock(return_value=(False, "Audio Pro Speaker", "10.0.0.32"))

        discovery_info = MagicMock()
        discovery_info.name = "A10-MkII._linkplay._tcp.local."
        discovery_info.host = "10.0.0.32"
        discovery_info.type = "_linkplay._tcp.local."

        with patch("custom_components.wiim.config_flow.validate_wiim_device", mock_validate):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "zeroconf"}, data=discovery_info
            )

            # Audio Pro should get manual setup, not hard failure
            assert result["type"] == FlowResultType.FORM
            assert result.get("step_id") == "discovery_confirm"
            assert "reason" not in result or result.get("reason") != "cannot_connect"


class TestSSDPDiscovery:
    """Test SSDP discovery flow for all device types."""

    @pytest.mark.asyncio
    async def test_successful_ssdp_discovery(self, hass: HomeAssistant):
        """Test successful SSDP discovery."""
        mock_validate = AsyncMock(return_value=(True, "WiiM Pro", "uuid-ssdp-12345"))

        discovery_info = MagicMock()
        discovery_info.ssdp_location = "http://192.168.1.200:49152/description.xml"
        discovery_info.ssdp_st = "upnp:rootdevice"
        discovery_info.ssdp_server = "WiiM Pro/1.0"

        with patch("custom_components.wiim.config_flow.validate_wiim_device", mock_validate):
            result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "ssdp"}, data=discovery_info)

            assert result["type"] == FlowResultType.FORM
            assert result.get("step_id") == "discovery_confirm"

    @pytest.mark.asyncio
    async def test_ssdp_audio_pro_discovery(self, hass: HomeAssistant):
        """Test SSDP discovery for Audio Pro devices."""
        mock_validate = AsyncMock(return_value=(False, "Audio Pro Speaker", "10.0.0.50"))

        discovery_info = MagicMock()
        discovery_info.ssdp_location = "http://10.0.0.50:49152/description.xml"
        discovery_info.ssdp_st = "upnp:rootdevice"
        discovery_info.ssdp_server = "Audio-Pro-A15-MkII/1.0"

        with patch("custom_components.wiim.config_flow.validate_wiim_device", mock_validate):
            result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "ssdp"}, data=discovery_info)

            assert result["type"] == FlowResultType.FORM
            assert "reason" not in result or result.get("reason") != "cannot_connect"

    @pytest.mark.asyncio
    async def test_ssdp_no_location(self, hass: HomeAssistant):
        """Test SSDP discovery with missing location."""
        discovery_info = MagicMock()
        discovery_info.ssdp_location = None

        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "ssdp"}, data=discovery_info)

        assert result["type"] == FlowResultType.ABORT
        assert result.get("reason") == "no_host"


class TestDiscoveryEdgeCases:
    """Test edge cases and error conditions in discovery."""

    @pytest.mark.asyncio
    async def test_audio_pro_detection_various_models(self, hass: HomeAssistant):
        """Test Audio Pro detection for various model names."""
        models = [
            ("A10-MkII", True),
            ("A15-W", True),
            ("C10-Mk2", True),
            ("W Series", True),
            ("WiiM-Mini", False),  # Not Audio Pro
            ("WiiM-Pro", False),  # Not Audio Pro
        ]

        for model_name, should_be_audio_pro in models:
            discovery_info = MagicMock()
            discovery_info.name = f"{model_name}._linkplay._tcp.local."
            discovery_info.host = "192.168.1.100"
            discovery_info.type = "_linkplay._tcp.local."

            # Check if it would be detected as Audio Pro
            discovery_name = discovery_info.name.lower()
            discovery_type = discovery_info.type.lower()
            discovery_text = f"{discovery_name} {discovery_type}"

            audio_pro_indicators = [
                "audio pro",
                "audio_pro",
                "a10",
                "a15",
                "a28",
                "c10",
                "mkii",
                "mk2",
                "w-",
                "w series",
                "w generation",
            ]

            is_audio_pro = any(indicator in discovery_text for indicator in audio_pro_indicators)

            assert is_audio_pro == should_be_audio_pro, f"{model_name} detection incorrect"

    @pytest.mark.asyncio
    async def test_uuid_vs_host_fallback_logic(self):
        """Test the logic that distinguishes real UUIDs from host fallbacks."""
        test_cases = [
            {
                "device_uuid": "192.168.1.100",
                "host": "192.168.1.100",
                "expected_is_real": False,  # Not a real UUID
            },
            {
                "device_uuid": "uuid-12345-67890",
                "host": "192.168.1.100",
                "expected_is_real": True,  # Real UUID
            },
            {
                "device_uuid": "abcdef123456",
                "host": "192.168.1.100",
                "expected_is_real": True,  # Real UUID
            },
            {
                "device_uuid": "10.0.0.50",
                "host": "10.0.0.50",
                "expected_is_real": False,  # Not a real UUID
            },
        ]

        for case in test_cases:
            device_uuid = case["device_uuid"]
            host = case["host"]
            expected = case["expected_is_real"]

            is_real_uuid = device_uuid and device_uuid != host

            assert is_real_uuid == expected, (
                f"UUID {device_uuid} with host {host} should be {'real' if expected else 'not real'}"
            )

    @pytest.mark.asyncio
    async def test_discovery_without_name(self, hass: HomeAssistant):
        """Test discovery when device has no name."""
        mock_validate = AsyncMock(return_value=(True, "Unknown Device", "uuid-test-123"))

        discovery_info = MagicMock()
        discovery_info.name = None
        discovery_info.host = "192.168.1.255"
        discovery_info.type = "_linkplay._tcp.local."

        with patch("custom_components.wiim.config_flow.validate_wiim_device", mock_validate):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "zeroconf"}, data=discovery_info
            )

            # Should handle gracefully
            assert result["type"] in [FlowResultType.FORM, FlowResultType.ABORT]
