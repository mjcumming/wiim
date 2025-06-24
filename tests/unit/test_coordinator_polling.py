"""Test coordinator polling implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.wiim.coordinator_polling import async_update_data
from custom_components.wiim.models import PlayerStatus, DeviceInfo, TrackMetadata, EQInfo, PollingMetrics
from custom_components.wiim.api import WiiMError
from tests.const import MOCK_STATUS_RESPONSE, MOCK_DEVICE_DATA


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

    # API capability flags
    coordinator._statusex_supported = None
    coordinator._metadata_supported = None
    coordinator._eq_supported = None
    coordinator._presets_supported = None
    coordinator._eq_list_extended = True

    # Endpoint health flags
    coordinator._player_status_working = None
    coordinator._device_info_working = None
    coordinator._multiroom_working = None

    # Backoff controller
    coordinator._backoff = MagicMock()
    coordinator._backoff.record_success = MagicMock()
    coordinator._backoff.record_failure = MagicMock()
    coordinator._backoff.next_interval = MagicMock()

    coordinator._last_command_failure = None
    coordinator.clear_command_failures = MagicMock()
    coordinator._last_response_time = None

    return coordinator


async def test_polling_success_complete(mock_coordinator):
    """Test successful complete polling cycle."""
    # Mock all endpoint calls
    with (
        patch("custom_components.wiim.coordinator_polling._endpoints.fetch_player_status") as mock_player_status,
        patch("custom_components.wiim.coordinator_polling._endpoints.fetch_device_info") as mock_device_info,
        patch.object(mock_coordinator, "_get_multiroom_info_defensive") as mock_multiroom,
        patch.object(mock_coordinator, "_get_track_metadata_defensive") as mock_metadata,
        patch.object(mock_coordinator, "_get_eq_info_defensive") as mock_eq,
        patch.object(mock_coordinator, "_detect_role_from_status_and_slaves") as mock_role,
        patch.object(mock_coordinator, "_resolve_multiroom_source_and_media") as mock_resolve,
        patch.object(mock_coordinator, "_update_speaker_object") as mock_update_speaker,
    ):
        # Set up return values
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
        mock_resolve.return_value = None
        mock_update_speaker.return_value = None

        # Mock presets call
        mock_coordinator.client.get_presets = AsyncMock(return_value=[])

        result = await async_update_data(mock_coordinator)

        # Verify result structure
        assert isinstance(result, dict)
        assert "status_model" in result
        assert "device_model" in result
        assert "multiroom" in result
        assert "metadata_model" in result
        assert "eq_model" in result
        assert "role" in result
        assert "polling_metrics" in result

        # Verify models
        assert isinstance(result["status_model"], PlayerStatus)
        assert isinstance(result["device_model"], DeviceInfo)
        assert isinstance(result["metadata_model"], TrackMetadata)
        assert isinstance(result["eq_model"], EQInfo)
        assert isinstance(result["polling_metrics"], PollingMetrics)

        # Verify success tracking
        mock_coordinator._backoff.record_success.assert_called_once()
        assert mock_coordinator._player_status_working is True
        assert mock_coordinator._device_info_working is True


async def test_polling_player_status_failure(mock_coordinator):
    """Test polling when player status fails."""
    with patch("custom_components.wiim.coordinator_polling._endpoints.fetch_player_status") as mock_player_status:
        mock_player_status.side_effect = WiiMError("Connection failed")

        with pytest.raises(UpdateFailed, match="Error updating WiiM device"):
            await async_update_data(mock_coordinator)

        # Verify failure tracking
        mock_coordinator._backoff.record_failure.assert_called_once()
        assert mock_coordinator._player_status_working is False
        assert mock_coordinator._device_info_working is False
        assert mock_coordinator._multiroom_working is False


async def test_polling_device_info_failure(mock_coordinator):
    """Test polling when device info fails but player status succeeds."""
    with (
        patch("custom_components.wiim.coordinator_polling._endpoints.fetch_player_status") as mock_player_status,
        patch("custom_components.wiim.coordinator_polling._endpoints.fetch_device_info") as mock_device_info,
    ):
        mock_player_status.return_value = PlayerStatus.model_validate(MOCK_STATUS_RESPONSE)
        mock_device_info.side_effect = WiiMError("Device info failed")

        with pytest.raises(UpdateFailed):
            await async_update_data(mock_coordinator)


async def test_polling_presets_not_supported(mock_coordinator):
    """Test polling when presets are not supported."""
    with (
        patch("custom_components.wiim.coordinator_polling._endpoints.fetch_player_status") as mock_player_status,
        patch("custom_components.wiim.coordinator_polling._endpoints.fetch_device_info") as mock_device_info,
        patch.object(mock_coordinator, "_get_multiroom_info_defensive") as mock_multiroom,
        patch.object(mock_coordinator, "_get_track_metadata_defensive") as mock_metadata,
        patch.object(mock_coordinator, "_get_eq_info_defensive") as mock_eq,
        patch.object(mock_coordinator, "_detect_role_from_status_and_slaves") as mock_role,
        patch.object(mock_coordinator, "_resolve_multiroom_source_and_media") as mock_resolve,
        patch.object(mock_coordinator, "_update_speaker_object") as mock_update_speaker,
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

        result = await async_update_data(mock_coordinator)

        assert result["presets"] == []
        assert mock_coordinator._presets_supported is False


async def test_polling_presets_already_not_supported(mock_coordinator):
    """Test polling when presets already known to be unsupported."""
    with (
        patch("custom_components.wiim.coordinator_polling._endpoints.fetch_player_status") as mock_player_status,
        patch("custom_components.wiim.coordinator_polling._endpoints.fetch_device_info") as mock_device_info,
        patch.object(mock_coordinator, "_get_multiroom_info_defensive") as mock_multiroom,
        patch.object(mock_coordinator, "_get_track_metadata_defensive") as mock_metadata,
        patch.object(mock_coordinator, "_get_eq_info_defensive") as mock_eq,
        patch.object(mock_coordinator, "_detect_role_from_status_and_slaves") as mock_role,
        patch.object(mock_coordinator, "_resolve_multiroom_source_and_media") as mock_resolve,
        patch.object(mock_coordinator, "_update_speaker_object") as mock_update_speaker,
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

        result = await async_update_data(mock_coordinator)

        assert result["presets"] == []
        # Should not have called get_presets
        mock_coordinator.client.get_presets.assert_not_called()


async def test_polling_artwork_propagation(mock_coordinator):
    """Test artwork propagation from metadata to status."""
    with (
        patch("custom_components.wiim.coordinator_polling._endpoints.fetch_player_status") as mock_player_status,
        patch("custom_components.wiim.coordinator_polling._endpoints.fetch_device_info") as mock_device_info,
        patch.object(mock_coordinator, "_get_multiroom_info_defensive") as mock_multiroom,
        patch.object(mock_coordinator, "_get_track_metadata_defensive") as mock_metadata,
        patch.object(mock_coordinator, "_get_eq_info_defensive") as mock_eq,
        patch.object(mock_coordinator, "_detect_role_from_status_and_slaves") as mock_role,
        patch.object(mock_coordinator, "_resolve_multiroom_source_and_media") as mock_resolve,
        patch.object(mock_coordinator, "_update_speaker_object") as mock_update_speaker,
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

        result = await async_update_data(mock_coordinator)

        # Artwork should be propagated to status model
        assert result["status_model"].entity_picture == "http://example.com/cover.jpg"
        assert result["status_model"].cover_url == "http://example.com/cover.jpg"


async def test_polling_eq_preset_propagation(mock_coordinator):
    """Test EQ preset propagation from EQ info to status."""
    with (
        patch("custom_components.wiim.coordinator_polling._endpoints.fetch_player_status") as mock_player_status,
        patch("custom_components.wiim.coordinator_polling._endpoints.fetch_device_info") as mock_device_info,
        patch.object(mock_coordinator, "_get_multiroom_info_defensive") as mock_multiroom,
        patch.object(mock_coordinator, "_get_track_metadata_defensive") as mock_metadata,
        patch.object(mock_coordinator, "_get_eq_info_defensive") as mock_eq,
        patch.object(mock_coordinator, "_detect_role_from_status_and_slaves") as mock_role,
        patch.object(mock_coordinator, "_resolve_multiroom_source_and_media") as mock_resolve,
        patch.object(mock_coordinator, "_update_speaker_object") as mock_update_speaker,
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

        result = await async_update_data(mock_coordinator)

        # EQ preset should be propagated to status model
        assert result["status_model"].eq_preset == "rock"


async def test_polling_uuid_injection(mock_coordinator):
    """Test UUID injection when device API doesn't provide it."""
    with (
        patch("custom_components.wiim.coordinator_polling._endpoints.fetch_player_status") as mock_player_status,
        patch("custom_components.wiim.coordinator_polling._endpoints.fetch_device_info") as mock_device_info,
        patch.object(mock_coordinator, "_get_multiroom_info_defensive") as mock_multiroom,
        patch.object(mock_coordinator, "_get_track_metadata_defensive") as mock_metadata,
        patch.object(mock_coordinator, "_get_eq_info_defensive") as mock_eq,
        patch.object(mock_coordinator, "_detect_role_from_status_and_slaves") as mock_role,
        patch.object(mock_coordinator, "_resolve_multiroom_source_and_media") as mock_resolve,
        patch.object(mock_coordinator, "_update_speaker_object") as mock_update_speaker,
    ):
        # Device model without UUID
        device_data = MOCK_DEVICE_DATA.copy()
        device_data["uuid"] = None

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

        result = await async_update_data(mock_coordinator)

        # UUID should be injected from config entry
        assert result["device_model"].uuid == "test-unique-id"


