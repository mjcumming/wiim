# WiiM Integration - Entity Reference

> **Purpose**: Complete documentation of all entities created by the WiiM integration, their purpose, and when they're available.

---

## 🔑 **CRITICAL ENTITIES (Always Available)**

These entities are ESSENTIAL for WiiM functionality and are **NEVER optional**.

### **Media Player Entity**

- **Entity ID**: `media_player.{device_name}`
- **Purpose**: Primary device control (play, pause, volume, grouping)
- **Always Available**: ✅ Yes - Core functionality
- **Platform**: `media_player`

### **🔴 MULTIROOM ROLE SENSOR (MOST IMPORTANT)**

- **Entity ID**: `sensor.{device_name}_multiroom_role`
- **Purpose**: Shows multiroom group status - **ESSENTIAL for user understanding**
- **Always Available**: ✅ Yes - Never hidden
- **Platform**: `sensor`

**States**:

- **"Solo"** - Speaker operates independently
- **"Master"** - Group leader that controls all slaves
- **"Slave"** - Group member that follows master commands

**Why This Sensor is CRITICAL**:

1. **🎯 Multiroom Understanding** - Users MUST know group hierarchy
2. **🔧 Essential for Troubleshooting** - When groups fail, users need to see roles
3. **🏠 Required for Automations** - Scripts need to know which speaker to control
4. **📱 Dashboard Display** - Role status drives UI decisions
5. **🎛️ Group Operations** - Users must know master vs slave for control

**Attributes**:

```yaml
sensor.living_room_multiroom_role:
  state: "Master"
  attributes:
    is_group_coordinator: true
    group_members_count: 3
    group_member_names: ["Living Room", "Kitchen", "Dining Room"]
    coordinator_name: null # Only for slaves
```

---

## 🔧 **MAINTENANCE ENTITIES (Default: Enabled)**

Useful for device management and troubleshooting. **Default: ON** (can be disabled).

### **Reboot Button**

- **Entity ID**: `button.{device_name}_reboot`
- **Purpose**: Restart device for troubleshooting
- **Default**: ✅ Enabled (can disable via config)
- **Platform**: `button`

### **Sync Time Button**

- **Entity ID**: `button.{device_name}_sync_time`
- **Purpose**: Synchronize device clock with network time
- **Default**: ✅ Enabled (can disable via config)
- **Platform**: `button`

---

## 📊 **DIAGNOSTIC ENTITIES (Default: Disabled)**

Advanced entities for developers and troubleshooting. **Default: OFF** (can be enabled).

### **Activity Level Sensor**

- **Entity ID**: `sensor.{device_name}_activity_level`
- **Purpose**: Shows defensive polling state for performance monitoring
- **Default**: ❌ Disabled (enable via diagnostic entities option)
- **Platform**: `sensor`

**States**:

- **"PLAYING"** - Device is playing, using fast polling (1s)
- **"IDLE"** - Device is idle, using slower polling (5s)

**Attributes**:

```yaml
sensor.living_room_activity_level:
  state: "PLAYING"
  attributes:
    polling_interval: 1
    playing_interval: 1
    idle_interval: 5
    statusex_supported: true
    metadata_supported: true
    eq_supported: false
    coordinator_ip: "192.168.1.100"
```

### **Polling Interval Sensor**

- **Entity ID**: `sensor.{device_name}_polling_interval`
- **Purpose**: Shows current defensive polling interval in seconds
- **Default**: ❌ Disabled (enable via diagnostic entities option)
- **Platform**: `sensor`

**Attributes**:

```yaml
sensor.living_room_polling_interval:
  state: 1 # seconds
  attributes:
    playing_rate: 1
    idle_rate: 5
    defensive_polling_enabled: true
    coordinator_available: true
```

---

## 🎛️ **ENTITY FILTERING CONFIGURATION**

Users control which optional entities are created through **Settings → Configure**.

### **Configuration Options**

| Option                  | Controls                     | Default    | Purpose                               |
| ----------------------- | ---------------------------- | ---------- | ------------------------------------- |
| **Maintenance Buttons** | `button.*` entities          | ✅ **ON**  | Device management (reboot, sync time) |
| **Diagnostic Entities** | Advanced `sensor.*` entities | ❌ **OFF** | Developer/troubleshooting tools       |

### **Why These Defaults?**

1. **Role Sensor Always ON** - Critical for multiroom understanding
2. **Maintenance Buttons ON** - Useful for most users, not overwhelming
3. **Diagnostic Entities OFF** - Advanced use only, avoid clutter

---

