# Features Guide

This guide showcases all capabilities of the WiiM Audio integration for Home Assistant.

## Core Media Player Features

### Playback Controls

**Transport Controls**

- **Play/Pause/Stop**: Standard media player controls
- **Next/Previous Track**: Navigate through playlists
- **Seek**: Jump to specific position in track
- **Shuffle/Repeat**: Toggle playback modes

```yaml
# Service examples
service: media_player.media_play
target:
  entity_id: media_player.living_room

service: media_player.media_next_track
target:
  entity_id: media_player.living_room

service: media_player.set_shuffle
target:
  entity_id: media_player.living_room
data:
  shuffle: true
```

**Playback Modes**

- **Normal**: Linear playback
- **Repeat All**: Loop entire playlist
- **Repeat One**: Loop single track
- **Shuffle**: Random track order
- **Shuffle + Repeat**: Random with looping

### Volume Management

**Volume Control**

- **Absolute**: Set exact volume level (0-100%)
- **Relative**: Increase/decrease by step size
- **Mute**: Toggle speaker mute state
- **Configurable Steps**: Per-device volume increment

```yaml
# Set exact volume
service: media_player.volume_set
target:
  entity_id: media_player.living_room
data:
  volume_level: 0.75  # 75%

# Volume up/down
service: media_player.volume_up
target:
  entity_id: media_player.living_room

# Mute toggle
service: media_player.volume_mute
target:
  entity_id: media_player.living_room
data:
  is_volume_muted: true
```

**Group Volume Features**

- **Unified Control**: Single slider for entire group
- **Relative Scaling**: Maintains volume relationships
- **Individual Override**: Fine-tune specific speakers

### Source Selection

**Supported Sources**

- **Wi-Fi**: Network streaming, internet radio
- **Bluetooth**: Paired devices
- **Line In**: Analog audio input
- **Optical**: Digital optical input
- **USB**: USB audio devices/storage
- **AirPlay**: Apple AirPlay streaming
- **DLNA**: DLNA/UPnP streaming

```yaml
# Switch audio source
service: media_player.select_source
target:
  entity_id: media_player.living_room
data:
  source: "Bluetooth"
```

---

## Audio Enhancement

### Equalizer Control

**EQ Presets**

- **Flat**: No audio coloring
- **Rock**: Enhanced for rock music
- **Jazz**: Optimized for jazz
- **Classical**: Classical music profile
- **Pop**: Modern pop music
- **Bass**: Enhanced low frequencies
- **Treble**: Enhanced high frequencies
- **Vocal**: Voice-optimized

```yaml
# Set EQ preset
service: media_player.select_sound_mode
target:
  entity_id: media_player.living_room
data:
  sound_mode: "Rock"

# Custom EQ service
service: wiim.set_eq
target:
  entity_id: media_player.living_room
data:
  preset: "custom"
  custom_values: [2, 4, 3, 0, -2, 1, 3, 2, 1, 0]  # 10 bands: -12dB to +12dB
```

**Custom EQ**

- **10-Band**: Full frequency spectrum control
- **Range**: -12dB to +12dB per band
- **Real-time**: Immediate audio changes
- **Persistent**: Settings saved to device

### Audio Quality Features

**Format Support**

- **Lossless**: FLAC, WAV, ALAC
- **Compressed**: MP3, AAC, OGG
- **High-Res**: 24-bit/192kHz capable
- **Streaming**: Spotify, Tidal, Amazon Music

**Audio Processing**

- **Dynamic Range**: Preserves audio dynamics
- **Sample Rate**: Auto-detection and conversion
- **Bit-perfect**: Optional bypass mode

---

## Multiroom Audio

### Group Management

**Group Operations**

```yaml
# Create group (join speakers)
service: media_player.join
target:
  entity_id: media_player.living_room  # Master
data:
  group_members:
    - media_player.kitchen
    - media_player.bedroom

# Leave group
service: media_player.unjoin
target:
  entity_id: media_player.bedroom

# Disband entire group
service: media_player.unjoin
target:
  entity_id: media_player.living_room  # Master
```

**Group Roles**

- **Master**: Controls group playback, streams audio
- **Slave**: Receives audio from master
- **Solo**: Independent operation

### Group Entity Features

**Virtual Group Controller**

- **Unified Playback**: Single control for entire group
- **Group Volume**: Coordinated volume management
- **Member Status**: Individual speaker monitoring
- **Metadata Display**: Shows master's current track

