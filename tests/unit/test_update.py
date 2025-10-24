"""Unit tests for WiiM update platform."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestWiiMFirmwareUpdateEntity:
    """Test WiiM Firmware Update Entity."""

    async def test_update_entity_creation(self):
        """Test update entity creation."""
        from custom_components.wiim.update import WiiMFirmwareUpdateEntity

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"

        update_entity = WiiMFirmwareUpdateEntity(speaker)

        assert update_entity.speaker is speaker
        assert update_entity.unique_id == "test-speaker-uuid_fw_update"
        assert update_entity.name == "Firmware Update"
        assert update_entity.device_class == "firmware"
        assert update_entity.supported_features == 1  # INSTALL feature

    def test_installed_version_with_device_model(self):
        """Test installed version when device model is available."""
        from custom_components.wiim.update import WiiMFirmwareUpdateEntity

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.device_model = MagicMock()
        speaker.device_model.firmware = "1.0.0"

        update_entity = WiiMFirmwareUpdateEntity(speaker)
        assert update_entity.installed_version == "1.0.0"

    def test_installed_version_no_device_model(self):
        """Test installed version when device model is None."""
        from custom_components.wiim.update import WiiMFirmwareUpdateEntity

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.device_model = None

        update_entity = WiiMFirmwareUpdateEntity(speaker)
        assert update_entity.installed_version is None

    def test_latest_version_with_valid_version(self):
        """Test latest version when a valid version is available."""
        from custom_components.wiim.update import WiiMFirmwareUpdateEntity

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.device_model = MagicMock()
        speaker.device_model.latest_version = "1.0.1"

        update_entity = WiiMFirmwareUpdateEntity(speaker)
        assert update_entity.latest_version == "1.0.1"

    def test_latest_version_with_invalid_versions(self):
        """Test latest version with various invalid version values."""
        from custom_components.wiim.update import WiiMFirmwareUpdateEntity

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.device_model = MagicMock()

        update_entity = WiiMFirmwareUpdateEntity(speaker)

        # Test invalid values that should return None
        for invalid_version in ["0", 0, "", "-", " ", None]:
            speaker.device_model.latest_version = invalid_version
            assert update_entity.latest_version is None

    def test_latest_version_no_device_model(self):
        """Test latest version when device model is None."""
        from custom_components.wiim.update import WiiMFirmwareUpdateEntity

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.device_model = None

        update_entity = WiiMFirmwareUpdateEntity(speaker)
        assert update_entity.latest_version is None

    def test_available_with_update_available(self):
        """Test available property when update is available."""
        from custom_components.wiim.update import WiiMFirmwareUpdateEntity

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.device_model = MagicMock()
        speaker.device_model.version_update = True

        update_entity = WiiMFirmwareUpdateEntity(speaker)
        assert update_entity.available is True

    def test_available_with_no_update(self):
        """Test available property when no update is available."""
        from custom_components.wiim.update import WiiMFirmwareUpdateEntity

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.device_model = MagicMock()
        speaker.device_model.version_update = False

        update_entity = WiiMFirmwareUpdateEntity(speaker)
        assert update_entity.available is False

    def test_available_no_device_model(self):
        """Test available property when device model is None."""
        from custom_components.wiim.update import WiiMFirmwareUpdateEntity

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.device_model = None

        update_entity = WiiMFirmwareUpdateEntity(speaker)
        assert update_entity.available is False

    @pytest.mark.asyncio
    async def test_async_install_success(self):
        """Test async install with successful reboot."""
        from custom_components.wiim.update import WiiMFirmwareUpdateEntity

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.coordinator = MagicMock()
        speaker.coordinator.client = MagicMock()
        speaker.coordinator.client.reboot = AsyncMock()

        update_entity = WiiMFirmwareUpdateEntity(speaker)

        await update_entity.async_install("1.0.1", False)

        speaker.coordinator.client.reboot.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_install_with_error(self):
        """Test async install with API error."""
        from custom_components.wiim.update import WiiMFirmwareUpdateEntity

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.coordinator = MagicMock()
        speaker.coordinator.client = MagicMock()
        speaker.coordinator.client.reboot = AsyncMock(side_effect=Exception("Network error"))

        update_entity = WiiMFirmwareUpdateEntity(speaker)

        with pytest.raises(Exception, match="Network error"):
            await update_entity.async_install("1.0.1", False)


class TestUpdatePlatformSetup:
    """Test update platform setup functionality."""

    @pytest.mark.asyncio
    async def test_async_setup_entry(self):
        """Test update platform setup."""
        from custom_components.wiim.update import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()

        # Mock speaker lookup
        speaker = MagicMock()
        speaker.name = "Test WiiM"

        with patch("custom_components.wiim.update.get_speaker_from_config_entry", return_value=speaker):
            entities = []
            async_add_entities = MagicMock()

            await async_setup_entry(hass, config_entry, async_add_entities)

            # Verify entities were created
            async_add_entities.assert_called_once()
            entities = async_add_entities.call_args[0][0]

            # Should create exactly one update entity
            assert len(entities) == 1
            assert entities[0].__class__.__name__ == "WiiMFirmwareUpdateEntity"
