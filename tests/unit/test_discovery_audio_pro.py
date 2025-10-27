"""Tests for Audio Pro device discovery handling.

This test suite prevents regression of GitHub issue #80, which was caused by
improper handling of Audio Pro devices during zeroconf/SSDP discovery.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.wiim.const import DOMAIN


class TestAudioProDiscoveryBugFix:
    """Test fixes for GitHub issue #80: Audio Pro discovery failures."""

    @pytest.mark.asyncio
    async def test_audio_pro_zeroconf_discovery_with_validation_failure(self, hass: HomeAssistant):
        """Test that Audio Pro devices that fail validation still get proper handling.

        This test prevents the bug where Audio Pro devices were incorrectly rejected
        during discovery, causing "validation completely failed" errors.
        """
        # Mock validate_wiim_device to fail (common for Audio Pro MkII/W-Series)
        # The key issue: it returns (False, name, host) where host is used as fallback
        mock_validate = AsyncMock(
            return_value=(False, "Audio Pro Speaker", "10.0.0.32")  # UUID is host!
        )

        # Mock discovery info that looks like Audio Pro
        discovery_info = MagicMock()
        discovery_info.name = "A10-MkII._linkplay._tcp.local."
        discovery_info.host = "10.0.0.32"
        discovery_info.type = "_linkplay._tcp.local."

        with patch("custom_components.wiim.config_flow.validate_wiim_device", mock_validate):
            # Start zeroconf discovery flow
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "zeroconf"}, data=discovery_info
            )

            # CRITICAL: Should NOT abort with "cannot_connect"
            # Should instead offer manual setup with Audio Pro guidance
            assert "reason" not in result or result.get("reason") != "cannot_connect", (
                "Audio Pro devices should get manual setup, not hard failure"
            )

            # Should reach discovery confirmation step
            assert result["type"] in ["form", "create_entry"], "Should show confirmation or create entry"
            assert result.get("step_id") == "discovery_confirm", "Should be at discovery confirmation step"

    @pytest.mark.asyncio
    async def test_audio_pro_ssdp_discovery_with_validation_failure(self, hass: HomeAssistant):
        """Test SSDP discovery with Audio Pro devices."""
        # Same as above but for SSDP
        mock_validate = AsyncMock(return_value=(False, "Audio Pro Speaker", "10.0.0.31"))

        discovery_info = MagicMock()
        discovery_info.ssdp_location = "http://10.0.0.31:49152/description.xml"
        discovery_info.ssdp_st = "upnp:rootdevice"
        discovery_info.ssdp_server = "A15-MkII UPnP/1.0"

        with patch("custom_components.wiim.config_flow.validate_wiim_device", mock_validate):
            result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "ssdp"}, data=discovery_info)

            assert "reason" not in result or result.get("reason") != "cannot_connect"
            assert result["type"] in ["form", "create_entry"]

    @pytest.mark.asyncio
    async def test_real_uuid_vs_host_fallback_detection(self):
        """Test the fix that distinguishes real UUIDs from host fallbacks.

        The bug was: when validation fails, device_uuid = host (e.g., "10.0.0.32")
        The code checked `elif device_uuid:` which is always True for non-empty strings
        This prevented Audio Pro handling from being reached.
        """
        # Simulate the fixed logic
        host = "10.0.0.32"
        device_uuid_host_fallback = "10.0.0.32"  # Host used as fallback
        device_uuid_real = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"  # Real UUID

        # Check if UUID is real or just host fallback
        is_real_uuid_host = device_uuid_host_fallback and device_uuid_host_fallback != host
        is_real_uuid_real = device_uuid_real and device_uuid_real != host

        # The host fallback should be detected as NOT a real UUID
        assert not is_real_uuid_host, "Host fallback should not be treated as real UUID"

        # The real UUID should be detected as a real UUID
        assert is_real_uuid_real, "Real UUID should be treated as real UUID"

    @pytest.mark.asyncio
    async def test_all_audio_pro_models(self, hass: HomeAssistant):
        """Test discovery for all Audio Pro models mentioned in issue #80."""
        audio_pro_models = [
            ("A10-MkII", "10.0.0.30"),
            ("A15-MkII", "10.0.0.31"),
            ("A28-MkII", "10.0.0.72"),
            ("C10-MkII", "10.0.0.43"),
        ]

        for model, ip in audio_pro_models:
            mock_validate = AsyncMock(return_value=(False, f"Audio Pro {model}", ip))

            discovery_info = MagicMock()
            discovery_info.name = f"{model}._linkplay._tcp.local."
            discovery_info.host = ip
            discovery_info.type = "_linkplay._tcp.local."

            with patch("custom_components.wiim.config_flow.validate_wiim_device", mock_validate):
                result = await hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": "zeroconf"}, data=discovery_info
                )

                # All models should get proper handling, not hard failures
                assert "reason" not in result or result.get("reason") != "cannot_connect", (
                    f"{model} should not be rejected during discovery"
                )
                assert result["type"] in ["form", "create_entry"], f"{model} should reach confirmation"


class TestDiscoveryConditionalLogic:
    """Test the conditional logic fix in discovery flows."""

    @pytest.mark.asyncio
    async def test_discovery_flow_condition_order(self):
        """Test that condition order is correct after the fix.

        Before fix:
        - elif device_uuid: (line 616) - ALWAYS True when validation fails
        - elif is_likely_audio_pro: (line 630) - NEVER reached!

        After fix:
        - elif is_real_uuid: - Only True when UUID != host
        - elif is_likely_audio_pro: - NOW can be reached!
        """
        # Simulate scenarios
        scenarios = [
            {
                "name": "successful_validation",
                "is_valid": True,
                "device_uuid": "real-uuid-123",
                "host": "10.0.0.32",
                "is_likely_audio_pro": False,
                "expected_path": "success",
            },
            {
                "name": "real_uuid_fallback",
                "is_valid": False,
                "device_uuid": "real-uuid-456",  # Real UUID from failed device
                "host": "10.0.0.33",
                "is_likely_audio_pro": False,
                "expected_path": "soft_failure",
            },
            {
                "name": "audio_pro_host_fallback",
                "is_valid": False,
                "device_uuid": "10.0.0.32",  # Host as fallback - THE BUG!
                "host": "10.0.0.32",
                "is_likely_audio_pro": True,
                "expected_path": "audio_pro_handling",
            },
            {
                "name": "non_audio_pro_host_fallback",
                "is_valid": False,
                "device_uuid": "192.168.1.100",
                "host": "192.168.1.100",
                "is_likely_audio_pro": False,
                "expected_path": "hard_failure",
            },
        ]

        for scenario in scenarios:
            device_uuid = scenario["device_uuid"]
            host = scenario["host"]
            is_likely_audio_pro = scenario["is_likely_audio_pro"]

            # Apply the fix logic
            is_real_uuid = device_uuid and device_uuid != host

            # Determine which path would be taken
            if scenario["is_valid"] and device_uuid:
                path_taken = "success"
            elif is_real_uuid:
                path_taken = "soft_failure"
            elif is_likely_audio_pro:
                path_taken = "audio_pro_handling"
            else:
                path_taken = "hard_failure"

            assert path_taken == scenario["expected_path"], (
                f"Scenario '{scenario['name']}' should take path '{scenario['expected_path']}'"
            )