**Group Entity Attributes**

```yaml
# Example group entity state
media_player.living_room_group:
  state: playing
  volume_level: 0.8
  attributes:
    member_192_168_1_10_volume: 80
    member_192_168_1_10_mute: false
    member_192_168_1_10_name: "Living Room"
    member_192_168_1_20_volume: 60
    member_192_168_1_20_mute: false
    member_192_168_1_20_name: "Kitchen"
```

### Synchronization

**Audio Sync**

- **Perfect Timing**: <1ms synchronization
- **Network Resilient**: Handles WiFi latency
- **Auto-correction**: Drift compensation
- **Buffer Management**: Optimized for stability

---

## Device Management

### Power Control

**Power States**

- **On**: Actively powered and responsive
- **Standby**: Low power, quick wake
- **Off**: Powered down (if supported)

```yaml
# Power control
service: media_player.turn_on
target:
  entity_id: media_player.living_room

service: media_player.turn_off
target:
  entity_id: media_player.living_room

# Toggle power (custom service)
service: media_player.toggle_power
target:
  entity_id: media_player.living_room
```

### Preset Management

**Hardware Presets**

- **6 Presets**: Device front panel buttons 1-6
- **Custom Content**: User-configured stations/playlists
- **Quick Access**: One-touch playback

```yaml
# Play preset
service: media_player.play_preset
target:
  entity_id: media_player.living_room
data:
  preset: 3 # Preset button 3
```

### Device Information

**Status Monitoring**

- **Network**: IP address, WiFi signal strength
- **Firmware**: Version information
- **Hardware**: Model, capabilities
- **Group Role**: Current multiroom status

**Diagnostic Entities**

```yaml
# Available sensors (optional)
sensor.living_room_multiroom_role: "master"
sensor.living_room_ip_address: "192.168.1.10"
sensor.living_room_wifi_signal: "-45 dBm"
sensor.living_room_firmware: "4.6.2.1"
```

---

## Home Assistant Integration

### Discovery & Setup

**Auto-Discovery**

- **UPnP/SSDP**: Network device discovery
- **Zeroconf**: mDNS service discovery
- **Device Filtering**: WiiM/LinkPlay detection
- **Automatic Setup**: Minimal user configuration

**Manual Configuration**

- **IP Entry**: Direct device addressing
- **Validation**: Connection testing
- **Fallback**: When discovery fails

### Configuration Options

**Per-Device Settings**
| Option | Purpose | Default | Range |
|--------|---------|---------|-------|
| **Polling Interval** | Status update frequency | 5 seconds | 1-60s |
| **Volume Step** | Volume button increment | 5% | 1-50% |
| **Group Entity** | Virtual group controller | Disabled | On/Off |
| **Debug Logging** | Enhanced troubleshooting | Disabled | On/Off |

**Global Settings**

- **Component-wide**: Apply to all devices
- **Individual Override**: Per-device customization
- **Options Flow**: GUI configuration interface

### Entity Types

**Media Player Entities**

- **Device Players**: One per physical speaker
- **Group Players**: Optional virtual group controllers
- **Rich Attributes**: Detailed device information
- **Standard Interface**: Compatible with all HA features

**Additional Entities**

```yaml
# Number entities (configuration)
number.living_room_polling_interval
number.living_room_volume_step

# Button entities (actions)
button.living_room_reboot
button.living_room_sync_time

# Sensor entities (monitoring)
sensor.living_room_multiroom_role
sensor.living_room_wifi_signal
```

---

## Advanced Features

### Media Browsing

**Preset Browser**

- **Built-in Browser**: Home Assistant media browser
- **Preset Access**: Quick selection interface
- **Category Organization**: Grouped by type

```yaml
# Media browser structure
Presets/
├── Preset 1
├── Preset 2
├── Preset 3
├── Preset 4
├── Preset 5
└── Preset 6
```

### Automation Integration

**Triggers**

```yaml
# State changes
trigger:
  platform: state
  entity_id: media_player.living_room
  attribute: source
  to: "Bluetooth"

# Group changes
trigger:
  platform: state
  entity_id: sensor.living_room_multiroom_role
  to: "master"
```

**Actions**

```yaml
# Volume automation
action:
  - service: media_player.volume_set
    target:
      entity_id: media_player.living_room_group
    data:
      volume_level: 0.3  # Night mode

# Source switching
action:
  - service: media_player.select_source
    target:
      entity_id: media_player.bedroom
    data:
      source: "Line In"
```

