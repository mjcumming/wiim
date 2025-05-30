"""Test WiiM config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wiim.const import DOMAIN

from .const import MOCK_CONFIG, MOCK_DEVICE_DATA


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}


async def test_form_successful_connection(hass: HomeAssistant) -> None:
    """Test successful connection during config flow."""
    with (
        patch(
            "custom_components.wiim.api.WiiMClient.get_device_info",
            return_value=MOCK_DEVICE_DATA,
        ),
        patch(
            "custom_components.wiim.config_flow.WiiMConfigFlow._test_connection",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_CONFIG,
        )
        await hass.async_block_till_done()

        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == "WiiM Mini"
        assert result2["data"] == MOCK_CONFIG


async def test_form_connection_error(hass: HomeAssistant) -> None:
    """Test connection error during config flow."""
    with patch(
        "custom_components.wiim.api.WiiMClient.get_device_info",
        side_effect=Exception("Connection error"),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_CONFIG,
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_timeout_error(hass: HomeAssistant) -> None:
    """Test timeout error during config flow."""
    with patch(
        "custom_components.wiim.api.WiiMClient.get_device_info",
        side_effect=TimeoutError("Connection timeout"),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_CONFIG,
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"] == {"base": "timeout_connect"}


async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test device already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="WiiM Mini",
        data=MOCK_CONFIG,
        unique_id=MOCK_DEVICE_DATA["uuid"],
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.wiim.api.WiiMClient.get_device_info",
        return_value=MOCK_DEVICE_DATA,
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_CONFIG,
        )

        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "already_configured"


async def test_form_invalid_host(hass: HomeAssistant) -> None:
    """Test invalid host error."""
    invalid_config = {"host": "invalid_host"}

    with patch(
        "custom_components.wiim.api.WiiMClient.get_device_info",
        side_effect=Exception("Invalid host"),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            invalid_config,
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"] == {"base": "cannot_connect"}


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="WiiM Mini",
        data=MOCK_CONFIG,
        unique_id=MOCK_DEVICE_DATA["uuid"],
    )
    entry.add_to_hass(hass)

    # Test options flow can be initialized
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM or result["type"] is FlowResultType.CREATE_ENTRY
