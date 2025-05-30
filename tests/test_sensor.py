"""Test WiiM sensor entities."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wiim.const import DOMAIN

from .const import MOCK_CONFIG, MOCK_DEVICE_DATA


async def test_sensor_setup(hass: HomeAssistant, bypass_get_data) -> None:
    """Test sensor setup and entity creation."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="WiiM Mini",
        data=MOCK_CONFIG,
        unique_id=MOCK_DEVICE_DATA["uuid"],
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Verify integration loaded
    assert entry.state.name == "loaded"

    # Check that sensor entities were created
    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    sensor_entities = [e for e in entities if e.domain == "sensor"]

    assert len(sensor_entities) > 0, "No sensor entities were created"


async def test_sensor_states(hass: HomeAssistant, bypass_get_data) -> None:
    """Test sensor states and attributes."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="WiiM Mini",
        data=MOCK_CONFIG,
        unique_id=MOCK_DEVICE_DATA["uuid"],
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Get all sensor states
    sensor_states = hass.states.async_all("sensor")
    assert len(sensor_states) > 0, "No sensor states found"

    # Test that sensors have valid states
    for state in sensor_states:
        assert state.state not in ["unknown", "unavailable", None]
        assert hasattr(state, "attributes")


async def test_sensor_device_info(hass: HomeAssistant, bypass_get_data) -> None:
    """Test sensor device information."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="WiiM Mini",
        data=MOCK_CONFIG,
        unique_id=MOCK_DEVICE_DATA["uuid"],
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Check device registry
    device_registry = dr.async_get(hass)
    assert len(device_registry.devices) > 0, "No devices registered"


async def test_sensor_unique_ids(hass: HomeAssistant, bypass_get_data) -> None:
    """Test sensor unique IDs are properly set."""
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
    sensor_entities = [e for e in entities if e.domain == "sensor"]

    # All sensors should have unique IDs
    for entity in sensor_entities:
        assert entity.unique_id is not None
        assert entity.unique_id != ""
