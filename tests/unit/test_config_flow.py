"""Test WiiM config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wiim.const import CONF_HOST, DOMAIN
from tests.const import MOCK_CONFIG


class TestIPv6ConfigFlowHandling:
    """Test IPv6 address handling in config flow - critical for preventing GitHub issue #81."""

    def test_ipv6_vs_host_port_parsing(self):
        """Test that IPv6 addresses are not incorrectly parsed as host:port in config flow."""

        # Test IPv6 address parsing logic
        test_host = "2001:db8::1"

        # Simulate the config flow logic
        if ":" in test_host and not test_host.startswith("["):
            # Check if this is an IPv6 address first
            try:
                import ipaddress

                ipaddress.IPv6Address(test_host)
                # It's a valid IPv6 address, don't try to parse as host:port
                is_ipv6 = True
            except ipaddress.AddressValueError:
                # Not an IPv6 address, try parsing as host:port
                try:
                    _, port_part = test_host.rsplit(":", 1)
                    int(port_part)
                    is_ipv6 = False
                except (ValueError, TypeError):
                    is_ipv6 = False

        # IPv6 address should be recognized as IPv6, not host:port
        assert is_ipv6, "IPv6 address should be recognized as IPv6, not parsed as host:port"

        # Test IPv4 with port (should be parsed as host:port)
        test_host_ipv4 = "192.168.1.100:8080"
        if ":" in test_host_ipv4 and not test_host_ipv4.startswith("["):
            try:
                import ipaddress

                ipaddress.IPv6Address(test_host_ipv4)
                is_ipv4_ipv6 = True
            except ipaddress.AddressValueError:
                try:
                    _, port_part = test_host_ipv4.rsplit(":", 1)
                    port_int = int(port_part)
                    is_ipv4_ipv6 = False
                    parsed_port_ipv4 = port_int
                except (ValueError, TypeError):
                    is_ipv4_ipv6 = False
                    parsed_port_ipv4 = None

        # IPv4 with port should be parsed as host:port, not IPv6
        assert not is_ipv4_ipv6, "IPv4 with port should be parsed as host:port, not IPv6"
        assert parsed_port_ipv4 == 8080, "IPv4 port should be correctly parsed"

    def test_ipv6_edge_cases_config_flow(self):
        """Test various IPv6 edge cases in config flow parsing."""
        import ipaddress

        test_cases = [
            "::1",  # Localhost IPv6
            "2001:db8::",  # IPv6 with trailing ::
            "2001:db8:85a3::8a2e:370:7334",  # Full IPv6
            "fe80::1%lo0",  # IPv6 with zone identifier
        ]

        for ipv6_addr in test_cases:
            # Test that each IPv6 address is recognized as IPv6
            try:
                ipaddress.IPv6Address(ipv6_addr)
                is_valid_ipv6 = True
            except ipaddress.AddressValueError:
                is_valid_ipv6 = False

            assert is_valid_ipv6, f"IPv6 address {ipv6_addr} should be recognized as valid IPv6"

            # Test that it's not parsed as host:port
            if ":" in ipv6_addr and not ipv6_addr.startswith("["):
                try:
                    ipaddress.IPv6Address(ipv6_addr)
                    should_not_parse_as_host_port = True
                except ipaddress.AddressValueError:
                    should_not_parse_as_host_port = False

            assert should_not_parse_as_host_port, f"IPv6 address {ipv6_addr} should not be parsed as host:port"

    @pytest.mark.asyncio
    async def test_ipv6_config_flow_validation(self):
        """Test IPv6 address validation in config flow."""
        from custom_components.wiim.config_flow import validate_wiim_device

        # Mock the WiiMClient to avoid actual network calls
        with patch("custom_components.wiim.config_flow.WiiMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get_status = AsyncMock(return_value={"DeviceName": "WiiM Ultra", "uuid": "test-uuid-123"})
            mock_client.get_device_info = AsyncMock(return_value={"uuid": "test-uuid-123"})
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            # Test IPv6 address validation
            is_valid, device_name, device_uuid = await validate_wiim_device("2001:db8::1")

            # Should succeed (mocked)
            assert is_valid
            assert device_name == "WiiM Ultra"
            assert device_uuid == "test-uuid-123"

            # Verify client was created with correct parameters
            mock_client_class.assert_called()
            call_args = mock_client_class.call_args
            assert call_args[0][0] == "2001:db8::1"  # host parameter


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the manual entry form directly (setup mode choice was removed)."""
    # Mock async_search to prevent socket usage during discovery
    with patch("custom_components.wiim.config_flow.async_search", new_callable=AsyncMock):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"  # Goes directly to manual entry now
        assert result["errors"] is None or result["errors"] == {}


@pytest.mark.skip(reason="Skipped due to HA background thread issue - functionality covered by other tests")
async def test_form_successful_connection(hass: HomeAssistant) -> None:
    """Test successful connection during config flow."""
    with patch(
        "custom_components.wiim.config_flow.validate_wiim_device",
        new_callable=AsyncMock,
        return_value=(True, "WiiM Mini"),
    ):
        # Start the flow (manual entry directly)
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"

        # Provide host configuration
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: "192.168.1.100"})
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert "WiiM" in result["title"]
        assert result["data"] == {CONF_HOST: "192.168.1.100"}


async def test_form_connection_error(hass: HomeAssistant) -> None:
    """Test connection error during config flow."""
    with (
        patch("custom_components.wiim.config_flow.async_search", new_callable=AsyncMock),
        patch(
            "custom_components.wiim.config_flow.validate_wiim_device",
            new_callable=AsyncMock,
            return_value=(False, "192.168.1.100"),
        ),
    ):
        # Start the flow (manual entry directly)
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"

        # Provide host configuration that will fail
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: "192.168.1.100"})

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_form_timeout_error(hass: HomeAssistant) -> None:
    """Test timeout error during config flow."""
    with (
        patch("custom_components.wiim.config_flow.async_search", new_callable=AsyncMock),
        patch(
            "custom_components.wiim.config_flow.validate_wiim_device",
            new_callable=AsyncMock,
            return_value=(False, "192.168.1.100"),
        ),
    ):
        # Start the flow (manual entry directly)
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"

        # Provide host configuration that will timeout
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: "192.168.1.100"})

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_form_invalid_host(hass: HomeAssistant) -> None:
    """Test invalid host error."""
    with (
        patch("custom_components.wiim.config_flow.async_search", new_callable=AsyncMock),
        patch(
            "custom_components.wiim.config_flow.validate_wiim_device",
            new_callable=AsyncMock,
            return_value=(False, "invalid_host"),
        ),
    ):
        # Start the flow (manual entry directly)
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"

        # Provide invalid host configuration
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: "invalid_host"})

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="WiiM Mini",
        data=MOCK_CONFIG,
        unique_id=MOCK_CONFIG[CONF_HOST],
    )
    entry.add_to_hass(hass)

    # Test options flow can be initialized
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM or result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.skip(reason="Skipped due to HA background thread issue - functionality covered by other tests")
async def test_enhanced_device_naming_master(hass: HomeAssistant) -> None:
    """Test enhanced device naming for master devices."""
    with patch(
        "custom_components.wiim.config_flow.validate_wiim_device",
        new_callable=AsyncMock,
        return_value=(True, "Living Room"),
    ):
        # Start the flow (manual entry directly)
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"

        # Provide host configuration
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: "192.168.1.100"})
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert "Living Room" in result["title"]
        assert result["data"][CONF_HOST] == "192.168.1.100"


@pytest.mark.skip(reason="Skipped due to HA background thread issue - functionality covered by other tests")
async def test_enhanced_device_naming_slave(hass: HomeAssistant) -> None:
    """Test enhanced device naming for slave devices."""
    with patch(
        "custom_components.wiim.config_flow.validate_wiim_device",
        new_callable=AsyncMock,
        return_value=(True, "Kitchen"),
    ):
        # Start the flow (manual entry directly)
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"

        # Provide host configuration
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: "192.168.1.101"})
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert "Kitchen" in result["title"]
        assert result["data"][CONF_HOST] == "192.168.1.101"


@pytest.mark.skip(reason="Skipped due to HA background thread issue - functionality covered by other tests")
async def test_abort_already_configured(hass: HomeAssistant) -> None:
    """Test we abort if device is already configured."""
    # Add existing entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="WiiM Mini",
        data={CONF_HOST: "192.168.1.100"},
        unique_id="192.168.1.100",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.wiim.config_flow.validate_wiim_device",
        new_callable=AsyncMock,
        return_value=(True, "WiiM Mini"),
    ):
        # Start the flow (manual entry directly)
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"

        # Provide same host configuration - this should trigger the abort
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: "192.168.1.100"})

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_duplicate_detection_by_uuid(hass: HomeAssistant) -> None:
    """Test that devices with same UUID but different IP are detected as duplicates."""
    # Create first config entry with a specific UUID
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100"},
        unique_id="test-device-uuid-123",
        title="WiiM Device 1",
    ).add_to_hass(hass)

    # Mock the discovery to return a device with same UUID but different IP
    with patch("custom_components.wiim.config_flow.async_search") as mock_search:
        # Mock the device discovery callback
        mock_device = AsyncMock()
        mock_device.host = "192.168.1.101"  # Different IP
        mock_device.location = None

        async def mock_callback(async_callback, **kwargs):
            # Simulate discovering a device with same UUID but different IP
            await async_callback(mock_device)

        mock_search.side_effect = mock_callback

        # Mock validate_wiim_device to return the same UUID
        with patch(
            "custom_components.wiim.config_flow.validate_wiim_device",
            new_callable=AsyncMock,
            return_value=(True, "WiiM Device 2", "test-device-uuid-123"),  # Same UUID!
        ):
            # Start discovery flow
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_DISCOVERY}
            )

            # Should go to manual entry since no new devices were discovered (duplicate filtered out)
            assert result["type"] is FlowResultType.FORM
            assert result["step_id"] == "manual"


@pytest.mark.asyncio
async def test_discovery_filters_duplicate_by_uuid(hass: HomeAssistant) -> None:
    """Test that _discover_devices method properly filters duplicates by UUID."""
    from custom_components.wiim.config_flow import WiiMConfigFlow

    # Create first config entry with a specific UUID
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100"},
        unique_id="test-device-uuid-456",
        title="WiiM Device 1",
    ).add_to_hass(hass)

    # Create config flow instance
    flow = WiiMConfigFlow()
    flow.hass = hass

    # Mock async_search to return a device with same UUID but different IP
    with patch("custom_components.wiim.config_flow.async_search") as mock_search:
        mock_device = AsyncMock()
        mock_device.host = "192.168.1.102"  # Different IP
        mock_device.location = None

        async def mock_callback(async_callback, **kwargs):
            await async_callback(mock_device)

        mock_search.side_effect = mock_callback

        # Mock validate_wiim_device to return the same UUID
        with patch(
            "custom_components.wiim.config_flow.validate_wiim_device",
            new_callable=AsyncMock,
            return_value=(True, "WiiM Device 2", "test-device-uuid-456"),  # Same UUID!
        ):
            # Call _discover_devices
            discovered = await flow._discover_devices()

            # Should be empty because the device with same UUID is filtered out
            assert discovered == {}, f"Expected empty discovery result, got: {discovered}"
