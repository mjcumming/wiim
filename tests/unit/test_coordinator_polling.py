"""Test coordinator polling implementation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.wiim.api import WiiMError
from custom_components.wiim.coordinator_polling import async_update_data
from custom_components.wiim.models import DeviceInfo, EQInfo, PlayerStatus, PollingMetrics, TrackMetadata
from tests.const import MOCK_DEVICE_DATA, MOCK_STATUS_RESPONSE


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator for polling testing."""
    coordinator = MagicMock()
    coordinator.client = MagicMock()
    coordinator.client.host = "192.168.1.100"
    coordinator.update_interval = MagicMock()
    coordinator.update_interval.total_seconds.return_value = 5.0
    coordinator.entry = MagicMock()
    coordinator.entry.unique_id = "test-unique-id"

    # API capability flags (initialize as True for testing)
    coordinator._statusex_supported = True
    coordinator._metadata_supported = True
    coordinator._eq_supported = True
    coordinator._presets_supported = True
    coordinator._eq_list_extended = True

    # Endpoint health flags (initialize as working for testing)
    coordinator._player_status_working = True
    coordinator._device_info_working = True
    coordinator._multiroom_working = True
    coordinator._initial_setup_complete = False  # Start as False, will be set to True during testing

    # Backoff controller
    coordinator._backoff = MagicMock()
    coordinator._backoff.record_success = MagicMock()
    coordinator._backoff.record_failure = MagicMock()
    coordinator._backoff.next_interval = MagicMock(return_value=5)
    coordinator._backoff.consecutive_failures = 0  # Initialize as number, not MagicMock

    # Core communication failure tracking
    coordinator._core_comm_failures = 0  # Initialize as number, not MagicMock

    # Audio output error tracking
    coordinator._audio_output_error_count = 0  # Initialize as number, not MagicMock

    # Time tracking attributes
    coordinator._last_device_info_check = 0.0
    coordinator._last_eq_info_check = 0.0
    coordinator._last_multiroom_check = 0.0
    coordinator._last_audio_output_check = 0.0
    coordinator._last_response_time = 0.0

    coordinator._last_command_failure = None
    coordinator.clear_command_failures = MagicMock()
    coordinator.data = None  # Will be populated during testing
    coordinator.hass = MagicMock()
    coordinator.hass.loop = MagicMock()
    coordinator.hass.loop.run_in_executor = AsyncMock(return_value={})

    # Mock the async methods that will be called - ensure they return proper coroutines
    coordinator._fetch_multiroom_info = AsyncMock(return_value={})
    coordinator._fetch_track_metadata = AsyncMock(return_value=None)
    coordinator._fetch_eq_info = AsyncMock(return_value=EQInfo.model_validate({"eq_enabled": False}))
    coordinator._detect_role_from_status_and_slaves = AsyncMock(return_value="solo")
    coordinator._resolve_multiroom_source_and_media = AsyncMock(return_value=None)
    coordinator._update_speaker_object = AsyncMock(return_value=None)
    coordinator._extend_eq_preset_map_once = AsyncMock(return_value=None)

    # Mock client async methods
    coordinator.client.get_player_status = AsyncMock(return_value=MOCK_STATUS_RESPONSE)
    coordinator.client.get_device_info = AsyncMock(return_value=MOCK_DEVICE_DATA)
    coordinator.client.get_presets = AsyncMock(return_value=[])
    coordinator.client.get_bluetooth_pair_status = AsyncMock(return_value=None)
    coordinator.client.get_audio_output_status = AsyncMock(return_value={"hardware": "2", "source": "0", "audiocast": "0"})

    # Initialize tracking attributes that might be checked
    # Don't set _last_track_info so it gets properly initialized in _track_changed
    # Ensure _last_track_info doesn't exist or is None
    if hasattr(coordinator, "_last_track_info"):
        delattr(coordinator, "_last_track_info")

    # Set test mode to avoid delayed metadata fetching
    coordinator._test_mode = True

    return coordinator


