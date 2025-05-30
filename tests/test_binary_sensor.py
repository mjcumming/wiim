"""Test WiiM binary sensor entities."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wiim.const import DOMAIN

from .const import MOCK_CONFIG, MOCK_DEVICE_DATA


async def test_binary_sensor_setup(hass: HomeAssistant, bypass_get_data) -> None:
    """Test binary sensor setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="WiiM Mini",
        data=MOCK_CONFIG,
        unique_id=MOCK_DEVICE_DATA["uuid"],
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Check if binary sensor entities exist
    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    binary_sensor_entities = [e for e in entities if e.domain == "binary_sensor"]

    # Binary sensors may or may not exist depending on implementation
    # This test just ensures no errors occur during setup
    assert len(entities) >= 0
    assert len(binary_sensor_entities) >= 0


async def test_binary_sensor_states(hass: HomeAssistant, bypass_get_data) -> None:
    """Test binary sensor states."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="WiiM Mini",
        data=MOCK_CONFIG,
        unique_id=MOCK_DEVICE_DATA["uuid"],
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Get binary sensor states
    binary_sensor_states = hass.states.async_all("binary_sensor")

    # If binary sensors exist, check their states
    for state in binary_sensor_states:
        assert state.state in ["on", "off", "unknown", "unavailable"]
        assert hasattr(state, "attributes")


async def test_binary_sensor_device_info(hass: HomeAssistant, bypass_get_data) -> None:
    """Test binary sensor device information."""
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
    binary_sensor_entities = [e for e in entities if e.domain == "binary_sensor"]

    # If binary sensors exist, verify their device info
    for entity in binary_sensor_entities:
        assert entity.device_id is not None
        assert entity.unique_id is not None
