# WiiM Platform Entities Architecture Guide

> **Goal**: Document the comprehensive platform entity ecosystem that leverages our Speaker-centric architecture for device monitoring, control, and configuration.

---

## 🏗️ **Entity Architecture Overview**

Our platform entities follow a **clean delegation pattern** where all business logic resides in the `Speaker` class, and entities serve as thin UI adapters that provide Home Assistant integration points.

### **Core Design Principles**

1. **Event-Driven Updates**: All entities listen for Speaker state changes via dispatchers
2. **Speaker Delegation**: Entities delegate all logic to their Speaker reference
3. **Consistent Patterns**: All entities follow the same architecture and naming conventions
4. **Rich Diagnostics**: Entities provide comprehensive monitoring and troubleshooting information

---

## 🎯 **Entity Inheritance Pattern**

### **Base Architecture**

```python
class WiiMSensorExample(WiimEntity, SensorEntity):
    """Example sensor following our standard pattern."""

    def __init__(self, speaker: Speaker) -> None:
        """Initialize with Speaker reference."""
        super().__init__(speaker)  # Event-driven base
        self._attr_unique_id = f"{speaker.uuid}_example"
        self._attr_name = f"{speaker.name} Example"

    @property
    def native_value(self) -> str | None:
        """Delegate state query to Speaker."""
        return self.speaker.get_example_value()

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Provide rich diagnostic information."""
        return {
            "speaker_uuid": self.speaker.uuid,
            "coordinator_ip": self.speaker.coordinator.client.host,
        }
```

### **Key Architecture Elements**

- **WiimEntity Base**: Provides event-driven updates and Speaker integration
- **Speaker Reference**: Direct access to rich business object
- **UUID-Based IDs**: Consistent `{speaker.uuid}_{suffix}` pattern
- **Name Convention**: `{speaker.name} {Function}` format
- **Rich Attributes**: Comprehensive diagnostic information

---

## 📊 **Platform Implementation Details**

### **Media Player** (`platforms/media_player.py`)

**Purpose**: Core audio control interface with full media player functionality.

```python
class WiiMMediaPlayer(WiimEntity, MediaPlayerEntity):
    """Ultra-clean media player - all logic delegated to Speaker."""

    @property
    def state(self) -> MediaPlayerState:
        return self.speaker.get_playback_state()

    async def async_play(self) -> None:
        await self.speaker.coordinator.client.play()
        await self._request_refresh_and_record_command("play")
```

**Key Features**:

- **88% Code Reduction**: From 1,762 → 211 lines
- **Full Functionality**: All media control features preserved
- **Smart Polling**: User commands optimize polling intervals
- **Group Management**: Delegates to Speaker group methods

---

### **Sensors** (`platforms/sensor.py`)

**Purpose**: Device monitoring and diagnostics with real-time status information.

#### **IP Address Sensor**

```python
class WiiMIPSensor(WiimEntity, SensorEntity):
    """Network monitoring for device IP tracking."""

    @property
    def native_value(self) -> str:
        return self.speaker.ip
```

#### **Group Role Sensor**

```python
class WiiMRoleSensor(WiimEntity, SensorEntity):
    """Multiroom group role monitoring."""

    @property
    def native_value(self) -> str:
        return self.speaker.role.title()
```

#### **Activity Level Sensor**

```python
class WiiMActivitySensor(WiimEntity, SensorEntity):
    """Smart polling activity monitoring."""

    @property
    def native_value(self) -> str | None:
        smart_polling = self.speaker.coordinator.data.get("smart_polling", {})
        return smart_polling.get("activity_level", "UNKNOWN")
```

**Sensor Capabilities**:

- **Real-Time Monitoring**: IP address, group role, polling activity
- **Rich Diagnostics**: MAC address, UUID, coordinator status
- **Performance Tracking**: Smart polling metrics and optimization

---

### **Buttons** (`platforms/button.py`)

**Purpose**: Device management and maintenance actions with smart polling integration.

#### **Reboot Button**

```python
class WiiMRebootButton(WiimEntity, ButtonEntity):
    """System maintenance and restart control."""

    async def async_press(self) -> None:
        await self.speaker.coordinator.client.reboot()
        self.speaker.coordinator.record_user_command("reboot")
        await self.speaker.coordinator.async_request_refresh()
```

#### **Manual Refresh Button**