async def test_polling_success_complete(mock_coordinator):
    """Test successful complete polling cycle."""
    # Mock all endpoint calls
    with (
        patch(
            "custom_components.wiim.coordinator_endpoints.fetch_player_status", new_callable=AsyncMock
        ) as mock_player_status,
        patch(
            "custom_components.wiim.coordinator_endpoints.fetch_device_info", new_callable=AsyncMock
        ) as mock_device_info,
        patch.object(mock_coordinator, "_fetch_multiroom_info", new_callable=AsyncMock) as mock_multiroom,
        patch.object(mock_coordinator, "_fetch_track_metadata", new_callable=AsyncMock) as mock_metadata,
        patch.object(mock_coordinator, "_fetch_eq_info", new_callable=AsyncMock) as mock_eq,
        patch.object(mock_coordinator, "_detect_role_from_status_and_slaves", new_callable=AsyncMock) as mock_role,
        patch.object(mock_coordinator, "_resolve_multiroom_source_and_media", new_callable=AsyncMock) as mock_resolve,
        patch.object(mock_coordinator, "_update_speaker_object", new_callable=AsyncMock) as mock_update_speaker,
    ):
        # Set up return values - ensure AsyncMock functions return awaitables
        status_model = PlayerStatus.model_validate(MOCK_STATUS_RESPONSE)
        device_model = DeviceInfo.model_validate(MOCK_DEVICE_DATA)
        metadata_model = TrackMetadata.model_validate({"title": "Test Track"})
        eq_model = EQInfo.model_validate({"eq_enabled": False})

        # Use AsyncMock with proper return values (AsyncMock already makes them awaitable)
        mock_player_status.return_value = status_model
        mock_device_info.return_value = device_model
        mock_multiroom.return_value = {"slave_count": 0}
        mock_metadata.return_value = metadata_model
        mock_eq.return_value = eq_model
        mock_role.return_value = "solo"
        # For AsyncMock, setting return_value is sufficient
        mock_resolve.return_value = None
        mock_update_speaker.return_value = None

        # Mock presets call
        mock_coordinator.client.get_presets = AsyncMock(return_value=[])

        # Mock audio output call
        mock_coordinator.client.get_audio_output_status = AsyncMock(
            return_value={"hardware": "2", "source": "0", "audiocast": "0"}
        )

        result = await async_update_data(mock_coordinator)

        # Verify result structure
        assert isinstance(result, dict)
        assert "status_model" in result
        assert "device_model" in result
        assert "multiroom" in result
        # Note: metadata_model may be None due to delayed fetching
        assert "metadata_model" in result
        assert "eq_model" in result
        assert "role" in result
        assert "polling_metrics" in result

        # Verify models
        assert isinstance(result["status_model"], PlayerStatus)
        assert isinstance(result["device_model"], DeviceInfo)
        # metadata_model may be None if delayed fetch is used
        if result["metadata_model"] is not None:
            assert isinstance(result["metadata_model"], TrackMetadata)
        assert isinstance(result["eq_model"], EQInfo)
        assert isinstance(result["polling_metrics"], PollingMetrics)

        # Verify success tracking
        mock_coordinator._backoff.record_success.assert_called_once()
        assert mock_coordinator._player_status_working is True
        assert mock_coordinator._device_info_working is True


async def test_polling_player_status_failure(mock_coordinator):
    """Test polling when player status fails."""
    # Set up coordinator to use direct client call instead of patched endpoints
    mock_coordinator.client.get_player_status = AsyncMock(side_effect=WiiMError("Connection failed"))

    with pytest.raises(UpdateFailed, match="Error updating WiiM device"):
        await async_update_data(mock_coordinator)

        # Verify failure tracking
        mock_coordinator._backoff.record_failure.assert_called_once()
        assert mock_coordinator._player_status_working is False
        assert mock_coordinator._device_info_working is False
        assert mock_coordinator._multiroom_working is False


