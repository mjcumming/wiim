# Test Fixtures Documentation

Complete guide to all test fixtures available in the WiiM integration tests.

## Realistic Player Fixtures

Located in `tests/fixtures/realistic_player.py`, these fixtures provide Player mocks that behave like real pywiim Player objects.

### `realistic_player`

Basic Player mock with callback simulation.

**Usage**:
```python
def test_volume_control(realistic_player):
    assert realistic_player.volume_level == 0.5
    await realistic_player.set_volume(0.7)
    assert realistic_player.volume_level == 0.7
```

**Features**:
- Simulates callback behavior when commands are called
- Returns proper types for all properties
- Handles state transitions correctly

### `realistic_player_solo`

Solo player (not in a group).

**Usage**:
```python
def test_solo_behavior(realistic_player_solo):
    assert realistic_player_solo.is_solo is True
    assert realistic_player_solo.is_master is False
    assert realistic_player_solo.is_slave is False
```

### `realistic_player_master`

Master player in a multiroom group.

**Usage**:
```python
def test_master_behavior(realistic_player_master):
    assert realistic_player_master.is_master is True
    assert realistic_player_master.role == "master"
```

### `realistic_player_slave`

Slave player in a multiroom group.

**Usage**:
```python
def test_slave_behavior(realistic_player_slave):
    assert realistic_player_slave.is_slave is True
    assert realistic_player_slave.role == "slave"
```

### `realistic_group`

Group mock for multiroom testing with master and slave.

**Usage**:
```python
def test_group_operations(realistic_group):
    group = realistic_group
    assert group.master.is_master is True
    assert len(group.slaves) > 0
    await group.set_volume_all(0.5)
```

### `player_with_state`

Parameterized fixture for different player states.

**Usage**:
```python
def test_custom_state(player_with_state):
    player = player_with_state(role="master", play_state="play", volume_level=0.8)
    assert player.is_master is True
    assert player.play_state == "play"
    assert player.volume_level == 0.8
```

## Core Mock Fixtures

Located in `tests/conftest.py`.

### `mock_wiim_client`

Mock WiiM API client with common methods.

### `mock_coordinator`

Mock coordinator with standard data structure.

### `wiim_coordinator`

Mock coordinator with full player object.

### `wiim_speaker`

Test Speaker instance with HA integration.

### `wiim_speaker_slave`

Test slave Speaker for group testing.

## Integration Test Fixtures

Located in `tests/integration/conftest.py`.

### `real_player_with_mocked_http`

Real pywiim Player object with mocked HTTP client.

**Usage**:
```python
async def test_real_player(real_player_with_mocked_http):
    player = real_player_with_mocked_http
    await player.refresh()
    assert player.volume_level is not None
```

### `coordinator_with_real_player`

Coordinator with real Player object.

**Usage**:
```python
async def test_coordinator_integration(coordinator_with_real_player):
    coordinator = coordinator_with_real_player
    data = await coordinator._async_update_data()
    assert "player" in data
```

## When to Use Which Fixture

- **Unit tests**: Use `realistic_player` or specific role fixtures
- **Integration tests**: Use `real_player_with_mocked_http` or `coordinator_with_real_player`
- **Group testing**: Use `realistic_group` with master/slave fixtures
- **Custom states**: Use `player_with_state` parameterized fixture

## Creating New Fixtures

When creating new fixtures:

1. Place in appropriate `conftest.py` (unit vs integration)
2. Use `realistic_player.py` pattern for Player mocks
3. Document in this file
4. Add examples to test files