```python
class WiiMRefreshButton(WiimEntity, ButtonEntity):
    """Immediate state update and polling boost."""

    async def async_press(self) -> None:
        await self.speaker.coordinator.async_request_refresh()
        # Boost activity for responsive polling
        self.speaker.coordinator.force_activity_level(ActivityLevel.RECENT_ACTIVITY)
```

**Button Capabilities**:

- **Device Management**: Reboot, time sync, manual refresh
- **Smart Integration**: All actions recorded for polling optimization
- **Immediate Feedback**: Actions trigger instant state updates

---

### **Number Entities** (`platforms/number.py`)

**Purpose**: Configurable numeric settings for device optimization and user preferences.

#### **Volume Step Configuration**

```python
class WiiMVolumeStepNumber(WiimEntity, NumberEntity):
    """Granular volume control configuration."""

    _attr_native_min_value = 1
    _attr_native_max_value = 20
    _attr_native_unit_of_measurement = "%"

    async def async_set_native_value(self, value: float) -> None:
        self._volume_step = int(value)
        self.speaker.coordinator.record_user_command("volume_step_change")
```

#### **Polling Interval Configuration**

```python
class WiiMPollingIntervalNumber(WiimEntity, NumberEntity):
    """Smart polling base interval optimization."""

    async def async_set_native_value(self, value: float) -> None:
        self.speaker.coordinator._base_poll_interval = int(value)
        # Update current interval if in low-activity state
```

**Number Entity Features**:

- **User Configuration**: Volume steps, polling intervals
- **Live Updates**: Changes apply immediately
- **Performance Tuning**: Direct integration with smart polling system

---

### **Switches** (`platforms/switch.py`)

**Purpose**: Feature toggles and device capability control with immediate state feedback.

#### **Equalizer Control**

```python
class WiiMEqualizerSwitch(WiimEntity, SwitchEntity):
    """Audio enhancement system control."""

    @property
    def is_on(self) -> bool | None:
        status = self.speaker.coordinator.data.get("status", {})
        return status.get("eq_enabled", False)

    async def async_turn_on(self, **kwargs) -> None:
        await self.speaker.coordinator.client.set_eq_enabled(True)
        self.speaker.coordinator.record_user_command("equalizer_on")
```

#### **Smart Polling Control**

```python
class WiiMSmartPollingSwitch(WiimEntity, SwitchEntity):
    """Performance optimization system control."""

    async def async_turn_off(self, **kwargs) -> None:
        self._smart_polling_enabled = False
        # Revert to fixed polling interval
        base_interval = self.speaker.coordinator._base_poll_interval
        self.speaker.coordinator.update_interval = timedelta(seconds=base_interval)
```

**Switch Capabilities**:

- **Feature Control**: Equalizer, smart polling toggles
- **Immediate Feedback**: State changes reflect instantly
- **System Integration**: Direct hooks into device capabilities

---

### **Binary Sensors** (`platforms/binary_sensor.py`)

**Purpose**: Device status monitoring with on/off state detection and health indicators.

#### **Playback Status**

```python
class WiiMPlayingBinarySensor(WiimEntity, BinarySensorEntity):
    """Real-time media playback monitoring."""

    @property
    def is_on(self) -> bool | None:
        current_state = self.speaker.get_playback_state()
        return current_state == MediaPlayerState.PLAYING
```

#### **Group Activity Status**

```python
class WiiMGroupActiveBinarySensor(WiimEntity, BinarySensorEntity):
    """Multiroom group participation monitoring."""

    @property
    def is_on(self) -> bool:
        return self.speaker.role in ["master", "slave"]
```

#### **Connectivity Status**

```python
class WiiMConnectivityBinarySensor(WiimEntity, BinarySensorEntity):
    """Device health and network connectivity."""

    @property
    def is_on(self) -> bool:
        return self.speaker.available
```

**Binary Sensor Features**:

- **Status Monitoring**: Playback, group participation, connectivity
- **Health Indicators**: Real-time device availability tracking
- **Rich Diagnostics**: Detailed status information in attributes

---

## 🔄 **Event-Driven Update Flow**

### **State Change Propagation**

```
Speaker State Change
       ↓
Speaker.async_write_entity_states()
       ↓
async_dispatcher_send(f"wiim_state_updated_{speaker.uuid}")
       ↓
All entities for this speaker update automatically
```

### **Entity Registration Pattern**

