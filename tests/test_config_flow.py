"""Test WiiM config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wiim.const import DOMAIN

from .const import MOCK_CONFIG, MOCK_DEVICE_DATA


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the initial choice form."""
    with patch("custom_components.wiim.config_flow.async_search", None):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] is None or result["errors"] == {}


async def test_form_successful_connection(hass: HomeAssistant) -> None:
    """Test successful connection during config flow."""
    with (
        patch("custom_components.wiim.config_flow.async_search", None),
        patch(
            "custom_components.wiim.api.WiiMClient.get_player_status",
            return_value=MOCK_DEVICE_DATA,
        ),
        patch(
            "custom_components.wiim.api.WiiMClient.close",
            return_value=None,
        ),
        patch(
            "custom_components.wiim.config_flow.wiim_factory_client",
        ) as mock_factory,
        patch(
            "custom_components.wiim.config_flow._get_enhanced_device_name",
            return_value="WiiM Mini",
        ) as mock_enhanced_name,
    ):
        # Mock the factory to return a client
        mock_client = mock_factory.return_value
        mock_client.get_player_status.return_value = MOCK_DEVICE_DATA
        mock_client.close.return_value = None

        # First step: choose manual mode
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"discovery_mode": "manual"},
        )

        # Second step: provide host configuration
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            MOCK_CONFIG,
        )
        await hass.async_block_till_done()

        assert result3["type"] is FlowResultType.CREATE_ENTRY
        assert result3["title"] == "WiiM Mini"  # Uses device_name from enhanced naming
        assert result3["data"] == MOCK_CONFIG
        # Verify enhanced naming was called
        mock_enhanced_name.assert_called_once()


async def test_form_connection_error(hass: HomeAssistant) -> None:
    """Test connection error during config flow."""
    with (
        patch("custom_components.wiim.config_flow.async_search", None),
        patch(
            "custom_components.wiim.config_flow.wiim_factory_client",
            side_effect=Exception("Connection error"),
        ),
    ):
        # First step: choose manual mode
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"discovery_mode": "manual"},
        )

        # Second step: provide host configuration that will fail
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            MOCK_CONFIG,
        )

        assert result3["type"] is FlowResultType.FORM
        assert result3["errors"] == {"base": "unknown"}


async def test_form_timeout_error(hass: HomeAssistant) -> None:
    """Test timeout error during config flow."""
    with (
        patch("custom_components.wiim.config_flow.async_search", None),
        patch(
            "custom_components.wiim.config_flow.wiim_factory_client",
            side_effect=TimeoutError("Connection timeout"),
        ),
    ):
        # First step: choose manual mode
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"discovery_mode": "manual"},
        )

        # Second step: provide host configuration that will timeout
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            MOCK_CONFIG,
        )

        assert result3["type"] is FlowResultType.FORM
        assert result3["errors"] == {"base": "unknown"}


async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test device already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="WiiM Mini",
        data=MOCK_CONFIG,
        unique_id=MOCK_CONFIG["host"],
    )
    entry.add_to_hass(hass)

    with (
        patch("custom_components.wiim.config_flow.async_search", None),
        patch(
            "custom_components.wiim.config_flow.wiim_factory_client",
        ) as mock_factory,
        patch(
            "custom_components.wiim.config_flow._get_enhanced_device_name",
            return_value="WiiM Mini",
        ),
    ):
        # Mock the factory to return a client
        mock_client = mock_factory.return_value
        mock_client.get_player_status.return_value = MOCK_DEVICE_DATA
        mock_client.close.return_value = None

        # First step: choose manual mode
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"discovery_mode": "manual"},
        )

        # Second step: provide host configuration for already configured device
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            MOCK_CONFIG,
        )

        assert result3["type"] is FlowResultType.ABORT
        assert result3["reason"] == "already_configured"


async def test_form_invalid_host(hass: HomeAssistant) -> None:
    """Test invalid host error."""
    invalid_config = {"host": "invalid_host"}

    with (
        patch("custom_components.wiim.config_flow.async_search", None),
        patch(
            "custom_components.wiim.config_flow.wiim_factory_client",
            side_effect=Exception("Invalid host"),
        ),
    ):
        # First step: choose manual mode
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"discovery_mode": "manual"},
        )

        # Second step: provide invalid host configuration
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            invalid_config,
        )

        assert result3["type"] is FlowResultType.FORM
        assert result3["errors"] == {"base": "unknown"}


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="WiiM Mini",
        data=MOCK_CONFIG,
        unique_id=MOCK_CONFIG["host"],
    )
    entry.add_to_hass(hass)

    # Test options flow can be initialized
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM or result["type"] is FlowResultType.CREATE_ENTRY


async def test_enhanced_device_naming_master(hass: HomeAssistant) -> None:
    """Test enhanced device naming for master devices."""
    with (
        patch("custom_components.wiim.config_flow.async_search", None),
        patch(
            "custom_components.wiim.config_flow.wiim_factory_client",
        ) as mock_factory,
    ):
        # Mock the factory to return a client
        mock_client = mock_factory.return_value
        mock_client.get_player_status.return_value = MOCK_DEVICE_DATA
        mock_client.get_status.return_value = {"DeviceName": "Living Room", "device_name": "Living Room"}
        mock_client.get_multiroom_info.return_value = {
            "slave_list": [
                {"ip": "192.168.1.101", "name": "Kitchen"},
                {"ip": "192.168.1.102", "name": "Bedroom"},
            ]
        }
        mock_client.close.return_value = None

        # First step: choose manual mode
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"discovery_mode": "manual"},
        )

        # Second step: provide host configuration
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            MOCK_CONFIG,
        )
        await hass.async_block_till_done()

        assert result3["type"] is FlowResultType.CREATE_ENTRY
        # Should indicate it's a master of 2 devices
        assert "Master of 2 devices" in result3["title"]
        assert result3["data"] == MOCK_CONFIG


async def test_enhanced_device_naming_slave(hass: HomeAssistant) -> None:
    """Test enhanced device naming for slave devices."""
    with (
        patch("custom_components.wiim.config_flow.async_search", None),
        patch(
            "custom_components.wiim.config_flow.wiim_factory_client",
        ) as mock_factory,
    ):
        # Mock the factory to return a client
        mock_client = mock_factory.return_value
        mock_client.get_player_status.return_value = MOCK_DEVICE_DATA
        mock_client.get_status.return_value = {"DeviceName": "Kitchen", "device_name": "Kitchen"}
        mock_client.get_multiroom_info.return_value = {
            "type": "1",  # Indicates slave
            "slave_list": [],
        }
        mock_client.close.return_value = None

        # First step: choose manual mode
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"discovery_mode": "manual"},
        )

        # Second step: provide host configuration
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            MOCK_CONFIG,
        )
        await hass.async_block_till_done()

        assert result3["type"] is FlowResultType.CREATE_ENTRY
        # Should indicate it's in a group
        assert "(In Group)" in result3["title"]
        assert result3["data"] == MOCK_CONFIG
