"""Global fixtures for WiiM integration tests."""

# Ensure the stubbed Home Assistant package is importable before any test modules
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry

# Add repository root to path for custom_components imports
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

STUBS_DIR = REPO_ROOT / "stubs"
if str(STUBS_DIR) not in sys.path:
    sys.path.insert(0, str(STUBS_DIR))

# Import WiiM components at module level
from custom_components.wiim.const import DOMAIN  # noqa: E402

from .const import MOCK_DEVICE_DATA, MOCK_STATUS_RESPONSE  # noqa: E402

# Import realistic player fixtures

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture
def event_loop() -> asyncio.AbstractEventLoop:
    """Provide legacy `event_loop` fixture for HA pytest plugin compatibility.

    Newer pytest-asyncio versions no longer provide the `event_loop` fixture by
    default, but pytest-homeassistant-custom-component still depends on it (via
    its autouse `enable_event_loop_debug` fixture).
    """
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


@pytest.fixture(scope="session", autouse=True)
def preload_aiodns_pycares_thread() -> None:
    """Preload aiohttp's AsyncResolver so pycares thread exists before tests.

    pytest-homeassistant-custom-component tracks threads created during each test
    and fails if any new non-dummy threads are spawned. aiohttp/aiodns/pycares can
    start a long-lived background thread (target: _run_safe_shutdown_loop) the
    first time an AsyncResolver is instantiated (often during the first HA
    ClientSession creation).

    By instantiating AsyncResolver once at session start, that thread exists
    before per-test thread snapshots are taken, avoiding a one-off failure in the
    first test that triggers HA HTTP session creation.
    """
    try:
        import asyncio

        from aiohttp.resolver import AsyncResolver
    except Exception:  # pragma: no cover
        return

    # Create a temporary loop to satisfy AsyncResolver initialization.
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        AsyncResolver(loop=loop)  # Intentionally not closed; avoids thread delta in tests
    finally:
        asyncio.set_event_loop(None)
        loop.close()


# ============================================================================
# Autouse Fixtures (applied to all tests automatically)
# ============================================================================


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    yield


@pytest.fixture(name="skip_notifications", autouse=True)
def skip_notifications_fixture():
    """Skip notification calls to prevent test failures."""
    with (
        patch("homeassistant.components.persistent_notification.async_create"),
        patch("homeassistant.components.persistent_notification.async_dismiss"),
    ):
        yield


@pytest.fixture(autouse=True)
def allow_unwatched_threads() -> bool:  # noqa: D401 – simple fixture
    """Tell pytest-homeassistant that background threads are expected."""
    return True


@pytest.fixture(autouse=True)
def fix_storage_mock():
    """Fix storage mock to work with current HA core version.

    pytest-homeassistant-custom-component's storage mock has a bug where
    _async_write_data mock doesn't accept the correct number of arguments.
    This fixture patches it to work correctly.

    The external fixture from pytest-homeassistant-custom-component creates
    a mock that only accepts 2 args (path, data) but HA core calls it with
    3 args (self, path, data). We override it with a proper mock.
    """
    from unittest.mock import patch

    async def mock_async_write_data(self, path: str, data: dict) -> None:
        """Mock storage write that accepts correct arguments (self, path, data)."""
        # Just return None - we don't need to actually write in tests
        return None

    # Patch the storage method to override pytest-homeassistant's broken mock
    with patch(
        "homeassistant.helpers.storage.Store._async_write_data",
        mock_async_write_data,
    ):
        yield


# ============================================================================
# Core Mock Fixtures (basic mocks for unit tests)
# ============================================================================


@pytest.fixture(name="mock_wiim_client")
def mock_wiim_client_fixture():
    """Mock WiiM API client with common methods."""
    client = MagicMock()
    client.get_status = AsyncMock(return_value=MOCK_STATUS_RESPONSE)
    client.get_device_info = AsyncMock(return_value=MOCK_DEVICE_DATA)
    client.get_player_status = AsyncMock(return_value=MOCK_STATUS_RESPONSE)
    client.get_multiroom_status = AsyncMock(return_value={})
    client.get_meta_info = AsyncMock(return_value={})
    client.get_eq_status = AsyncMock(return_value=False)
    client.get_eq = AsyncMock(return_value={})
    client.play = AsyncMock(return_value=True)
    client.pause = AsyncMock(return_value=True)
    client.stop = AsyncMock(return_value=True)
    client.set_volume = AsyncMock(return_value=True)
    client.mute = AsyncMock(return_value=True)
    client.unmute = AsyncMock(return_value=True)
    client.next_track = AsyncMock(return_value=True)
    client.previous_track = AsyncMock(return_value=True)
    client.seek = AsyncMock(return_value=True)
    client.select_preset = AsyncMock(return_value=True)
    client.join_group = AsyncMock(return_value=True)
    client.leave_group = AsyncMock(return_value=True)
    return client