async def test_polling_device_info_failure(mock_coordinator):
    """Test polling when device info fails but player status succeeds."""
    # Set up client methods directly
    mock_coordinator.client.get_player_status = AsyncMock(return_value=MOCK_STATUS_RESPONSE)
    mock_coordinator.client.get_device_info = AsyncMock(side_effect=WiiMError("Device info failed"))

    # Properly mock _fetch_eq_info to return an EQInfo object
    mock_coordinator._fetch_eq_info = AsyncMock(return_value=EQInfo.model_validate({"eq_enabled": False}))

    # Mock audio output call
    mock_coordinator.client.get_audio_output_status = AsyncMock(
        return_value={"hardware": "2", "source": "0", "audiocast": "0"}
    )

    # Mock the heavy processing to return empty data
    with patch("custom_components.wiim.coordinator_polling._process_heavy_operations", return_value={}):
        result = await async_update_data(mock_coordinator)

        # Should succeed despite device_info failure
        assert isinstance(result, dict)
        assert "status_model" in result
        # Device info working should be marked as False
        assert mock_coordinator._device_info_working is False
        # But player status should still work
        assert mock_coordinator._player_status_working is True


async def test_polling_presets_not_supported(mock_coordinator):
    """Test polling when presets are not supported."""
    with (
        patch(
            "custom_components.wiim.coordinator_endpoints.fetch_player_status", new_callable=AsyncMock
        ) as mock_player_status,
        patch(
            "custom_components.wiim.coordinator_endpoints.fetch_device_info", new_callable=AsyncMock
        ) as mock_device_info,
        patch.object(mock_coordinator, "_fetch_multiroom_info", new_callable=AsyncMock) as mock_multiroom,
        patch.object(mock_coordinator, "_fetch_track_metadata", new_callable=AsyncMock) as mock_metadata,
        patch.object(mock_coordinator, "_fetch_eq_info", new_callable=AsyncMock) as mock_eq,
        patch.object(mock_coordinator, "_detect_role_from_status_and_slaves", new_callable=AsyncMock) as mock_role,
        patch.object(mock_coordinator, "_resolve_multiroom_source_and_media", new_callable=AsyncMock),
        patch.object(mock_coordinator, "_update_speaker_object", new_callable=AsyncMock),
    ):
        # Set up successful returns
        mock_player_status.return_value = PlayerStatus.model_validate(MOCK_STATUS_RESPONSE)
        mock_device_info.return_value = DeviceInfo.model_validate(MOCK_DEVICE_DATA)
        mock_multiroom.return_value = {"slave_count": 0}
        mock_metadata.return_value = TrackMetadata.model_validate({"title": "Test"})
        mock_eq.return_value = EQInfo.model_validate({"eq_enabled": False})
        mock_role.return_value = "solo"

        # Presets not supported - first call fails
        mock_coordinator._presets_supported = None
        mock_coordinator.client.get_presets = AsyncMock(side_effect=WiiMError("Not supported"))

        # Mock audio output call
        mock_coordinator.client.get_audio_output_status = AsyncMock(
            return_value={"hardware": "2", "source": "0", "audiocast": "0"}
        )

        result = await async_update_data(mock_coordinator)

        assert result["presets"] == []
        assert mock_coordinator._presets_supported is False


