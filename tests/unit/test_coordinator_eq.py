"""Test coordinator EQ helpers."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.wiim.api import WiiMError
from custom_components.wiim.coordinator_eq import fetch_eq_info
from custom_components.wiim.models import EQInfo


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator for EQ testing."""
    coordinator = MagicMock()
    coordinator.client = MagicMock()
    coordinator.client.host = "192.168.1.100"
    coordinator._eq_supported = None  # Not yet tested
    return coordinator


async def test_eq_info_not_supported(mock_coordinator):
    """Test EQ info when EQ is not supported."""
    mock_coordinator._eq_supported = False

    result = await fetch_eq_info(mock_coordinator)

    assert isinstance(result, EQInfo)
    assert result.eq_enabled is None
    assert result.eq_preset is None


async def test_eq_info_success_first_time(mock_coordinator):
    """Test successful EQ info collection on first attempt."""
    mock_coordinator._eq_supported = None  # First time
    mock_coordinator.client.get_eq_status = AsyncMock(return_value=True)
    mock_coordinator.client.get_eq = AsyncMock(return_value={"enabled": True, "preset": "rock", "EQ": "Rock Mode"})

    result = await fetch_eq_info(mock_coordinator)

    assert isinstance(result, EQInfo)
    assert result.eq_enabled is True
    assert result.eq_preset == "Rock Mode"  # Should extract from "EQ" field
    assert mock_coordinator._eq_supported is True  # Should be marked as supported


async def test_eq_info_success_already_supported(mock_coordinator):
    """Test EQ info when already known to be supported."""
    mock_coordinator._eq_supported = True
    mock_coordinator.client.get_eq_status = AsyncMock(return_value=False)
    mock_coordinator.client.get_eq = AsyncMock(return_value={"enabled": False, "preset": "flat"})

    result = await fetch_eq_info(mock_coordinator)

    assert isinstance(result, EQInfo)
    assert result.eq_enabled is False
    assert result.eq_preset == "flat"


async def test_eq_info_unknown_command_response(mock_coordinator):
    """Test EQ info when device returns 'unknown command'."""
    mock_coordinator._eq_supported = None
    mock_coordinator.client.get_eq_status = AsyncMock(return_value=True)
    mock_coordinator.client.get_eq = AsyncMock(return_value={"raw": "unknown command: getEQ"})

    result = await fetch_eq_info(mock_coordinator)

    assert isinstance(result, EQInfo)
    assert result.eq_enabled is True  # Status was successful
    assert result.eq_preset is None  # But no preset due to unknown command
    assert mock_coordinator._eq_supported is False  # Should be marked as not supported


async def test_eq_info_preset_field_variations(mock_coordinator):
    """Test EQ info with different preset field names."""
    mock_coordinator._eq_supported = True
    mock_coordinator.client.get_eq_status = AsyncMock(return_value=True)

    # Test various field names that might contain the preset
    preset_fields = [
        ("preset", "Classical"),
        ("EQ", "Jazz"),
        ("eq_preset", "Pop"),
        ("eq_mode", "Vocal"),
        ("sound_mode", "Rock"),
    ]

    for field_name, preset_value in preset_fields:
        mock_coordinator.client.get_eq = AsyncMock(return_value={field_name: preset_value})

        result = await fetch_eq_info(mock_coordinator)

        assert isinstance(result, EQInfo)
        assert result.eq_preset == preset_value


async def test_eq_info_wiim_error_first_time(mock_coordinator):
    """Test EQ info when WiiMError occurs on first attempt."""
    mock_coordinator._eq_supported = None  # First time
    mock_coordinator.client.get_eq_status = AsyncMock(side_effect=WiiMError("EQ not supported"))

    result = await fetch_eq_info(mock_coordinator)

    assert isinstance(result, EQInfo)
    assert result.eq_enabled is None
    assert result.eq_preset is None
    assert mock_coordinator._eq_supported is False  # Should be marked as not supported


async def test_eq_info_wiim_error_known_supported(mock_coordinator):
    """Test EQ info when WiiMError occurs on known supported device."""
    mock_coordinator._eq_supported = True  # Known to be supported
    mock_coordinator.client.get_eq_status = AsyncMock(side_effect=WiiMError("Temporary failure"))

    result = await fetch_eq_info(mock_coordinator)

    assert isinstance(result, EQInfo)
    assert result.eq_enabled is None
    assert result.eq_preset is None
    # Should remain marked as supported (temporary failure)
    assert mock_coordinator._eq_supported is True


async def test_eq_info_partial_data(mock_coordinator):
    """Test EQ info with partial data available."""
    mock_coordinator._eq_supported = True
    mock_coordinator.client.get_eq_status = AsyncMock(return_value=True)
    mock_coordinator.client.get_eq = AsyncMock(return_value={})  # Empty data

    result = await fetch_eq_info(mock_coordinator)

    assert isinstance(result, EQInfo)
    assert result.eq_enabled is True  # From status call
    assert result.eq_preset is None  # No preset data available


async def test_eq_info_status_failure_eq_success(mock_coordinator):
    """Test EQ info when status fails but EQ data succeeds."""
    mock_coordinator._eq_supported = True
    mock_coordinator.client.get_eq_status = AsyncMock(side_effect=WiiMError("Status failed"))
    mock_coordinator.client.get_eq = AsyncMock(return_value={"enabled": False, "preset": "flat"})

    result = await fetch_eq_info(mock_coordinator)

    assert isinstance(result, EQInfo)
    # Should use data from get_eq call
    assert result.eq_enabled is False
    assert result.eq_preset == "flat"
