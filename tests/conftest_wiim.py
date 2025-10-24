"""WiiM-specific pytest fixtures."""

# Import our components for testing
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def wiim_config_entry():
    """Create a WiiM config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.domain = "wiim"
    entry.entry_id = "test_wiim_entry"
    entry.data = {"host": "192.168.1.100", "name": "Test WiiM"}
    return entry


@pytest.fixture
def wiim_client():
    """Create a mock WiiM client."""
    client = AsyncMock()
    client.host = "192.168.1.100"

    # Mock the internal _request method for API endpoint testing
    client._request = AsyncMock()

    # Add actual API methods for testing
    client.set_source = AsyncMock(return_value=True)

    # Mock common API responses
    client.get_status.return_value = {
        "uuid": "test-speaker-uuid",
        "DeviceName": "Test WiiM",
        "project": "WiiM Mini",
        "firmware": "1.0.0",
        "MAC": "aa:bb:cc:dd:ee:ff",
        "vol": "50",
        "mute": "0",
        "status": "stop",
    }

    client.get_multiroom_status.return_value = {"slaves": 0, "slave_list": []}

    client.send_command.return_value = {"raw": "OK"}
    return client


@pytest.fixture
def wiim_coordinator(wiim_client):
    """Create a mock WiiM coordinator."""
    coordinator = MagicMock()
    coordinator.client = wiim_client
    coordinator.data = {
        "status": {
            "uuid": "test-speaker-uuid",
            "DeviceName": "Test WiiM",
            "project": "WiiM Mini",
            "firmware": "1.0.0",
            "MAC": "aa:bb:cc:dd:ee:ff",
            "vol": "50",
            "mute": "0",
            "status": "stop",
        },
        "multiroom": {"role": "solo", "slaves": 0},
        "role": "solo",
        "polling": {
            "interval": 5,
            "is_playing": False,
            "api_capabilities": {
                "statusex_supported": True,
                "metadata_supported": True,
                "eq_supported": True,
            },
        },
    }
    coordinator.last_update_success = True
    coordinator.async_request_refresh = AsyncMock()
    coordinator.record_user_command = MagicMock()
    return coordinator


@pytest.fixture
def wiim_speaker(hass, wiim_coordinator):
    """Create a test Speaker instance."""
    from homeassistant.config_entries import ConfigEntry

    from custom_components.wiim.const import DOMAIN
    from custom_components.wiim.data import Speaker

    # Create a mock config entry
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.unique_id = "test-speaker-uuid"
    config_entry.data = {"host": "192.168.1.100"}
    config_entry.options = {}
    config_entry.title = "Test WiiM"

    speaker = Speaker(hass, wiim_coordinator, config_entry)
    speaker.ip_address = "192.168.1.100"  # Use correct attribute name
    speaker.name = "Test WiiM"
    speaker.model = "WiiM Mini"
    speaker.role = "solo"

    # Emulate the data structure the integration uses at runtime so helper
    # functions (e.g. find_speaker_by_uuid) work inside the tests.
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {"speaker": speaker}

    return speaker


@pytest.fixture
def wiim_speaker_slave(hass):
    """Create a test slave Speaker instance."""
    from homeassistant.config_entries import ConfigEntry

    from custom_components.wiim.const import DOMAIN
    from custom_components.wiim.data import Speaker

    # Create mock coordinator for slave
    slave_coordinator = MagicMock()
    slave_coordinator.client = AsyncMock()
    slave_coordinator.client.host = "192.168.1.101"
    slave_coordinator.data = {
        "status": {
            "uuid": "test-slave-uuid",
            "DeviceName": "Test Slave",
            "project": "WiiM Pro",
        },
        "multiroom": {"role": "slave"},
    }
    slave_coordinator.last_update_success = True
    slave_coordinator.async_request_refresh = AsyncMock()

    # Create a mock config entry for slave
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.unique_id = "test-slave-uuid"
    config_entry.data = {"host": "192.168.1.101"}
    config_entry.options = {}
    config_entry.title = "Test Slave"

    speaker = Speaker(hass, slave_coordinator, config_entry)
    speaker.ip_address = "192.168.1.101"  # Use correct attribute name
    speaker.name = "Test Slave"
    speaker.model = "WiiM Pro"
    speaker.role = "slave"

    # Register slave speaker in hass.data for helper lookups
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {"speaker": speaker}

    return speaker


@pytest.fixture
def mock_wiim_device_registry():
    """Mock Home Assistant device registry for WiiM tests."""
    with patch("custom_components.wiim.data.dr") as mock_dr:
        registry = MagicMock()
        mock_dr.async_get.return_value = registry

        device_entry = MagicMock()
        device_entry.id = "mock_device_id"
        registry.async_get_or_create.return_value = device_entry

        yield registry


@pytest.fixture
def mock_wiim_dispatcher():
    """Mock Home Assistant dispatcher for WiiM tests."""
    with patch("custom_components.wiim.data.async_dispatcher_send") as mock_send:
        yield mock_send


# ---------------------------------------------------------------------------
# Global fixture: allow HA safe-shutdown helper thread to linger without
# failing pytest-homeassistant cleanup assertions.  When this fixture returns
# True the plugin downgrades lingering-thread assertions to warnings.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def allow_unwatched_threads() -> bool:  # noqa: D401 – simple fixture
    """Tell pytest-homeassistant that background threads are expected."""
    return True