@pytest.fixture(name="mock_coordinator")
def mock_coordinator_fixture():
    """Mock WiiM coordinator with standard data structure."""
    coordinator = MagicMock()
    # Create the proper data structure that matches what the real coordinator returns
    mock_status = MOCK_STATUS_RESPONSE.copy()
    mock_status["volume_level"] = 0.5  # Add parsed volume_level
    mock_status["volume"] = 50  # Add volume as integer

    coordinator.data = {
        "status": mock_status,
        "multiroom": {"slaves": 0},
        "role": "solo",
        "ha_group": {
            "is_leader": False,
            "members": [],
        },
    }
    coordinator.async_request_refresh = AsyncMock()
    coordinator.last_update_success = True
    # Add the client property
    coordinator.player = MagicMock()
    coordinator.player.host = "192.168.1.100"
    coordinator.player._host = "192.168.1.100"
    coordinator.ha_group_members = set()
    return coordinator


# ============================================================================
# Error Simulation Fixtures (for testing error handling and API bypass)
# ============================================================================


@pytest.fixture(name="bypass_get_data")
def bypass_get_data_fixture(hass):
    """Bypass API calls and return mock data - used for testing integration setup."""
    # Mock hass.http to prevent AttributeError when registering static paths
    from unittest.mock import AsyncMock, Mock

    hass.http = Mock()
    hass.http.async_register_static_paths = AsyncMock()

    # Create proper mock data with volume_level included and merge device data
    mock_status = MOCK_STATUS_RESPONSE.copy()
    mock_status["volume_level"] = 0.5  # Add parsed volume_level
    mock_status["volume"] = 50  # Add volume as integer

    # Merge device data into status so device info is available
    # Make sure project field is available for device model
    mock_status.update(MOCK_DEVICE_DATA)

    # Ensure critical fields are present for device registry
    mock_status["project"] = MOCK_DEVICE_DATA["project"]
    mock_status["hardware"] = MOCK_DEVICE_DATA["hardware"]
    mock_status["firmware"] = MOCK_DEVICE_DATA["firmware"]
    mock_status["uuid"] = MOCK_DEVICE_DATA["uuid"]
    mock_status["MAC"] = MOCK_DEVICE_DATA["MAC"]

    # Mock capabilities to avoid slow HTTP probing during setup
    # This prevents ~100+ HTTP requests per test (probing multiple ports/protocols)
    mock_capabilities = {
        "firmware_version": MOCK_DEVICE_DATA.get("firmware", "4.6.328252"),
        "device_type": MOCK_DEVICE_DATA.get("project", "UP2STREAM_MINI_V3"),
        "vendor": "wiim",
        "is_wiim_device": True,
        "is_legacy_device": False,
        "audio_pro_generation": "original",
        "supports_enhanced_grouping": False,
        "supports_audio_output": False,
        "supports_alarms": False,
        "supports_sleep_timer": False,
        "supports_firmware_install": True,
        "max_alarm_slots": 0,
        "response_timeout": 5.0,
        "retry_count": 3,
        "protocol_priority": ["https", "http"],
        "supports_led_control": False,
        "led_command_format": "wiim",
        "supports_getstatuse": True,
        "supports_getslavelist": True,
        "supports_metadata": True,
        "supports_presets": True,
        "supports_eq": False,
        "supports_player_status_ex": True,
    }

    # Create a factory function for mock Player that returns properly configured mock
    def create_mock_player(*args, **kwargs):
        mock_player = MagicMock()

        # Device identity properties - use actual strings, not MagicMock
        mock_player.name = MOCK_DEVICE_DATA.get("DeviceName", "WiiM Mini")
        mock_player.host = MOCK_DEVICE_DATA.get("ip", "192.168.1.100")
        mock_player.port = 80
        mock_player.model = "WiiM Speaker"
        mock_player.firmware = MOCK_DEVICE_DATA.get("firmware", "4.6.328252")
        mock_player.uuid = MOCK_DEVICE_DATA.get("uuid", "FF31F09E1A5020113B0A3918")
        mock_player.mac_address = MOCK_DEVICE_DATA.get("MAC", "00:22:6C:33:D4:AD")
        mock_player.discovered_endpoint = None
        mock_player.input_list = ["bluetooth", "line_in", "optical"]

        # Device info (Pydantic model) - mock with proper attributes
        mock_player.device_info = MagicMock()
        mock_player.device_info.mac = MOCK_DEVICE_DATA.get("MAC", "00:22:6C:33:D4:AD")
        mock_player.device_info.uuid = MOCK_DEVICE_DATA.get("uuid", "FF31F09E1A5020113B0A3918")
        mock_player.device_info.firmware = MOCK_DEVICE_DATA.get("firmware", "4.6.328252")
        mock_player.device_info.mcu_ver = "1.0.0"
        mock_player.device_info.dsp_ver = "1.0.0"
        mock_player.device_info.release_date = "2024-01-01"
        mock_player.device_info.version_update = "0"
        mock_player.device_info.latest_version = None
        mock_player.device_info.project = MOCK_DEVICE_DATA.get("project", "UP2STREAM_MINI_V3")
        mock_player.device_info.ssid = "TestNetwork"
        mock_player.device_info.ap_mac = "00:11:22:33:44:55"
        # Make model_dump return a dict with proper values
        mock_player.device_info.model_dump.return_value = {
            "mac": MOCK_DEVICE_DATA.get("MAC", "00:22:6C:33:D4:AD"),
            "uuid": MOCK_DEVICE_DATA.get("uuid", "FF31F09E1A5020113B0A3918"),
            "firmware": MOCK_DEVICE_DATA.get("firmware", "4.6.328252"),
            "project": MOCK_DEVICE_DATA.get("project", "UP2STREAM_MINI_V3"),
            "mcu_ver": "1.0.0",
            "dsp_ver": "1.0.0",
            "release_date": "2024-01-01",
            "ssid": "TestNetwork",
            "ap_mac": "00:11:22:33:44:55",
        }

        # Playback state properties
        mock_player.volume_level = 0.5
        mock_player.is_muted = False
        mock_player.play_state = "stop"
        mock_player.is_playing = False
        mock_player.source = "wifi"

        # Role and group properties
        mock_player.role = "solo"
        mock_player.is_solo = True
        mock_player.is_master = False
        mock_player.is_slave = False
        mock_player.group = None
        mock_player.group_master_name = None

        # Media properties - use None or actual strings, not MagicMock
        mock_player.media_title = None
        mock_player.media_artist = None
        mock_player.media_album = None
        mock_player.media_duration = None
        mock_player.media_position = None
        mock_player.media_position_updated_at = None
        mock_player.media_image_url = None  # Must be None or string, not MagicMock
        mock_player.media_content_id = None

        # Audio quality properties
        mock_player.media_sample_rate = 44100
        mock_player.media_bit_depth = 16
        mock_player.media_bit_rate = 320
        mock_player.media_codec = "mp3"

        # EQ properties
        mock_player.supports_eq = True
        mock_player.eq_preset = "Flat"
        mock_player.eq_presets = ["Flat", "Bass", "Treble", "Acoustic", "Rock"]

        # Shuffle/repeat properties
        mock_player.shuffle = False
        mock_player.repeat = "off"
        mock_player.shuffle_supported = True
        mock_player.repeat_supported = True

        # Transport support
        mock_player.supports_next_track = True
        mock_player.supports_previous_track = True

        # Available sources - use actual list, not MagicMock
        mock_player.available_sources = ["wifi", "bluetooth", "line_in", "optical"]

        # Audio output - use actual values, not MagicMock
        mock_player.audio_output_mode = "Line Out"
        mock_player.is_bluetooth_output_active = False
        mock_player.available_outputs = ["Line Out", "Optical Out"]
        mock_player.available_output_modes = ["Line Out", "Optical Out"]
        mock_player.bluetooth_output_devices = []

        # Network info
        mock_player.wifi_rssi = -50

        # Client properties
        mock_player.client = MagicMock()
        mock_player.client.discovered_endpoint = None
        mock_player.client.host = MOCK_DEVICE_DATA.get("ip", "192.168.1.100")
        mock_player.client.close = AsyncMock()
        mock_player.client.sync_time = AsyncMock()
        mock_player.client.reboot = AsyncMock()

        # Methods
        mock_player.refresh = AsyncMock()
        mock_player.reboot = AsyncMock()
        mock_player.sync_time = AsyncMock()  # Time sync method
        mock_player.play = AsyncMock()
        mock_player.pause = AsyncMock()
        mock_player.stop = AsyncMock()
        mock_player.set_volume = AsyncMock()
        mock_player.set_mute = AsyncMock()
        mock_player.set_source = AsyncMock()
        mock_player.next_track = AsyncMock()
        mock_player.previous_track = AsyncMock()
        mock_player.seek = AsyncMock()
        mock_player.set_eq_preset = AsyncMock()
        mock_player.set_shuffle = AsyncMock()
        mock_player.get_eq = AsyncMock(return_value={})
        mock_player.get_eq_presets = AsyncMock(return_value=["Flat", "Bass", "Treble"])
        mock_player.get_eq_status = AsyncMock(return_value=True)

        return mock_player

    with (
        # Patch at pywiim level to catch all instances, regardless of import path
        # This MUST be first to prevent HTTP requests during capability detection
        # Patch both the class method and the instance method to be comprehensive
        patch(
            "pywiim.WiiMClient._detect_capabilities",
            new_callable=AsyncMock,
            return_value=mock_capabilities,
        ),
        # Also patch where it's imported in the integration module
        patch(
            "custom_components.wiim.__init__.WiiMClient._detect_capabilities",
            new_callable=AsyncMock,
            return_value=mock_capabilities,
        ),
        patch(
            "pywiim.WiiMClient.get_player_status",
            return_value=mock_status,  # Use merged status instead of original
        ),
        patch(
            "pywiim.WiiMClient.get_device_info",
            return_value=MOCK_DEVICE_DATA,
        ),
        patch(
            "pywiim.WiiMClient.get_multiroom_status",
            return_value={"slaves": 0},
        ),
        patch(
            "pywiim.WiiMClient.reboot",
            return_value=True,
        ),
        patch(
            "pywiim.WiiMClient.sync_time",
            return_value=True,
        ),
        # Patch Player class to return our mock with correct properties
        patch(
            "pywiim.Player",
            side_effect=create_mock_player,
        ),
        # Also patch where Player is imported in coordinator
        patch(
            "custom_components.wiim.coordinator.Player",
            side_effect=create_mock_player,
        ),
    ):
        yield