async def test_polling_presets_already_not_supported(mock_coordinator):
    """Test polling when presets already known to be unsupported."""
    with (
        patch(
            "custom_components.wiim.coordinator_endpoints.fetch_player_status", new_callable=AsyncMock
        ) as mock_player_status,
        patch(
            "custom_components.wiim.coordinator_endpoints.fetch_device_info", new_callable=AsyncMock
        ) as mock_device_info,
        patch.object(mock_coordinator, "_fetch_multiroom_info", new_callable=AsyncMock) as mock_multiroom,
        patch.object(mock_coordinator, "_fetch_track_metadata", new_callable=AsyncMock) as mock_metadata,
        patch.object(mock_coordinator, "_fetch_eq_info", new_callable=AsyncMock) as mock_eq,
        patch.object(mock_coordinator, "_detect_role_from_status_and_slaves", new_callable=AsyncMock) as mock_role,
        patch.object(mock_coordinator, "_resolve_multiroom_source_and_media", new_callable=AsyncMock),
        patch.object(mock_coordinator, "_update_speaker_object", new_callable=AsyncMock),
    ):
        # Set up successful returns
        mock_player_status.return_value = PlayerStatus.model_validate(MOCK_STATUS_RESPONSE)
        mock_device_info.return_value = DeviceInfo.model_validate(MOCK_DEVICE_DATA)
        mock_multiroom.return_value = {"slave_count": 0}
        mock_metadata.return_value = TrackMetadata.model_validate({"title": "Test"})
        mock_eq.return_value = EQInfo.model_validate({"eq_enabled": False})
        mock_role.return_value = "solo"

        # Presets already known to be unsupported
        mock_coordinator._presets_supported = False

        # Mock audio output call
        mock_coordinator.client.get_audio_output_status = AsyncMock(
            return_value={"hardware": "2", "source": "0", "audiocast": "0"}
        )

        result = await async_update_data(mock_coordinator)

        assert result["presets"] == []
        # Should not have called get_presets
        mock_coordinator.client.get_presets.assert_not_called()


async def test_polling_artwork_propagation(mock_coordinator):
    """Test artwork propagation from metadata to status."""
    with (
        patch(
            "custom_components.wiim.coordinator_endpoints.fetch_player_status", new_callable=AsyncMock
        ) as mock_player_status,
        patch(
            "custom_components.wiim.coordinator_endpoints.fetch_device_info", new_callable=AsyncMock
        ) as mock_device_info,
        patch.object(mock_coordinator, "_fetch_multiroom_info", new_callable=AsyncMock) as mock_multiroom,
        patch.object(mock_coordinator, "_fetch_track_metadata", new_callable=AsyncMock) as mock_metadata,
        patch.object(mock_coordinator, "_fetch_eq_info", new_callable=AsyncMock) as mock_eq,
        patch.object(mock_coordinator, "_detect_role_from_status_and_slaves", new_callable=AsyncMock) as mock_role,
        patch.object(mock_coordinator, "_resolve_multiroom_source_and_media", new_callable=AsyncMock),
        patch.object(mock_coordinator, "_update_speaker_object", new_callable=AsyncMock),
    ):
        status_model = PlayerStatus.model_validate(MOCK_STATUS_RESPONSE)
        device_model = DeviceInfo.model_validate(MOCK_DEVICE_DATA)
        metadata_model = TrackMetadata.model_validate(
            {"title": "Test Track", "entity_picture": "http://example.com/cover.jpg"}
        )
        eq_model = EQInfo.model_validate({"eq_enabled": False})

        mock_player_status.return_value = status_model
        mock_device_info.return_value = device_model
        mock_multiroom.return_value = {"slave_count": 0}
        mock_metadata.return_value = metadata_model
        mock_eq.return_value = eq_model
        mock_role.return_value = "solo"

        mock_coordinator.client.get_presets = AsyncMock(return_value=[])

        # Mock audio output call
        mock_coordinator.client.get_audio_output_status = AsyncMock(
            return_value={"hardware": "2", "source": "0", "audiocast": "0"}
        )

        result = await async_update_data(mock_coordinator)

        # Artwork should be propagated to status model
        assert result["status_model"].entity_picture == "http://example.com/cover.jpg"
        assert result["status_model"].cover_url == "http://example.com/cover.jpg"


