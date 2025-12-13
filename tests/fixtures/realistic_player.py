"""Realistic Player mock fixtures that simulate pywiim Player behavior.

These fixtures provide Player mocks that behave like real pywiim Player objects,
including callback simulation, state transitions, and Group object support.
"""

from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock

import pytest


def create_realistic_player(
    host: str = "192.168.1.100",
    role: str = "solo",
    play_state: str = "stop",
    volume_level: float = 0.5,
    is_muted: bool = False,
    source: str | None = None,
    on_state_changed: Callable | None = None,
) -> MagicMock:
    """Create a realistic Player mock that simulates pywiim Player behavior.

    Args:
        host: Device IP address
        role: Device role ("solo", "master", "slave")
        play_state: Current playback state ("play", "pause", "stop", "idle")
        volume_level: Volume level (0.0-1.0)
        is_muted: Mute state
        source: Current source (e.g., "Spotify", "AirPlay", "Line In")
        on_state_changed: Optional callback function to fire on state changes

    Returns:
        MagicMock configured as a realistic Player object
    """
    player = MagicMock()

    # Device identity properties
    player.host = host
    player.port = 80
    player.name = "Test WiiM"
    player.model = "WiiM Mini"
    player.firmware = "4.6.328252"
    player.mac_address = "aa:bb:cc:dd:ee:ff"
    player.uuid = "test-speaker-uuid"
    player.discovered_endpoint = None
    player.input_list = ["bluetooth", "line_in", "optical"]

    # Playback state properties
    player.volume_level = volume_level
    player.is_muted = is_muted
    player.play_state = play_state
    player.source = source

    # Role and group properties
    player.role = role
    player.is_solo = role == "solo"
    player.is_master = role == "master"
    player.is_slave = role == "slave"
    player.group = None  # Will be set by realistic_group fixture if needed
    player.group_master_name = None

    # Media properties
    player.media_title = None
    player.media_artist = None
    player.media_album = None
    player.media_duration = None
    player.media_position = None
    player.media_position_updated_at = None
    player.media_image_url = None
    player.media_content_id = None

    # Audio quality properties
    player.media_sample_rate = None
    player.media_bit_depth = None
    player.media_bit_rate = None
    player.media_codec = None

    # EQ properties
    player.supports_eq = True
    player.eq_preset = None
    player.eq_presets = ["Flat", "Bass", "Treble", "Acoustic", "Rock"]

    # Shuffle/repeat properties
    player.shuffle = None
    player.repeat = None
    player.shuffle_supported = True
    player.repeat_supported = True

    # Transport support
    player.supports_next_track = True
    player.supports_previous_track = True

    # Available sources
    player.available_sources = ["bluetooth", "line_in", "optical"]
    if source:
        player.available_sources.append(source)

    # Audio output
    player.audio_output_mode = "Line Out"
    player.is_bluetooth_output_active = False
    player.available_outputs = ["Line Out", "Optical Out"]
    player.available_output_modes = ["Line Out", "Optical Out"]
    player.bluetooth_output_devices = []

    # Store callback
    player._on_state_changed = on_state_changed

    # Helper to fire callbacks
    def fire_callback():
        """Fire the state changed callback if set."""
        if player._on_state_changed:
            player._on_state_changed()

    # Command methods with callback simulation
    async def play():
        """Simulate play command with state update and callback."""
        player.play_state = "play"
        fire_callback()

    async def pause():
        """Simulate pause command with state update and callback."""
        player.play_state = "pause"
        fire_callback()

    async def stop():
        """Simulate stop command with state update and callback."""
        player.play_state = "stop"
        fire_callback()

    async def set_volume(volume: float):
        """Simulate volume set with state update and callback."""
        player.volume_level = max(0.0, min(1.0, volume))
        fire_callback()

    async def set_mute(muted: bool):
        """Simulate mute set with state update and callback."""
        player.is_muted = muted
        fire_callback()

    async def set_source(src: str):
        """Simulate source change with state update and callback."""
        player.source = src
        if src not in player.available_sources:
            player.available_sources.append(src)
        fire_callback()

    async def next_track():
        """Simulate next track with callback."""
        fire_callback()

    async def previous_track():
        """Simulate previous track with callback."""
        fire_callback()

    async def seek(position: int):
        """Simulate seek with state update and callback."""
        if player.media_duration:
            player.media_position = min(position, player.media_duration)
        else:
            player.media_position = position
        fire_callback()

    async def set_eq_preset(preset: str):
        """Simulate EQ preset change with state update and callback."""
        player.eq_preset = preset.title()  # Normalize to Title Case
        fire_callback()

    async def set_shuffle(enabled: bool):
        """Simulate shuffle toggle with state update and callback."""
        player.shuffle = enabled
        fire_callback()

    async def refresh():
        """Simulate refresh - updates state from device."""
        # In real pywiim, this would fetch from device
        # For mocks, we just fire callback to simulate state update
        fire_callback()

    # Assign async methods
    player.play = AsyncMock(side_effect=play)
    player.pause = AsyncMock(side_effect=pause)
    player.stop = AsyncMock(side_effect=stop)
    player.set_volume = AsyncMock(side_effect=set_volume)
    player.set_mute = AsyncMock(side_effect=set_mute)
    player.set_source = AsyncMock(side_effect=set_source)
    player.next_track = AsyncMock(side_effect=next_track)
    player.previous_track = AsyncMock(side_effect=previous_track)
    player.seek = AsyncMock(side_effect=seek)
    player.set_eq_preset = AsyncMock(side_effect=set_eq_preset)
    player.set_shuffle = AsyncMock(side_effect=set_shuffle)
    player.refresh = AsyncMock(side_effect=refresh)

    # Other methods
    player.reboot = AsyncMock()
    player.get_eq = AsyncMock(return_value={})
    player.get_eq_presets = AsyncMock(return_value=player.eq_presets)
    player.get_eq_status = AsyncMock(return_value=True)

    # Client reference
    player.client = MagicMock()
    player.client.host = host
    player.client.close = AsyncMock()

    return player