@pytest.fixture(name="error_on_get_data")
def error_get_data_fixture():
    """Simulate API errors - useful for testing error handling."""
    with (
        patch(
            "pywiim.WiiMClient.get_player_status",
            side_effect=Exception,
        ),
        patch(
            "pywiim.WiiMClient.get_device_info",
            side_effect=Exception,
        ),
    ):
        yield


# ============================================================================
# WiiM-Specific Fixtures (higher-level fixtures for specific test scenarios)
# ============================================================================


@pytest.fixture
def wiim_config_entry():
    """Create a WiiM config entry for testing."""
    entry = MagicMock(spec=ConfigEntry)
    entry.domain = "wiim"
    entry.entry_id = "test_wiim_entry"
    entry.unique_id = "test-speaker-uuid"
    entry.data = {"host": "192.168.1.100", "name": "Test WiiM"}
    entry.options = {}
    entry.title = "Test WiiM"
    return entry


@pytest.fixture
def wiim_client():
    """Create a mock WiiM client with realistic responses."""
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
    """Create a mock WiiM coordinator with full player object."""
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
    mock_player.media_content_id = None  # URL if playing URL-based media
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
    coordinator.player = mock_player  # Remove dead code assignment
    coordinator.data = {"player": mock_player}
    coordinator.last_update_success = True
    coordinator.async_request_refresh = AsyncMock()
    coordinator.record_user_command = MagicMock()
    return coordinator


@pytest.fixture
def wiim_coordinator_slave(hass):
    """Create a test slave coordinator for group testing."""
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
    slave_coordinator.player = slave_player
    slave_coordinator.data = {"player": slave_player}
    slave_coordinator.last_update_success = True
    slave_coordinator.async_request_refresh = AsyncMock()

    # Create a mock config entry for slave
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.entry_id = "test_slave_entry"
    config_entry.unique_id = "test-slave-uuid"
    config_entry.data = {"host": "192.168.1.101"}
    config_entry.options = {}
    config_entry.title = "Test Slave"

    # Register slave coordinator in hass.data for helper lookups
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "coordinator": slave_coordinator,
        "entry": config_entry,
    }

    return slave_coordinator


# ============================================================================
# Helper Fixtures (for specific testing scenarios)
# ============================================================================


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