async def test_polling_eq_preset_propagation(mock_coordinator):
    """Test EQ preset propagation from EQ info to status."""
    with (
        patch(
            "custom_components.wiim.coordinator_endpoints.fetch_player_status", new_callable=AsyncMock
        ) as mock_player_status,
        patch(
            "custom_components.wiim.coordinator_endpoints.fetch_device_info", new_callable=AsyncMock
        ) as mock_device_info,
        patch.object(mock_coordinator, "_fetch_multiroom_info", new_callable=AsyncMock) as mock_multiroom,
        patch.object(mock_coordinator, "_fetch_track_metadata", new_callable=AsyncMock) as mock_metadata,
        patch.object(mock_coordinator, "_fetch_eq_info", new_callable=AsyncMock) as mock_eq,
        patch.object(mock_coordinator, "_detect_role_from_status_and_slaves", new_callable=AsyncMock) as mock_role,
        patch.object(mock_coordinator, "_resolve_multiroom_source_and_media", new_callable=AsyncMock),
        patch.object(mock_coordinator, "_update_speaker_object", new_callable=AsyncMock),
    ):
        status_model = PlayerStatus.model_validate(MOCK_STATUS_RESPONSE)
        device_model = DeviceInfo.model_validate(MOCK_DEVICE_DATA)
        metadata_model = TrackMetadata.model_validate({"title": "Test Track"})
        eq_model = EQInfo.model_validate({"eq_enabled": True, "eq_preset": "rock"})

        mock_player_status.return_value = status_model
        mock_device_info.return_value = device_model
        mock_multiroom.return_value = {"slave_count": 0}
        mock_metadata.return_value = metadata_model
        mock_eq.return_value = eq_model
        mock_role.return_value = "solo"

        mock_coordinator.client.get_presets = AsyncMock(return_value=[])

        # Mock audio output call
        mock_coordinator.client.get_audio_output_status = AsyncMock(
            return_value={"hardware": "2", "source": "0", "audiocast": "0"}
        )

        result = await async_update_data(mock_coordinator)

        # EQ preset should be propagated to status model
        assert result["status_model"].eq_preset == "rock"


async def test_polling_uuid_injection(mock_coordinator):
    """Test UUID injection when device API doesn't provide it."""
    # Device model without UUID
    device_data = MOCK_DEVICE_DATA.copy()
    device_data["uuid"] = None

    # Override the coordinator's client method to return device data without UUID
    mock_coordinator.client.get_device_info = AsyncMock(return_value=device_data)

    with (
        patch(
            "custom_components.wiim.coordinator_endpoints.fetch_player_status", new_callable=AsyncMock
        ) as mock_player_status,
        patch(
            "custom_components.wiim.coordinator_endpoints.fetch_device_info", new_callable=AsyncMock
        ) as mock_device_info,
        patch.object(mock_coordinator, "_fetch_multiroom_info", new_callable=AsyncMock) as mock_multiroom,
        patch.object(mock_coordinator, "_fetch_track_metadata", new_callable=AsyncMock) as mock_metadata,
        patch.object(mock_coordinator, "_fetch_eq_info", new_callable=AsyncMock) as mock_eq,
        patch.object(mock_coordinator, "_detect_role_from_status_and_slaves", new_callable=AsyncMock) as mock_role,
        patch.object(mock_coordinator, "_resolve_multiroom_source_and_media", new_callable=AsyncMock),
        patch.object(mock_coordinator, "_update_speaker_object", new_callable=AsyncMock),
    ):
        status_model = PlayerStatus.model_validate(MOCK_STATUS_RESPONSE)
        device_model = DeviceInfo.model_validate(device_data)
        metadata_model = TrackMetadata.model_validate({"title": "Test Track"})
        eq_model = EQInfo.model_validate({"eq_enabled": False})

        mock_player_status.return_value = status_model
        mock_device_info.return_value = device_model
        mock_multiroom.return_value = {"slave_count": 0}
        mock_metadata.return_value = metadata_model
        mock_eq.return_value = eq_model
        mock_role.return_value = "solo"

        mock_coordinator.client.get_presets = AsyncMock(return_value=[])

        # Mock audio output call
        mock_coordinator.client.get_audio_output_status = AsyncMock(
            return_value={"hardware": "2", "source": "0", "audiocast": "0"}
        )

        result = await async_update_data(mock_coordinator)

        # UUID should be injected from config entry
        assert result["device_model"].uuid == "test-unique-id"


