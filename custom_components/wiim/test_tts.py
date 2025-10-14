"""Test TTS functionality for WiiM integration."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.media_player import MediaPlayerState, MediaType
from homeassistant.exceptions import HomeAssistantError

from .media_player_commands import MediaCommandsMixin


class MockSpeaker:
    """Mock speaker for testing."""

    def __init__(self, name: str, role: str = "solo"):
        self.name = name
        self.role = role
        self.coordinator_speaker = None
        self._async_handle_tts_announcement = AsyncMock()


class MockController:
    """Mock controller for testing."""

    def __init__(self):
        self.set_volume = AsyncMock()
        self.set_mute = AsyncMock()
        self.pause = AsyncMock()
        self.play = AsyncMock()
        self.play_url = AsyncMock()


class MockMediaPlayer(MediaCommandsMixin):
    """Mock media player for testing TTS functionality."""

    def __init__(self, speaker: MockSpeaker):
        self.speaker = speaker
        self.controller = MockController()
        self.hass = MagicMock()
        self._optimistic_volume = None
        self._optimistic_mute = None
        self._optimistic_state = None
        self._optimistic_source = None
        self._optimistic_media_title = None
        self._optimistic_group_state = None
        self._optimistic_group_members = None
        self._optimistic_state_timestamp = None
        self._pending_volume = None
        self._volume_debouncer = None
        self._last_track_info = {}
        self._last_duration = None
        self._quick_station_cache = []

    @property
    def volume_level(self) -> float | None:
        return 0.5

    @property
    def is_volume_muted(self) -> bool | None:
        return False

    @property
    def state(self) -> MediaPlayerState | None:
        return MediaPlayerState.PLAYING

    @property
    def media_position(self) -> int | None:
        return 30

    @property
    def source(self) -> str | None:
        return "WiFi"

    def async_write_ha_state(self) -> None:
        pass


@pytest.mark.asyncio
async def test_tts_solo_speaker():
    """Test TTS on a solo speaker."""
    speaker = MockSpeaker("Test Speaker", "solo")
    player = MockMediaPlayer(speaker)

    # Test TTS announcement
    await player.async_play_media(MediaType.MUSIC, "media-source://tts?message=hello", announce=True)

    # Verify TTS was handled locally
    assert speaker._async_handle_tts_announcement.called


@pytest.mark.asyncio
async def test_tts_slave_speaker():
    """Test TTS on a slave speaker delegates to master."""
    master = MockSpeaker("Master Speaker", "master")
    slave = MockSpeaker("Slave Speaker", "slave")
    slave.coordinator_speaker = master

    player = MockMediaPlayer(slave)

    # Test TTS announcement
    await player.async_play_media(MediaType.MUSIC, "media-source://tts?message=hello", announce=True)

    # Verify TTS was delegated to master
    assert master._async_handle_tts_announcement.called


@pytest.mark.asyncio
async def test_tts_slave_no_master():
    """Test TTS on a slave without master raises error."""
    slave = MockSpeaker("Slave Speaker", "slave")
    # No coordinator_speaker set

    player = MockMediaPlayer(slave)

    # Test TTS announcement should fail
    with pytest.raises(HomeAssistantError, match="cannot play TTS independently"):
        await player.async_play_media(MediaType.MUSIC, "media-source://tts?message=hello", announce=True)


@pytest.mark.asyncio
async def test_tts_force_local():
    """Test force_local TTS behavior."""
    slave = MockSpeaker("Slave Speaker", "slave")
    master = MockSpeaker("Master Speaker", "master")
    slave.coordinator_speaker = master

    player = MockMediaPlayer(slave)

    # Test force_local TTS
    await player.async_play_media(
        MediaType.MUSIC, "media-source://tts?message=hello", announce=True, extra={"tts_behavior": "force_local"}
    )

    # Should play locally despite being slave
    assert slave._async_handle_tts_announcement.called


@pytest.mark.asyncio
async def test_tts_force_group():
    """Test force_group TTS behavior."""
    master = MockSpeaker("Master Speaker", "master")
    player = MockMediaPlayer(master)

    # Test force_group TTS on master
    await player.async_play_media(
        MediaType.MUSIC, "media-source://tts?message=hello", announce=True, extra={"tts_behavior": "force_group"}
    )

    # Should play locally since it's already master
    assert master._async_handle_tts_announcement.called


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__])
