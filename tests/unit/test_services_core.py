"""Core service tests for WiiM - testing service registration and execution."""

from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wiim.const import DOMAIN
from tests.const import MOCK_CONFIG, MOCK_DEVICE_DATA


class TestServiceRegistration:
    """Test service registration."""

    @pytest.mark.asyncio
    async def test_services_registered_on_first_entry(self, hass: HomeAssistant, bypass_get_data) -> None:
        """Test that services are registered when first entry is set up."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini",
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Services should be registered
        assert hass.services.has_service(DOMAIN, "reboot_device")
        assert hass.services.has_service(DOMAIN, "sync_time")

    @pytest.mark.asyncio
    async def test_services_not_duplicated_on_second_entry(self, hass: HomeAssistant, bypass_get_data) -> None:
        """Test that services are not registered multiple times."""
        entry1 = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini 1",
            data={**MOCK_CONFIG, "host": "192.168.1.100"},
            unique_id="uuid-1",
        )
        entry1.add_to_hass(hass)

        entry2 = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini 2",
            data={**MOCK_CONFIG, "host": "192.168.1.101"},
            unique_id="uuid-2",
        )
        entry2.add_to_hass(hass)

        await hass.config_entries.async_setup(entry1.entry_id)
        await hass.async_block_till_done()

        await hass.config_entries.async_setup(entry2.entry_id)
        await hass.async_block_till_done()

        # Services should still be registered (not duplicated)
        assert hass.services.has_service(DOMAIN, "reboot_device")
        assert hass.services.has_service(DOMAIN, "sync_time")


class TestRebootDeviceService:
    """Test reboot_device service."""

    @pytest.mark.asyncio
    async def test_reboot_device_service_success(self, hass: HomeAssistant, bypass_get_data) -> None:
        """Test reboot_device service executes successfully."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini",
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Create a media player entity with state
        entity_registry = er.async_get(hass)
        device_registry = dr.async_get(hass)

        device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, MOCK_DEVICE_DATA["uuid"])},
        )

        entity_id = "media_player.wiim_mini"
        entity_registry.async_get_or_create(
            "media_player",
            DOMAIN,
            f"{MOCK_DEVICE_DATA['uuid']}_media_player",
            suggested_object_id="wiim_mini",
            device_id=device.id,
        )

        # Set entity state so hass.states.get() can find it
        hass.states.async_set(entity_id, "idle")

        # Mock the client reboot method
        speaker = hass.data[DOMAIN][entry.entry_id]["speaker"]
        speaker.coordinator.player.client.reboot = AsyncMock(return_value=True)

        # Call the service
        await hass.services.async_call(
            DOMAIN,
            "reboot_device",
            {"entity_id": entity_id},
            blocking=True,
        )

        # Verify reboot was called
        speaker.coordinator.player.client.reboot.assert_called_once()

    @pytest.mark.asyncio
    async def test_reboot_device_service_missing_entity_id(self, hass: HomeAssistant, bypass_get_data) -> None:
        """Test reboot_device service handles missing entity_id."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini",
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Call service without entity_id
        await hass.services.async_call(
            DOMAIN,
            "reboot_device",
            {},
            blocking=True,
        )

        # Should not raise - error is logged but service completes

    @pytest.mark.asyncio
    async def test_reboot_device_service_invalid_entity(self, hass: HomeAssistant, bypass_get_data) -> None:
        """Test reboot_device service handles invalid entity."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini",
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Call service with non-existent entity
        await hass.services.async_call(
            DOMAIN,
            "reboot_device",
            {"entity_id": "media_player.nonexistent"},
            blocking=True,
        )

        # Should not raise - error is logged but service completes


class TestSyncTimeService:
    """Test sync_time service."""

    @pytest.mark.asyncio
    async def test_sync_time_service_success(self, hass: HomeAssistant, bypass_get_data) -> None:
        """Test sync_time service executes successfully."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini",
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Create a media player entity with state
        entity_registry = er.async_get(hass)
        device_registry = dr.async_get(hass)

        device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, MOCK_DEVICE_DATA["uuid"])},
        )

        entity_id = "media_player.wiim_mini"
        entity_registry.async_get_or_create(
            "media_player",
            DOMAIN,
            f"{MOCK_DEVICE_DATA['uuid']}_media_player",
            suggested_object_id="wiim_mini",
            device_id=device.id,
        )

        # Set entity state so hass.states.get() can find it
        hass.states.async_set(entity_id, "idle")

        # Mock the client sync_time method
        speaker = hass.data[DOMAIN][entry.entry_id]["speaker"]
        speaker.coordinator.player.client.sync_time = AsyncMock(return_value=True)

        # Call the service
        await hass.services.async_call(
            DOMAIN,
            "sync_time",
            {"entity_id": entity_id},
            blocking=True,
        )

        # Verify sync_time was called
        speaker.coordinator.player.client.sync_time.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_time_service_error_handling(self, hass: HomeAssistant, bypass_get_data) -> None:
        """Test sync_time service handles errors."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini",
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Create a media player entity with state
        entity_registry = er.async_get(hass)
        device_registry = dr.async_get(hass)

        device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, MOCK_DEVICE_DATA["uuid"])},
        )

        entity_id = "media_player.wiim_mini"
        entity_registry.async_get_or_create(
            "media_player",
            DOMAIN,
            f"{MOCK_DEVICE_DATA['uuid']}_media_player",
            suggested_object_id="wiim_mini",
            device_id=device.id,
        )

        # Set entity state so hass.states.get() can find it
        hass.states.async_set(entity_id, "idle")

        # Mock the client sync_time method to raise an error
        speaker = hass.data[DOMAIN][entry.entry_id]["speaker"]
        speaker.coordinator.player.client.sync_time = AsyncMock(side_effect=Exception("Sync failed"))

        # Call the service - should raise an error (service re-raises the exception)
        with pytest.raises(Exception, match="Sync failed"):
            await hass.services.async_call(
                DOMAIN,
                "sync_time",
                {"entity_id": entity_id},
                blocking=True,
            )