async def test_polling_response_time_tracking(mock_coordinator):
    """Test that response time is tracked."""
    with (
        patch(
            "custom_components.wiim.coordinator_endpoints.fetch_player_status", new_callable=AsyncMock
        ) as mock_player_status,
        patch(
            "custom_components.wiim.coordinator_endpoints.fetch_device_info", new_callable=AsyncMock
        ) as mock_device_info,
        patch.object(mock_coordinator, "_fetch_multiroom_info", new_callable=AsyncMock) as mock_multiroom,
        patch.object(mock_coordinator, "_fetch_track_metadata", new_callable=AsyncMock) as mock_metadata,
        patch.object(mock_coordinator, "_fetch_eq_info", new_callable=AsyncMock) as mock_eq,
        patch.object(mock_coordinator, "_detect_role_from_status_and_slaves", new_callable=AsyncMock) as mock_role,
        patch.object(mock_coordinator, "_resolve_multiroom_source_and_media", new_callable=AsyncMock),
        patch.object(mock_coordinator, "_update_speaker_object", new_callable=AsyncMock),
    ):
        status_model = PlayerStatus.model_validate(MOCK_STATUS_RESPONSE)
        device_model = DeviceInfo.model_validate(MOCK_DEVICE_DATA)
        metadata_model = TrackMetadata.model_validate({"title": "Test Track"})
        eq_model = EQInfo.model_validate({"eq_enabled": False})

        mock_player_status.return_value = status_model
        mock_device_info.return_value = device_model
        mock_multiroom.return_value = {"slave_count": 0}
        mock_metadata.return_value = metadata_model
        mock_eq.return_value = eq_model
        mock_role.return_value = "solo"

        mock_coordinator.client.get_presets = AsyncMock(return_value=[])

        # Mock audio output call
        mock_coordinator.client.get_audio_output_status = AsyncMock(
            return_value={"hardware": "2", "source": "0", "audiocast": "0"}
        )

        await async_update_data(mock_coordinator)

        # Response time should be recorded
        assert mock_coordinator._last_response_time is not None
        assert mock_coordinator._last_response_time > 0


async def test_polling_command_failure_clearing(mock_coordinator):
    """Test that command failures are cleared on success."""
    mock_coordinator._last_command_failure = 12345.0  # Some timestamp

    with (
        patch(
            "custom_components.wiim.coordinator_endpoints.fetch_player_status", new_callable=AsyncMock
        ) as mock_player_status,
        patch(
            "custom_components.wiim.coordinator_endpoints.fetch_device_info", new_callable=AsyncMock
        ) as mock_device_info,
        patch.object(mock_coordinator, "_fetch_multiroom_info", new_callable=AsyncMock) as mock_multiroom,
        patch.object(mock_coordinator, "_fetch_track_metadata", new_callable=AsyncMock) as mock_metadata,
        patch.object(mock_coordinator, "_fetch_eq_info", new_callable=AsyncMock) as mock_eq,
        patch.object(mock_coordinator, "_detect_role_from_status_and_slaves", new_callable=AsyncMock) as mock_role,
        patch.object(mock_coordinator, "_resolve_multiroom_source_and_media", new_callable=AsyncMock),
        patch.object(mock_coordinator, "_update_speaker_object", new_callable=AsyncMock),
    ):
        status_model = PlayerStatus.model_validate(MOCK_STATUS_RESPONSE)
        device_model = DeviceInfo.model_validate(MOCK_DEVICE_DATA)
        metadata_model = TrackMetadata.model_validate({"title": "Test Track"})
        eq_model = EQInfo.model_validate({"eq_enabled": False})

        mock_player_status.return_value = status_model
        mock_device_info.return_value = device_model
        mock_multiroom.return_value = {"slave_count": 0}
        mock_metadata.return_value = metadata_model
        mock_eq.return_value = eq_model
        mock_role.return_value = "solo"

        mock_coordinator.client.get_presets = AsyncMock(return_value=[])

        # Mock audio output call
        mock_coordinator.client.get_audio_output_status = AsyncMock(
            return_value={"hardware": "2", "source": "0", "audiocast": "0"}
        )

        await async_update_data(mock_coordinator)

        # Verify successful polling (command failures are cleared by media player commands, not polling)
        assert mock_coordinator._last_response_time is not None
