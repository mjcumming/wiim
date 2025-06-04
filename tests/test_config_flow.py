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
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None or result["errors"] == {}


async def test_form_successful_connection(hass: HomeAssistant) -> None:
    """Test successful connection during config flow."""
    with (
        patch(
            "custom_components.wiim.config_flow.WiiMClient.get_status",
            return_value=MOCK_DEVICE_DATA,
        ),
        patch(
            "custom_components.wiim.config_flow.WiiMClient.close",
            return_value=None,
        ),
    ):
        # Provide host configuration
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_CONFIG
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert "WiiM" in result["title"]  # Should contain device name
        assert result["data"] == {
            **MOCK_CONFIG,
            "uuid": MOCK_DEVICE_DATA.get("uuid", MOCK_DEVICE_DATA.get("MAC", "").replace(":", "")),
        }


async def test_form_connection_error(hass: HomeAssistant) -> None:
    """Test connection error during config flow."""
    with patch(
        "custom_components.wiim.config_flow.WiiMClient.get_status",
        side_effect=Exception("Connection error"),
    ):
        # Provide host configuration that will fail
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_CONFIG
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}


async def test_form_timeout_error(hass: HomeAssistant) -> None:
    """Test timeout error during config flow."""
    with patch(
        "custom_components.wiim.config_flow.WiiMClient.get_status",
        side_effect=TimeoutError("Connection timeout"),
    ):
        # Provide host configuration that will timeout
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_CONFIG
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}


async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test device already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="WiiM Mini",
        data=MOCK_CONFIG,
        unique_id=MOCK_DEVICE_DATA.get("uuid", MOCK_DEVICE_DATA.get("MAC", "").replace(":", "")),
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.wiim.config_flow.WiiMClient.get_status",
            return_value=MOCK_DEVICE_DATA,
        ),
        patch(
            "custom_components.wiim.config_flow.WiiMClient.close",
            return_value=None,
        ),
    ):
        # Provide host configuration for already configured device
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_CONFIG
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_form_invalid_host(hass: HomeAssistant) -> None:
    """Test invalid host error."""
    invalid_config = {"host": "invalid_host"}

    with patch(
        "custom_components.wiim.config_flow.WiiMClient.get_status",
        side_effect=Exception("Invalid host"),
    ):
        # Provide invalid host configuration
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=invalid_config
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}


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
    master_device_data = {**MOCK_DEVICE_DATA, "DeviceName": "Living Room", "device_name": "Living Room"}

    with (
        patch(
            "custom_components.wiim.config_flow.WiiMClient.get_status",
            return_value=master_device_data,
        ),
        patch(
            "custom_components.wiim.config_flow.WiiMClient.close",
            return_value=None,
        ),
    ):
        # Provide host configuration
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_CONFIG
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert "Living Room" in result["title"]
        assert result["data"]["host"] == MOCK_CONFIG["host"]


async def test_enhanced_device_naming_slave(hass: HomeAssistant) -> None:
    """Test enhanced device naming for slave devices."""
    slave_device_data = {**MOCK_DEVICE_DATA, "DeviceName": "Kitchen", "device_name": "Kitchen"}

    with (
        patch(
            "custom_components.wiim.config_flow.WiiMClient.get_status",
            return_value=slave_device_data,
        ),
        patch(
            "custom_components.wiim.config_flow.WiiMClient.close",
            return_value=None,
        ),
    ):
        # Provide host configuration
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_CONFIG
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert "Kitchen" in result["title"]
        assert result["data"]["host"] == MOCK_CONFIG["host"]