async def test_polling_response_time_tracking(mock_coordinator):
    """Test that response time is tracked."""
    with (
        patch("custom_components.wiim.coordinator_polling._endpoints.fetch_player_status") as mock_player_status,
        patch("custom_components.wiim.coordinator_polling._endpoints.fetch_device_info") as mock_device_info,
        patch.object(mock_coordinator, "_get_multiroom_info_defensive") as mock_multiroom,
        patch.object(mock_coordinator, "_get_track_metadata_defensive") as mock_metadata,
        patch.object(mock_coordinator, "_get_eq_info_defensive") as mock_eq,
        patch.object(mock_coordinator, "_detect_role_from_status_and_slaves") as mock_role,
        patch.object(mock_coordinator, "_resolve_multiroom_source_and_media") as mock_resolve,
        patch.object(mock_coordinator, "_update_speaker_object") as mock_update_speaker,
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

        await async_update_data(mock_coordinator)

        # Response time should be recorded
        assert mock_coordinator._last_response_time is not None
        assert mock_coordinator._last_response_time > 0


async def test_polling_command_failure_clearing(mock_coordinator):
    """Test that command failures are cleared on success."""
    mock_coordinator._last_command_failure = 12345.0  # Some timestamp

    with (
        patch("custom_components.wiim.coordinator_polling._endpoints.fetch_player_status") as mock_player_status,
        patch("custom_components.wiim.coordinator_polling._endpoints.fetch_device_info") as mock_device_info,
        patch.object(mock_coordinator, "_get_multiroom_info_defensive") as mock_multiroom,
        patch.object(mock_coordinator, "_get_track_metadata_defensive") as mock_metadata,
        patch.object(mock_coordinator, "_get_eq_info_defensive") as mock_eq,
        patch.object(mock_coordinator, "_detect_role_from_status_and_slaves") as mock_role,
        patch.object(mock_coordinator, "_resolve_multiroom_source_and_media") as mock_resolve,
        patch.object(mock_coordinator, "_update_speaker_object") as mock_update_speaker,
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

        await async_update_data(mock_coordinator)

        # Command failures should be cleared
        mock_coordinator.clear_command_failures.assert_called_once()