```python
async def async_added_to_hass(self) -> None:
    """Set up event listening when entity is added."""
    # Register in central mapping
    data: WiimData = self.hass.data[DOMAIN]["data"]
    data.entity_id_mappings[self.entity_id] = self.speaker

    # Listen for speaker state changes
    self.async_on_remove(
        async_dispatcher_connect(
            self.hass,
            f"wiim_state_updated_{self.speaker.uuid}",
            self.async_write_ha_state,
        )
    )
```

### **Benefits of Event-Driven Architecture**

- **Zero Polling**: Entities never poll for state updates
- **Instant Updates**: State changes propagate immediately to all entities
- **Efficient**: Single state change updates all related entities
- **Consistent**: All entities reflect the same Speaker state simultaneously

---

## 🎯 **Unique ID and Naming Conventions**

### **Unique ID Pattern**

All entities follow the consistent pattern:

```
{speaker.uuid}_{suffix}
```

**Examples**:

- `abc123_ip` - IP sensor
- `abc123_reboot` - Reboot button
- `abc123_equalizer` - Equalizer switch
- `abc123_playing` - Playing binary sensor

### **Entity Naming Pattern**

All entities follow the consistent pattern:

```
{speaker.name} {Function}
```

**Examples**:

- `Living Room Speaker IP Address`
- `Kitchen Speaker Reboot`
- `Bedroom Speaker Equalizer`
- `Office Speaker Playing`

### **Benefits of Consistent Patterns**

- **Predictable**: Users can easily identify related entities
- **Organized**: Entities group naturally by speaker in the UI
- **Stable**: UUIDs persist across restarts and IP changes
- **Scalable**: Pattern works for any number of speakers

---

## 🧪 **Testing and Validation**

### **Entity Architecture Validation**

Each entity type is validated for:

1. **Inheritance**: Proper inheritance from `WiimEntity`
2. **Speaker Reference**: Correct Speaker object delegation
3. **Unique IDs**: UUID-based identifier patterns
4. **Event Integration**: Response to Speaker state changes
5. **Naming Convention**: Consistent entity naming
6. **Functionality**: Core entity-specific features

### **Test Coverage Areas**

- **Creation**: Entity instantiation with Speaker reference
- **State Reading**: Property delegation to Speaker
- **Actions**: Command execution and coordinator integration
- **Events**: Response to Speaker state change events
- **Attributes**: Rich diagnostic information availability

---

## 🚀 **Extension Guidelines**

### **Adding New Entity Types**

1. **Inherit from WiimEntity**: Use the event-driven base class
2. **Follow Naming Patterns**: UUID-based IDs, consistent names
3. **Delegate to Speaker**: Keep entities thin, logic in Speaker
4. **Rich Diagnostics**: Provide comprehensive extra_state_attributes
5. **Test Integration**: Validate architecture compliance

### **Example New Entity**

```python
class WiiMExampleSensor(WiimEntity, SensorEntity):
    """Example of adding a new sensor type."""

    _attr_icon = "mdi:example"

    def __init__(self, speaker: Speaker) -> None:
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_example"
        self._attr_name = f"{speaker.name} Example"

    @property
    def native_value(self) -> str | None:
        # Delegate to Speaker business logic
        return self.speaker.get_example_data()

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        return {
            "speaker_uuid": self.speaker.uuid,
            "example_details": self.speaker.get_example_details(),
        }
```

---

## 📊 **Platform Entity Summary**

| Platform          | Entities | Lines of Code | Purpose                |
| ----------------- | -------- | ------------- | ---------------------- |
| **media_player**  | 1        | 211           | Core audio control     |
| **sensor**        | 4        | 149           | Device monitoring      |
| **button**        | 3        | 130           | Device management      |
| **number**        | 2        | 137           | Configuration          |
| **switch**        | 2        | 211           | Feature toggles        |
| **binary_sensor** | 3        | 127           | Status monitoring      |
| **Total**         | **15**   | **965**       | **Complete ecosystem** |

### **Architecture Success Metrics**

- ✅ **Consistent Architecture**: All 15 entities follow identical patterns
- ✅ **Event-Driven**: Zero polling, instant state updates
- ✅ **Rich Diagnostics**: Comprehensive monitoring capabilities
- ✅ **Smart Integration**: Full smart polling optimization
- ✅ **Speaker Delegation**: Clean separation of concerns
- ✅ **Future-Proof**: Easy to extend with new entity types

---

This platform entity architecture provides a **world-class foundation** for WiiM device integration, offering comprehensive monitoring, control, and configuration capabilities while maintaining the clean, event-driven architecture that makes the integration maintainable and performant.
