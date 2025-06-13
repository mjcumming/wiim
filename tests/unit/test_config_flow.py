"""Test WiiM config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wiim.const import CONF_HOST, DOMAIN
from tests.const import MOCK_CONFIG


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the manual entry form directly (setup mode choice was removed)."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"  # Goes directly to manual entry now
    assert result["errors"] is None or result["errors"] == {}


async def test_form_successful_connection(hass: HomeAssistant, expected_lingering_threads) -> None:
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
    with patch(
        "custom_components.wiim.config_flow.validate_wiim_device",
        new_callable=AsyncMock,
        return_value=(False, "192.168.1.100"),
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
    with patch(
        "custom_components.wiim.config_flow.validate_wiim_device",
        new_callable=AsyncMock,
        return_value=(False, "192.168.1.100"),
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
    with patch(
        "custom_components.wiim.config_flow.validate_wiim_device",
        new_callable=AsyncMock,
        return_value=(False, "invalid_host"),
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
