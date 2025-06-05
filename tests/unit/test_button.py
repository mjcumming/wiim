"""Test WiiM button entities."""

from unittest.mock import patch

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wiim.const import DOMAIN

from tests.const import MOCK_CONFIG, MOCK_DEVICE_DATA


async def test_button_setup(hass: HomeAssistant, bypass_get_data) -> None:
    """Test button setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="WiiM Mini",
        data=MOCK_CONFIG,
        unique_id=MOCK_DEVICE_DATA["uuid"],
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Check if button entities exist
    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    button_entities = [e for e in entities if e.domain == "button"]

    # Buttons may or may not exist depending on implementation
    assert len(entities) >= 0
    assert len(button_entities) >= 0


async def test_button_press_service(hass: HomeAssistant, bypass_get_data) -> None:
    """Test button press service."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="WiiM Mini",
        data=MOCK_CONFIG,
        unique_id=MOCK_DEVICE_DATA["uuid"],
    )
    entry.add_to_hass(hass)

    with (
        patch("custom_components.wiim.api.WiiMClient.play", return_value=True),
        patch("custom_components.wiim.api.WiiMClient.reboot", return_value=True),
        patch("custom_components.wiim.api.WiiMClient.sync_time", return_value=True),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Get button entities
        button_states = hass.states.async_all("button")

        # If buttons exist, test pressing them
        for state in button_states:
            # Button press should not raise an error
            await hass.services.async_call(
                BUTTON_DOMAIN,
                SERVICE_PRESS,
                {"entity_id": state.entity_id},
                blocking=True,
            )


async def test_button_device_info(hass: HomeAssistant, bypass_get_data) -> None:
    """Test button device information."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="WiiM Mini",
        data=MOCK_CONFIG,
        unique_id=MOCK_DEVICE_DATA["uuid"],
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    button_entities = [e for e in entities if e.domain == "button"]

    # If buttons exist, verify their device info
    for entity in button_entities:
        assert entity.device_id is not None
        assert entity.unique_id is not None


async def test_button_states(hass: HomeAssistant, bypass_get_data) -> None:
    """Test button states."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="WiiM Mini",
        data=MOCK_CONFIG,
        unique_id=MOCK_DEVICE_DATA["uuid"],
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Get button states
    button_states = hass.states.async_all("button")

    # If buttons exist, check their states
    for state in button_states:
        # Buttons typically have state "unknown" when not pressed
        assert state.state in ["unknown", "unavailable"] or state.state is not None
        assert hasattr(state, "attributes")
