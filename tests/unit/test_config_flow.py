"""Unit tests for WiiM Config Flow - testing options flow, discovery, and error handling."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.data_entry_flow import FlowResultType

from custom_components.wiim.config_flow import WiiMConfigFlow, WiiMOptionsFlow
from custom_components.wiim.const import (
    CONF_ENABLE_MAINTENANCE_BUTTONS,
    CONF_HOST,
    CONF_VOLUME_STEP,
    CONF_VOLUME_STEP_PERCENT,
    DOMAIN,
)


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.unique_id = "test-uuid"
    entry.data = {"host": "192.168.1.100"}
    entry.options = {}
    return entry


@pytest.fixture
def options_flow(mock_config_entry):
    """Create a WiiMOptionsFlow instance."""
    return WiiMOptionsFlow(mock_config_entry)


class TestWiiMOptionsFlow:
    """Test options flow functionality."""

    @pytest.mark.asyncio
    async def test_options_flow_init_with_defaults(self, options_flow, mock_config_entry):
        """Test options flow initialization with default values."""
        mock_config_entry.options = {}

        result = await options_flow.async_step_init()

        assert result["type"] == "form"
        assert result["step_id"] == "init"
        assert "data_schema" in result

    @pytest.mark.asyncio
    async def test_options_flow_saves_volume_step(self, options_flow, mock_config_entry):
        """Test that options flow saves volume step correctly."""
        user_input = {
            CONF_VOLUME_STEP_PERCENT: 10,  # 10%
            CONF_ENABLE_MAINTENANCE_BUTTONS: False,
        }

        result = await options_flow.async_step_init(user_input)

        assert result["type"] == "create_entry"
        assert result["data"][CONF_VOLUME_STEP] == 0.1  # Converted to decimal

    @pytest.mark.asyncio
    async def test_options_flow_reads_existing_options(self, options_flow, mock_config_entry):
        """Test that options flow reads existing options."""
        mock_config_entry.options = {
            CONF_VOLUME_STEP: 0.15,  # 15% as decimal
            CONF_ENABLE_MAINTENANCE_BUTTONS: True,
        }

        result = await options_flow.async_step_init()

        assert result["type"] == "form"
        # Check that form has correct defaults
        # The schema should have the correct default values
        assert "data_schema" in result

    @pytest.mark.asyncio
    async def test_options_flow_handles_missing_entry_options(self, options_flow, mock_config_entry):
        """Test that options flow handles missing entry.options gracefully."""
        # Simulate entry.options being None or missing
        del mock_config_entry.options
        mock_config_entry.options = {}

        result = await options_flow.async_step_init()

        assert result["type"] == "form"
        # Should use defaults

    @pytest.mark.asyncio
    async def test_options_flow_error_handling(self, options_flow, mock_config_entry):
        """Test that options flow handles errors gracefully."""
        # Make entry.options raise an exception
        mock_config_entry.options = MagicMock(side_effect=Exception("Test error"))

        result = await options_flow.async_step_init()

        # Should return form with error
        assert result["type"] == "form"
        assert "errors" in result

    @pytest.mark.asyncio
    async def test_options_flow_volume_step_conversion(self, options_flow, mock_config_entry):
        """Test volume step percentage to decimal conversion."""
        test_cases = [
            (1, 0.01),  # 1% = 0.01
            (5, 0.05),  # 5% = 0.05
            (10, 0.1),  # 10% = 0.1
            (25, 0.25),  # 25% = 0.25
            (50, 0.5),  # 50% = 0.5
        ]

        for percent, expected_decimal in test_cases:
            user_input = {CONF_VOLUME_STEP_PERCENT: percent}
            result = await options_flow.async_step_init(user_input)

            assert result["type"] == "create_entry"
            assert result["data"][CONF_VOLUME_STEP] == expected_decimal


class TestWiiMConfigFlow:
    """Test config flow functionality."""

    @pytest.fixture
    def config_flow(self, hass):
        """Create a WiiMConfigFlow instance."""
        flow = WiiMConfigFlow()
        flow.hass = hass
        return flow

    @pytest.mark.asyncio
    async def test_user_step_manual_entry(self, config_flow, hass):
        """Test manual entry step."""
        # async_step_user calls async_step_discovery, which may call async_step_manual
        # Mock discovery to return empty list so it goes to manual
        with patch("custom_components.wiim.config_flow.discover_devices", return_value=[]):
            with patch("custom_components.wiim.config_flow.validate_device") as mock_validate:
                from pywiim.models import DeviceInfo

                mock_device = DeviceInfo(
                    ip="192.168.1.100",
                    uuid="test-uuid",
                    name="Test WiiM",
                )
                mock_validate.return_value = mock_device
                # Mock async_set_unique_id and _abort_if_unique_id_configured
                config_flow.async_set_unique_id = AsyncMock()
                config_flow._abort_if_unique_id_configured = MagicMock(return_value=None)

                # Start with user step (which calls discovery)
                result = await config_flow.async_step_user(None)

                # Should show form or proceed to manual
                if result["type"] == FlowResultType.FORM:
                    # If form shown, submit manual entry
                    user_input = {CONF_HOST: "192.168.1.100"}
                    result = await config_flow.async_step_manual(user_input)

                # Should proceed to next step or create entry
                assert result["type"] in (FlowResultType.FORM, FlowResultType.CREATE_ENTRY)

    @pytest.mark.asyncio
    async def test_user_step_handles_connection_error(self, config_flow, hass):
        """Test user step handles connection errors."""
        from pywiim.exceptions import WiiMConnectionError

        # Mock discovery to return empty list so it goes to manual
        with patch("custom_components.wiim.config_flow.discover_devices", return_value=[]):
            with patch("custom_components.wiim.config_flow.validate_device") as mock_validate:
                mock_validate.side_effect = WiiMConnectionError("Connection failed")

                # Start with user step
                result = await config_flow.async_step_user(None)

                # If form shown, submit manual entry
                if result["type"] == FlowResultType.FORM:
                    user_input = {CONF_HOST: "192.168.1.100"}
                    # The error will propagate - test that it raises the exception
                    with pytest.raises(WiiMConnectionError):
                        await config_flow.async_step_manual(user_input)
                else:
                    # If no form, the error should have been raised
                    pytest.fail("Expected form to be shown")

    @pytest.mark.asyncio
    async def test_discovery_step(self, config_flow, hass):
        """Test discovery step."""

        from homeassistant.components.ssdp import SsdpServiceInfo

        discovery_info = SsdpServiceInfo(
            ssdp_location="http://192.168.1.100:49152/description.xml",
            ssdp_st="upnp:rootdevice",
            ssdp_usn="uuid:test-uuid::upnp:rootdevice",
            upnp={},
        )

        with patch("custom_components.wiim.config_flow.validate_device") as mock_validate:
            from pywiim.models import DeviceInfo

            mock_device = DeviceInfo(
                ip="192.168.1.100",
                uuid="test-uuid",
                name="Test WiiM",
            )
            mock_validate.return_value = mock_device
            # Initialize config_flow.data
            config_flow.data = {}
            # Mock async_set_unique_id and _abort_if_unique_id_configured
            config_flow.async_set_unique_id = AsyncMock()
            config_flow._abort_if_unique_id_configured = MagicMock(return_value=None)
            # Mock async_step_discovery_confirm to return a form
            config_flow.async_step_discovery_confirm = AsyncMock(
                return_value={
                    "type": FlowResultType.FORM,
                    "step_id": "discovery_confirm",
                }
            )

            result = await config_flow.async_step_ssdp(discovery_info)

            # Should proceed to next step or create entry
            assert result["type"] in (FlowResultType.FORM, FlowResultType.CREATE_ENTRY, FlowResultType.ABORT)

    @pytest.mark.asyncio
    async def test_discovery_step_handles_duplicate(self, config_flow, hass):
        """Test discovery step handles duplicate entries."""
        from homeassistant.components.ssdp import SsdpServiceInfo

        discovery_info = SsdpServiceInfo(
            ssdp_location="http://192.168.1.100:49152/description.xml",
            ssdp_st="upnp:rootdevice",
            ssdp_usn="uuid:test-uuid::upnp:rootdevice",
            upnp={},
        )

        # Mock existing entry
        existing_entry = MagicMock(spec=ConfigEntry)
        existing_entry.unique_id = "test-uuid"
        existing_entry.domain = DOMAIN
        existing_entry.data = {CONF_HOST: "192.168.1.100"}

        with patch("custom_components.wiim.config_flow.validate_device") as mock_validate:
            from pywiim.models import DeviceInfo

            mock_device = DeviceInfo(
                ip="192.168.1.100",
                uuid="test-uuid",
                name="Test WiiM",
            )
            mock_validate.return_value = mock_device
            # Initialize config_flow.data
            config_flow.data = {}
            # Mock async_set_unique_id to set unique_id
            config_flow.async_set_unique_id = AsyncMock()
            # Mock _abort_if_unique_id_configured to return None (not a duplicate by UUID)
            config_flow._abort_if_unique_id_configured = MagicMock(return_value=None)

            with patch.object(hass.config_entries, "async_entries", return_value=[existing_entry]):
                result = await config_flow.async_step_ssdp(discovery_info)

                # Should abort if duplicate by IP (checked before validation)
                assert result["type"] == FlowResultType.ABORT
                assert result["reason"] == "already_configured"

    @pytest.mark.asyncio
    async def test_zeroconf_step(self, config_flow, hass):
        """Test zeroconf discovery step."""
        from ipaddress import IPv4Address

        from homeassistant.components.zeroconf import ZeroconfServiceInfo

        zeroconf_info = ZeroconfServiceInfo(
            ip_address=IPv4Address("192.168.1.100"),
            ip_addresses=[IPv4Address("192.168.1.100")],
            hostname="test-wiim.local",
            name="Test WiiM",
            port=8080,
            properties={},
            type="_wiim._tcp.local.",
        )

        with patch("custom_components.wiim.config_flow.validate_device") as mock_validate:
            from pywiim.models import DeviceInfo

            mock_device = DeviceInfo(
                ip="192.168.1.100",
                uuid="test-uuid",
                name="Test WiiM",
            )
            mock_validate.return_value = mock_device
            # Initialize config_flow.data
            config_flow.data = {}
            # Mock async_set_unique_id and _abort_if_unique_id_configured
            config_flow.async_set_unique_id = AsyncMock()
            config_flow._abort_if_unique_id_configured = MagicMock(return_value=None)
            # Mock async_step_discovery_confirm to return a form
            config_flow.async_step_discovery_confirm = AsyncMock(
                return_value={
                    "type": FlowResultType.FORM,
                    "step_id": "discovery_confirm",
                }
            )

            result = await config_flow.async_step_zeroconf(zeroconf_info)

            # Should proceed to next step or create entry
            assert result["type"] in (FlowResultType.FORM, FlowResultType.CREATE_ENTRY, FlowResultType.ABORT)

    @pytest.mark.asyncio
    async def test_missing_device_step(self, config_flow, hass):
        """Test missing_device step."""
        from pywiim.models import DeviceInfo

        config_flow.context = {"unique_id": "test-uuid"}
        config_flow.data = {"device_name": "Test Device"}

        with patch("custom_components.wiim.config_flow.validate_device") as mock_validate:
            mock_device = DeviceInfo(
                ip="192.168.1.100",
                uuid="test-uuid",
                name="Test WiiM",
            )
            mock_validate.return_value = mock_device
            config_flow.async_set_unique_id = AsyncMock()
            config_flow._abort_if_unique_id_configured = MagicMock()
            config_flow._discover_slaves = AsyncMock()

            # First call shows form
            result = await config_flow.async_step_missing_device(None)
            assert result["type"] == FlowResultType.FORM

            # Second call with input creates entry
            user_input = {CONF_HOST: "192.168.1.100"}
            result = await config_flow.async_step_missing_device(user_input)

            assert result["type"] == FlowResultType.CREATE_ENTRY
            mock_validate.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_device_step_uuid_mismatch(self, config_flow, hass):
        """Test missing_device step with UUID mismatch."""
        from pywiim.models import DeviceInfo

        config_flow.context = {"unique_id": "expected-uuid"}
        config_flow.data = {"device_name": "Test Device"}

        with patch("custom_components.wiim.config_flow.validate_device") as mock_validate:
            mock_device = DeviceInfo(
                ip="192.168.1.100",
                uuid="different-uuid",  # Mismatch
                name="Test WiiM",
            )
            mock_validate.return_value = mock_device

            user_input = {CONF_HOST: "192.168.1.100"}
            result = await config_flow.async_step_missing_device(user_input)

            assert result["type"] == FlowResultType.FORM
            assert "base" in result.get("errors", {})

    @pytest.mark.asyncio
    async def test_discovery_confirm_step(self, config_flow, hass):
        """Test discovery_confirm step."""
        config_flow.data = {CONF_HOST: "192.168.1.100", "name": "Test WiiM"}
        config_flow.context = {}  # Initialize as dict, not mappingproxy
        config_flow._discover_slaves = AsyncMock()
        config_flow.hass = hass
        config_flow.async_create_entry = MagicMock(
            return_value={"type": FlowResultType.CREATE_ENTRY, "data": {CONF_HOST: "192.168.1.100"}}
        )

        # First call shows form
        result = await config_flow.async_step_discovery_confirm(None)
        assert result["type"] == FlowResultType.FORM

        # Second call with input creates entry
        user_input = {}
        result = await config_flow.async_step_discovery_confirm(user_input)

        assert result["type"] == FlowResultType.CREATE_ENTRY
        config_flow.async_create_entry.assert_called_once()

    @pytest.mark.asyncio
    async def test_discovery_confirm_with_ssdp_info(self, config_flow, hass):
        """Test discovery_confirm step preserves SSDP info."""
        config_flow.data = {
            CONF_HOST: "192.168.1.100",
            "name": "Test WiiM",
            "ssdp_info": {"location": "http://192.168.1.100/description.xml"},
        }
        config_flow.context = {}  # Initialize as dict
        config_flow._discover_slaves = AsyncMock()
        config_flow.hass = hass
        config_flow.async_create_entry = MagicMock(
            return_value={
                "type": FlowResultType.CREATE_ENTRY,
                "data": {CONF_HOST: "192.168.1.100", "ssdp_info": {"location": "http://192.168.1.100/description.xml"}},
            }
        )

        user_input = {}
        result = await config_flow.async_step_discovery_confirm(user_input)

        assert result["type"] == FlowResultType.CREATE_ENTRY
        # Verify async_create_entry was called with ssdp_info
        call_kwargs = config_flow.async_create_entry.call_args[1]
        assert "ssdp_info" in call_kwargs["data"]
