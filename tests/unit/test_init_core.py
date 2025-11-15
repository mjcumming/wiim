"""Core integration tests for WiiM - following HA design patterns."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from pytest_homeassistant_custom_component.common import MockConfigEntry

from pywiim.exceptions import WiiMConnectionError, WiiMError, WiiMTimeoutError

from custom_components.wiim.const import DOMAIN
from tests.const import MOCK_CONFIG, MOCK_DEVICE_DATA


def _setup_mock_http(hass: HomeAssistant) -> None:
    """Helper to mock hass.http for tests that need it."""
    hass.http = Mock()
    hass.http.async_register_static_paths = AsyncMock()


class TestAsyncSetupEntry:
    """Test async_setup_entry - core integration setup."""

    @pytest.mark.asyncio
    async def test_setup_entry_success(self, hass: HomeAssistant, bypass_get_data) -> None:
        """Test successful setup of config entry."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini",
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert result is True
        assert entry.state is ConfigEntryState.LOADED
        assert DOMAIN in hass.data
        assert entry.entry_id in hass.data[DOMAIN]

    @pytest.mark.asyncio
    async def test_setup_entry_creates_coordinator(self, hass: HomeAssistant, bypass_get_data) -> None:
        """Test that coordinator is created during setup."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini",
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entry_data = hass.data[DOMAIN][entry.entry_id]
        assert "coordinator" in entry_data
        assert "client" in entry_data
        assert "speaker" in entry_data
        coordinator = entry_data["coordinator"]
        assert coordinator is not None
        assert coordinator.last_update_success is True

    @pytest.mark.asyncio
    async def test_setup_entry_creates_speaker(self, hass: HomeAssistant, bypass_get_data) -> None:
        """Test that speaker is created during setup."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini",
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entry_data = hass.data[DOMAIN][entry.entry_id]
        speaker = entry_data["speaker"]
        assert speaker is not None
        assert speaker.uuid == MOCK_DEVICE_DATA["uuid"]

    @pytest.mark.asyncio
    async def test_setup_entry_connection_error(self, hass: HomeAssistant) -> None:
        """Test setup failure due to connection error raises ConfigEntryNotReady."""
        _setup_mock_http(hass)

        entry = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini",
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )
        entry.add_to_hass(hass)

        with (
            patch(
                "custom_components.wiim.__init__.WiiMClient._detect_capabilities",
                return_value={},
            ),
            patch(
                "custom_components.wiim.coordinator.WiiMCoordinator.async_config_entry_first_refresh",
                side_effect=WiiMConnectionError("Connection failed"),
            ),
        ):
            # HA catches ConfigEntryNotReady and sets state to SETUP_RETRY
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        # Entry should be in retry state
        assert entry.state is ConfigEntryState.SETUP_RETRY

    @pytest.mark.asyncio
    async def test_setup_entry_timeout_error(self, hass: HomeAssistant) -> None:
        """Test setup failure due to timeout raises ConfigEntryNotReady."""
        _setup_mock_http(hass)

        entry = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini",
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )
        entry.add_to_hass(hass)

        with (
            patch(
                "custom_components.wiim.__init__.WiiMClient._detect_capabilities",
                return_value={},
            ),
            patch(
                "custom_components.wiim.coordinator.WiiMCoordinator.async_config_entry_first_refresh",
                side_effect=WiiMTimeoutError("Timeout"),
            ),
        ):
            # HA catches ConfigEntryNotReady and sets state to SETUP_RETRY
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        # Entry should be in retry state
        assert entry.state is ConfigEntryState.SETUP_RETRY

    @pytest.mark.asyncio
    async def test_setup_entry_generic_error(self, hass: HomeAssistant) -> None:
        """Test setup failure due to generic WiiM error raises ConfigEntryNotReady."""
        _setup_mock_http(hass)

        entry = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini",
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )
        entry.add_to_hass(hass)

        with (
            patch(
                "custom_components.wiim.__init__.WiiMClient._detect_capabilities",
                return_value={},
            ),
            patch(
                "custom_components.wiim.coordinator.WiiMCoordinator.async_config_entry_first_refresh",
                side_effect=WiiMError("Generic error"),
            ),
        ):
            # HA catches ConfigEntryNotReady and sets state to SETUP_RETRY
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        # Entry should be in retry state
        assert entry.state is ConfigEntryState.SETUP_RETRY

    @pytest.mark.asyncio
    async def test_setup_entry_capability_detection_failure(self, hass: HomeAssistant) -> None:
        """Test setup continues even if capability detection fails."""
        _setup_mock_http(hass)

        entry = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini",
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )
        entry.add_to_hass(hass)

        with (
            patch(
                "custom_components.wiim.__init__.WiiMClient._detect_capabilities",
                side_effect=Exception("Capability detection failed"),
            ),
            patch(
                "custom_components.wiim.coordinator.WiiMCoordinator.async_config_entry_first_refresh",
            ),
        ):
            # Should not raise - capability detection failure is handled gracefully
            result = await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

            # Setup should still succeed with empty capabilities
            assert result is True

    @pytest.mark.asyncio
    async def test_setup_entry_registers_services(self, hass: HomeAssistant, bypass_get_data) -> None:
        """Test that services are registered on first entry."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini",
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Check services are registered
        assert hass.services.has_service(DOMAIN, "reboot_device")
        assert hass.services.has_service(DOMAIN, "sync_time")

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Multiple entry setup test needs refinement - teardown behavior")
    async def test_setup_entry_multiple_entries(self, hass: HomeAssistant, bypass_get_data) -> None:
        """Test setup of multiple config entries."""
        # Use different UUIDs and hosts to avoid conflicts
        entry1 = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini 1",
            data={"host": "192.168.1.100"},
            unique_id="uuid-1",
        )
        entry1.add_to_hass(hass)

        entry2 = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini 2",
            data={"host": "192.168.1.101"},
            unique_id="uuid-2",
        )
        entry2.add_to_hass(hass)

        # Setup first entry
        result1 = await hass.config_entries.async_setup(entry1.entry_id)
        await hass.async_block_till_done()
        assert result1 is True

        # Setup second entry
        result2 = await hass.config_entries.async_setup(entry2.entry_id)
        await hass.async_block_till_done()
        assert result2 is True

        # Both setups should succeed
        assert result1 is True and result2 is True


class TestAsyncUnloadEntry:
    """Test async_unload_entry - integration teardown."""

    @pytest.mark.asyncio
    async def test_unload_entry_success(self, hass: HomeAssistant, bypass_get_data) -> None:
        """Test successful unload of config entry."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini",
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED

        result = await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        assert result is True
        assert entry.state is ConfigEntryState.NOT_LOADED
        assert entry.entry_id not in hass.data[DOMAIN]

    @pytest.mark.asyncio
    async def test_unload_entry_removes_speaker(self, hass: HomeAssistant, bypass_get_data) -> None:
        """Test that speaker is removed from hass.data on unload."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini",
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Verify speaker exists
        assert entry.entry_id in hass.data[DOMAIN]
        assert "speaker" in hass.data[DOMAIN][entry.entry_id]

        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        # Verify speaker is removed
        assert entry.entry_id not in hass.data[DOMAIN]


class TestAsyncReloadEntry:
    """Test async_reload_entry - integration reload."""

    @pytest.mark.asyncio
    async def test_reload_entry_success(self, hass: HomeAssistant, bypass_get_data) -> None:
        """Test successful reload of config entry."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini",
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED
        assert entry.entry_id in hass.data[DOMAIN]

    @pytest.mark.asyncio
    async def test_reload_entry_recreates_coordinator(self, hass: HomeAssistant, bypass_get_data) -> None:
        """Test that coordinator is recreated on reload."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini",
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Get original coordinator
        original_coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

        # Get new coordinator
        new_coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

        # Should be different objects (recreated)
        assert new_coordinator is not original_coordinator
        assert new_coordinator is not None