def create_realistic_group(master_player: MagicMock, slave_players: list[MagicMock] | None = None) -> MagicMock:
    """Create a realistic Group mock for multiroom testing.

    Args:
        master_player: The master Player object
        slave_players: List of slave Player objects (optional)

    Returns:
        MagicMock configured as a realistic Group object
    """
    if slave_players is None:
        slave_players = []

    group = MagicMock()
    group.master = master_player
    group.slaves = slave_players
    group.all_players = [master_player] + slave_players
    group.size = len(group.all_players)

    # Group properties (computed from players)
    @property
    def volume_level():
        """Group volume = MAX of all devices."""
        volumes = [p.volume_level for p in group.all_players if p.volume_level is not None]
        return max(volumes) if volumes else None

    @property
    def is_muted():
        """Group mute = ALL devices muted."""
        muted_states = [p.is_muted for p in group.all_players if p.is_muted is not None]
        return all(muted_states) if muted_states else None

    @property
    def play_state():
        """Group play state = master's play state."""
        return master_player.play_state

    group.volume_level = volume_level
    group.is_muted = is_muted
    group.play_state = play_state

    # Group operations
    async def set_volume_all(volume: float):
        """Set volume on all group members."""
        for player in group.all_players:
            await player.set_volume(volume)

    async def mute_all(muted: bool):
        """Mute/unmute all group members."""
        for player in group.all_players:
            await player.set_mute(muted)

    async def play():
        """Play on master (affects all slaves)."""
        await master_player.play()

    async def pause():
        """Pause on master (affects all slaves)."""
        await master_player.pause()

    async def stop():
        """Stop on master (affects all slaves)."""
        await master_player.stop()

    async def disband():
        """Disband the group."""
        for player in group.all_players:
            player.role = "solo"
            player.is_solo = True
            player.is_master = False
            player.is_slave = False
            player.group = None

    group.set_volume_all = AsyncMock(side_effect=set_volume_all)
    group.mute_all = AsyncMock(side_effect=mute_all)
    group.play = AsyncMock(side_effect=play)
    group.pause = AsyncMock(side_effect=pause)
    group.stop = AsyncMock(side_effect=stop)
    group.disband = AsyncMock(side_effect=disband)

    # Link players to group
    master_player.group = group
    master_player.role = "master"
    master_player.is_master = True
    master_player.is_solo = False
    master_player.is_slave = False

    for slave in slave_players:
        slave.group = group
        slave.role = "slave"
        slave.is_slave = True
        slave.is_master = False
        slave.is_solo = False

    return group


@pytest.fixture
def realistic_player():
    """Fixture providing a realistic Player mock with callback simulation."""
    return create_realistic_player()


@pytest.fixture
def realistic_player_solo():
    """Fixture providing a solo Player mock."""
    return create_realistic_player(role="solo")


@pytest.fixture
def realistic_player_master():
    """Fixture providing a master Player mock."""
    return create_realistic_player(role="master", play_state="play")


@pytest.fixture
def realistic_player_slave():
    """Fixture providing a slave Player mock."""
    return create_realistic_player(role="slave", host="192.168.1.101")


@pytest.fixture
def realistic_group(realistic_player_master, realistic_player_slave):
    """Fixture providing a realistic Group mock with master and slave."""
    return create_realistic_group(realistic_player_master, [realistic_player_slave])


@pytest.fixture
def player_with_state():
    """Parameterized fixture for different player states."""
    def _create_player(**kwargs):
        return create_realistic_player(**kwargs)
    return _create_player