## 📊 **ENTITY COUNT BY CONFIGURATION**

| Configuration       | Entity Count | Entities Included            |
| ------------------- | ------------ | ---------------------------- |
| **Minimal**         | 2            | Media player + Role sensor   |
| **Default**         | 4            | + Reboot + Sync Time buttons |
| **Full Diagnostic** | 6            | + Activity + Polling sensors |

---

## 🔍 **ENTITY NAMING CONVENTION**

All entities use **clean device names** instead of IP addresses:

```yaml
# GOOD: Clean device-based entity IDs
media_player.living_room_speakers
sensor.living_room_speakers_multiroom_role
button.living_room_speakers_reboot

# BAD: Ugly IP-based entity IDs (old behavior)
media_player.wiim_192_168_1_68_wiim_192_168_1_68
sensor.wiim_192_168_1_68_wiim_192_168_1_68_multiroom_role
```

**Naming Rules**:

- Based on device name from WiiM device settings
- No IP addresses in entity IDs
- Clean, user-friendly names
- Consistent across all platforms

---

## 🎯 **ENTITY PLATFORM BREAKDOWN**

### **Always Loaded Platforms**

| Platform       | Purpose                   | Entity Count   |
| -------------- | ------------------------- | -------------- |
| `media_player` | Device control            | 1 per device   |
| `sensor`       | Role sensor + diagnostics | 1-3 per device |

### **Optional Platforms**

| Platform | Controlled By              | Default | Entity Count |
| -------- | -------------------------- | ------- | ------------ |
| `button` | Maintenance buttons option | ON      | 2 per device |

---

## 🚨 **CRITICAL: Role Sensor Architecture**

The role sensor is implemented with special architecture considerations:

### **Always Available Design**

```python
# sensor.py - ALWAYS creates role sensor
async def async_setup_entry(hass, config_entry, async_add_entities):
    entities = []

    # ALWAYS CREATE: Role sensor - ESSENTIAL for multiroom understanding
    entities.append(WiiMRoleSensor(speaker))  # ← NEVER optional

    # OPTIONAL: Diagnostic sensors only when user enables them
    if entry.options.get(CONF_ENABLE_DIAGNOSTIC_ENTITIES, False):
        entities.extend([...])
```

### **Platform Loading**

```python
# __init__.py - Sensor platform is core, not optional
CORE_PLATFORMS = [
    Platform.MEDIA_PLAYER,  # Always enabled
    Platform.SENSOR,        # Always enabled - for role sensor
]
```

### **Entity State Management**

The role sensor state is updated via the Speaker-centric architecture:

```python
# data.py - Speaker class manages role state
class Speaker:
    def update_from_coordinator_data(self, data: dict) -> None:
        old_role = self.role
        self.role = data.get("role", "solo")

        # If role changed, notify ALL entities (including role sensor)
        if old_role != self.role:
            self.async_write_entity_states()  # Event-driven updates
```

---

## 📝 **AUTOMATION EXAMPLES**

The role sensor enables powerful automation patterns:

### **Group Formation Detection**

```yaml
automation:
  - alias: "Notify when speakers group"
    trigger:
      platform: state
      entity_id: sensor.living_room_multiroom_role
      to: "Master"
    action:
      service: notify.mobile_app
      data:
        message: "Living room is now controlling a speaker group"

  - alias: "Lower volume when joining group"
    trigger:
      platform: state
      entity_id: sensor.kitchen_multiroom_role
      to: "Slave"
    action:
      service: media_player.volume_set
      target:
        entity_id: media_player.kitchen
      data:
        volume_level: 0.6 # Lower volume for group member
```

### **Master Speaker Logic**

```yaml
automation:
  - alias: "Only control master for group operations"
    trigger:
      platform: state
      entity_id: input_boolean.play_everywhere
      to: "on"
    action:
      - service: media_player.media_play
        target:
          entity_id: >
            {%- for entity in states.sensor -%}
              {%- if entity.entity_id.endswith('_multiroom_role') and entity.state == 'Master' -%}
                {{ entity.entity_id.replace('sensor.', 'media_player.').replace('_multiroom_role', '') }}
              {%- endif -%}
            {%- endfor -%}
```

This architecture ensures the role sensor is **always available** and **never hidden** because it's **essential for multiroom understanding**, not diagnostic information.

**Entity Details:**

- **Entity ID**: `sensor.{device_name}_multiroom_role`
- **States**: `Solo` | `Master` | `Slave`
- **Icon**: `mdi:account-group`
- **Attributes**: Group member count, coordinator name, member names
