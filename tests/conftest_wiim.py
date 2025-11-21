"""WiiM-specific pytest fixtures."""

# Import our components for testing
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry

# Import WiiM components at module level
from custom_components.wiim.const import DOMAIN
from custom_components.wiim.data import Speaker


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
    # Create mock Player object with all properties
    mock_player = MagicMock()
    mock_player.client = wiim_client
    mock_player.host = "192.168.1.100"

    # Playback state properties
    mock_player.volume_level = 0.5
    mock_player.is_muted = False
    mock_player.play_state = "stop"

    # Role and group properties
    mock_player.role = "solo"
    mock_player.is_master = False
    mock_player.is_slave = False
    mock_player.is_solo = True
    mock_player.group = None

    # Media properties
    mock_player.media_title = None
    mock_player.media_artist = None
    mock_player.media_album = None
    mock_player.media_duration = None
    mock_player.media_position = None
    mock_player.media_image_url = None
    mock_player.source = None

    # Audio quality properties
    mock_player.media_sample_rate = None
    mock_player.media_bit_depth = None
    mock_player.media_bit_rate = None
    mock_player.media_codec = None

    # Device info properties
    mock_player.name = "Test WiiM"
    mock_player.model = "WiiM Mini"
    mock_player.firmware = "1.0.0"
    mock_player.uuid = "test-speaker-uuid"
    mock_player.mac_address = "aa:bb:cc:dd:ee:ff"

    # Additional properties
    mock_player.eq_preset = None
    mock_player.wifi_rssi = None
    mock_player.shuffle = None
    mock_player.repeat = None
    mock_player.available_sources = []

    # Methods
    mock_player.refresh = AsyncMock()
    mock_player.reboot = AsyncMock()

    # Create coordinator with simplified data structure
    coordinator = MagicMock()
    coordinator.player = wiim_client
    coordinator.player = mock_player
    coordinator.data = {"player": mock_player}
    coordinator.last_update_success = True
    coordinator.async_request_refresh = AsyncMock()
    coordinator.record_user_command = MagicMock()
    return coordinator


@pytest.fixture
def wiim_speaker(hass, wiim_coordinator):
    """Create a test Speaker instance."""
    # Set up coordinator.player.host for ip_address property
    wiim_coordinator.player.host = "192.168.1.100"

    # Set up coordinator.data for other properties
    wiim_coordinator.data = {
        "device_name": "Test WiiM",
        "model": "WiiM Mini",
        "role": "solo",
        "firmware": "1.0.0",
    }

    # Create a mock config entry
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.entry_id = "test_wiim_entry"
    config_entry.unique_id = "test-speaker-uuid"
    config_entry.data = {"host": "192.168.1.100"}
    config_entry.options = {}
    config_entry.title = "Test WiiM"

    speaker = Speaker(hass, wiim_coordinator, config_entry)

    # Emulate the data structure the integration uses at runtime so helper
    # functions (e.g. find_speaker_by_uuid) work inside the tests.
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {"speaker": speaker}

    return speaker


@pytest.fixture
def wiim_speaker_slave(hass):
    """Create a test slave Speaker instance."""
    # Create mock Player object for slave
    slave_player = MagicMock()
    slave_player.host = "192.168.1.101"

    # Role properties - slave
    slave_player.role = "slave"
    slave_player.is_master = False
    slave_player.is_slave = True
    slave_player.is_solo = False
    slave_player.group = None  # Will be set in group tests

    # Other properties
    slave_player.volume_level = 0.5
    slave_player.is_muted = False
    slave_player.play_state = "stop"
    slave_player.name = "Test Slave"
    slave_player.model = "WiiM Pro"
    slave_player.uuid = "test-slave-uuid"

    # Create mock coordinator for slave
    slave_coordinator = MagicMock()
    slave_coordinator.player = slave_player.client
    slave_coordinator.player = slave_player
    slave_coordinator.data = {"player": slave_player}
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
