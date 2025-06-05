"""Test WiiM config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryNotReady
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wiim.const import CONF_HOST, DOMAIN

from .const import MOCK_CONFIG


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the initial choice form."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None or result["errors"] == {}


async def test_form_successful_connection(hass: HomeAssistant) -> None:
    """Test successful connection during config flow."""
    with (
        patch(
            "custom_components.wiim.config_flow.wiim_factory_client",
        ) as mock_factory,
        patch(
            "custom_components.wiim.config_flow._get_enhanced_device_name",
            return_value="WiiM Mini",
        ),
    ):
        # Mock the client factory to return a working client
        mock_client = AsyncMock()
        mock_client.close = AsyncMock()
        mock_factory.return_value = mock_client

        # Start the flow and choose manual entry
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        # Choose manual entry
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"discovery_mode": "manual"})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"

        # Provide host configuration
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: "192.168.1.100"})
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert "WiiM" in result["title"]
        assert result["data"] == {CONF_HOST: "192.168.1.100"}

        # Verify the client was created and closed
        mock_factory.assert_called_once_with("192.168.1.100")
        mock_client.close.assert_called_once()


async def test_form_connection_error(hass: HomeAssistant) -> None:
    """Test connection error during config flow."""
    with patch(
        "custom_components.wiim.config_flow.wiim_factory_client",
        side_effect=ConfigEntryNotReady("Connection error"),
    ):
        # Start the flow and choose manual entry
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        # Choose manual entry
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"discovery_mode": "manual"})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"

        # Provide host configuration that will fail
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: "192.168.1.100"})

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_form_timeout_error(hass: HomeAssistant) -> None:
    """Test timeout error during config flow."""
    with patch(
        "custom_components.wiim.config_flow.wiim_factory_client",
        side_effect=TimeoutError("Connection timeout"),
    ):
        # Start the flow and choose manual entry
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        # Choose manual entry
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"discovery_mode": "manual"})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"

        # Provide host configuration that will timeout
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: "192.168.1.100"})

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"
        assert result["errors"] == {"base": "timeout"}


async def test_form_invalid_host(hass: HomeAssistant) -> None:
    """Test invalid host error."""
    with patch(
        "custom_components.wiim.config_flow.wiim_factory_client",
        side_effect=Exception("Invalid host"),
    ):
        # Start the flow and choose manual entry
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        # Choose manual entry
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"discovery_mode": "manual"})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"

        # Provide invalid host configuration
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: "invalid_host"})

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"
        assert result["errors"] == {"base": "unknown"}


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


async def test_enhanced_device_naming_master(hass: HomeAssistant) -> None:
    """Test enhanced device naming for master devices."""
    master_multiroom_data = {
        "slave_list": [{"ip": "192.168.1.101", "uuid": "test-slave", "name": "Kitchen"}],
        "type": "0",
    }

    with (
        patch(
            "custom_components.wiim.config_flow.wiim_factory_client",
        ) as mock_factory,
        patch(
            "custom_components.wiim.config_flow._get_enhanced_device_name",
            return_value="Living Room (Master of 1 device)",
        ),
    ):
        # Mock the client factory to return a working client
        mock_client = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_status.return_value = {"DeviceName": "Living Room", "device_name": "Living Room"}
        mock_client.get_multiroom_info.return_value = master_multiroom_data
        mock_factory.return_value = mock_client

        # Start the flow and choose manual entry
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        # Choose manual entry
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"discovery_mode": "manual"})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"

        # Provide host configuration
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: "192.168.1.100"})
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert "Living Room" in result["title"]
        assert "Master" in result["title"]
        assert result["data"][CONF_HOST] == "192.168.1.100"


async def test_enhanced_device_naming_slave(hass: HomeAssistant) -> None:
    """Test enhanced device naming for slave devices."""
    slave_multiroom_data = {
        "slave_list": [],
        "type": "1",  # Slave type
    }

    with (
        patch(
            "custom_components.wiim.config_flow.wiim_factory_client",
        ) as mock_factory,
        patch(
            "custom_components.wiim.config_flow._get_enhanced_device_name",
            return_value="Kitchen (In Group)",
        ),
    ):
        # Mock the client factory to return a working client
        mock_client = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_status.return_value = {"DeviceName": "Kitchen", "device_name": "Kitchen"}
        mock_client.get_multiroom_info.return_value = slave_multiroom_data
        mock_factory.return_value = mock_client

        # Start the flow and choose manual entry
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        # Choose manual entry
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"discovery_mode": "manual"})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"

        # Provide host configuration
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: "192.168.1.101"})
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert "Kitchen" in result["title"]
        assert "Group" in result["title"]
        assert result["data"][CONF_HOST] == "192.168.1.101"


async def test_user_step_discovery_choice(hass: HomeAssistant) -> None:
    """Test user can choose discovery mode."""
    with patch(
        "custom_components.wiim.config_flow.async_search",
        return_value=None,  # Mock UPnP search to return nothing
    ):
        # Start the flow
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        # Choose discovery
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"discovery_mode": "discover"})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "discovery"


async def test_user_step_manual_choice(hass: HomeAssistant) -> None:
    """Test user can choose manual entry."""
    # Start the flow
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Choose manual
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"discovery_mode": "manual"})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


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

    with (
        patch(
            "custom_components.wiim.config_flow.wiim_factory_client",
        ) as mock_factory,
        patch(
            "custom_components.wiim.config_flow._get_enhanced_device_name",
            return_value="WiiM Mini",
        ),
    ):
        # Mock the client factory to return a working client
        mock_client = AsyncMock()
        mock_client.close = AsyncMock()
        mock_factory.return_value = mock_client

        # Start the flow and choose manual entry
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        # Choose manual entry
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"discovery_mode": "manual"})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"

        # Provide same host configuration - this should trigger the abort
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: "192.168.1.100"})

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"