### Custom Services

**Extended Functionality**

```yaml
# Device maintenance
service: wiim.reboot_device
target:
  entity_id: media_player.living_room

service: wiim.sync_time
target:
  entity_id: media_player.living_room

# Audio enhancement
service: wiim.set_eq
target:
  entity_id: media_player.living_room
data:
  preset: "custom"
  custom_values: [0, 2, 4, 2, 0, -1, 1, 3, 2, 0]

# Playback control
service: wiim.play_url
target:
  entity_id: media_player.living_room
data:
  url: "http://stream.radio.url/live"
```

---

## Performance Features

### Adaptive Polling

**Smart Intervals**

- **Active Playback**: 1-second updates
- **Recently Active**: 5-second updates
- **Idle**: 10-second updates
- **Configurable**: User override available

**Resource Optimization**

- **CPU Efficient**: Minimal processing overhead
- **Network Friendly**: Reduces API calls
- **Battery Aware**: Considers mobile HA installations

### Error Recovery

**Automatic Recovery**

- **Session Management**: Handles connection drops
- **SSL Fallback**: Manages certificate issues
- **Retry Logic**: Intelligent failure handling
- **Status Sync**: Maintains consistency

**Network Resilience**

- **Timeout Handling**: Graceful request failures
- **Connectivity Issues**: Auto-reconnection
- **Group Recovery**: Maintains group state
- **Status Validation**: Prevents inconsistent states

---

## Lovelace Integration

### Media Control Cards

**Standard Cards**

```yaml
# Basic media control
type: media-control
entity: media_player.living_room

# Group control
type: media-control
entity: media_player.living_room_group
```

**Custom Cards** (with community cards)

```yaml
# Mini media player
type: custom:mini-media-player
entity: media_player.living_room
artwork: cover
info: scroll
volume_stateless: true
group: true

# Sonos card (compatible)
type: custom:sonos-card
entities:
  - media_player.living_room
  - media_player.kitchen
  - media_player.bedroom
```

### Dashboard Integration

**Group Dashboards**

- **Multi-room Control**: Group management interface
- **Individual Controls**: Per-speaker adjustment
- **Status Overview**: System-wide monitoring
- **Quick Actions**: Common operations

**Automation Dashboards**

- **Scene Triggers**: Pre-configured audio scenes
- **Time-based**: Automatic scheduling
- **Event-driven**: Responsive to other HA events

---

## API Compatibility

### Home Assistant Standards

**Media Player Platform**

- **Full Compliance**: All standard features
- **Extended Features**: Additional WiiM capabilities
- **Service Compatibility**: Works with all HA services
- **Integration Ecosystem**: Compatible with other integrations

**Device Registry**

- **Proper Identification**: Unique device entries
- **Model Information**: Hardware details
- **Manufacturer Data**: Branding and support info
- **Connection Status**: Network information

### Third-Party Integration

**Voice Assistants**

- **Google Assistant**: "Hey Google, play music in the living room"
- **Amazon Alexa**: "Alexa, set bedroom volume to 50%"
- **Apple Siri**: Limited support via HomeKit bridge

**Automation Platforms**

- **Node-RED**: Advanced automation flows
- **AppDaemon**: Python-based automation
- **MQTT**: External system integration

---

## Future Roadmap

### Planned Features

**Enhanced Audio**

- **Room Correction**: EQ profiles per listening position
- **Audio Profiles**: Day/night/party modes
- **Advanced EQ**: Parametric equalizer
- **Audio Analysis**: Real-time frequency monitoring

**Smart Features**

- **Presence Detection**: Auto-adjust based on occupancy
- **Learning**: Adaptive volume based on time/activity
- **Integration**: Deeper HA ecosystem integration
- **Mobile**: Enhanced mobile app features

**Performance**

- **WebSocket**: Real-time communication
- **Cloud Sync**: Multi-instance HA support
- **Analytics**: Usage patterns and optimization
- **Efficiency**: Further resource optimization

### Community Contributions

**Open Source**

- **GitHub**: Public development
- **Community PRs**: Welcome contributions
- **Feature Requests**: User-driven development
- **Bug Reports**: Rapid issue resolution

**Documentation**

- **Wiki**: Community-maintained guides
- **Examples**: Real-world usage scenarios
- **Tutorials**: Video and written guides
- **Translations**: Multi-language support
