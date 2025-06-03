# WiiM Integration – Implementation Guide

> **Goal**: Step-by-step guide to implement our Sonos-inspired WiiM integration from scratch.

---

## 🎯 **Implementation Overview**

We're building this integration in **5 focused phases**, each delivering working functionality:

| Phase | Goal              | Deliverable                          | Duration |
| ----- | ----------------- | ------------------------------------ | -------- |
| **1** | Core Foundation   | `WiimData` + `Speaker` + basic setup | 1-2 days |
| **2** | Entity Framework  | `WiimEntity` + event system          | 1 day    |
| **3** | Media Player      | Clean, thin media player entity      | 1 day    |
| **4** | Platform Entities | Sensor, Button, etc.                 | 1 day    |
| **5** | Services & Polish | Group services, testing, docs        | 1-2 days |

---

## 🚀 **Phase 1: Core Foundation**

### **Step 1.1: Create Core Data Layer**

**File**: `custom_components/wiim/data.py`

```python
"""Core data layer for WiiM integration."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.components.media_player import MediaPlayerState

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import WiiMCoordinator

_LOGGER = logging.getLogger(__name__)

@dataclass
class WiimData:
    """Central registry for all WiiM speakers (like SonosData)."""

    hass: HomeAssistant
    speakers: dict[str, Speaker] = field(default_factory=dict)
    entity_id_mappings: dict[str, Speaker] = field(default_factory=dict)
    discovery_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def get_speaker_by_ip(self, ip: str) -> Speaker | None:
        """Find speaker by IP address."""
        return next((s for s in self.speakers.values() if s.ip == ip), None)

    def get_speaker_by_entity_id(self, entity_id: str) -> Speaker | None:
        """Find speaker by entity ID."""
        return self.entity_id_mappings.get(entity_id)

class Speaker:
    """Rich speaker object with business logic (like SonosSpeaker)."""

    def __init__(self, hass: HomeAssistant, uuid: str, coordinator: WiiMCoordinator):
        self.hass = hass
        self.uuid = uuid
        self.coordinator = coordinator

        # Device properties
        self.name: str = ""
        self.model: str = ""
        self.firmware: str | None = None
        self.ip: str = ""
        self.mac: str = ""

        # Group state
        self.role: str = "solo"  # solo/master/slave
        self.group_members: list[Speaker] = []
        self.coordinator_speaker: Speaker | None = None

        # HA integration
        self.device_info: DeviceInfo | None = None
        self._available: bool = True

    async def async_setup(self, entry: ConfigEntry) -> None:
        """Complete speaker setup and HA device registration."""
        await self._populate_device_info()
        await self._register_ha_device(entry)

    async def _populate_device_info(self) -> None:
        """Extract device info from coordinator data."""
        status = self.coordinator.data.get("status", {}) if self.coordinator.data else {}

        self.ip = self.coordinator.client.host
        self.mac = (status.get("MAC") or "").lower().replace(":", "")
        self.name = status.get("DeviceName") or f"WiiM {self.ip}"
        self.model = status.get("project") or "WiiM Speaker"
        self.firmware = status.get("firmware")

        # Group info
        multiroom = self.coordinator.data.get("multiroom", {}) if self.coordinator.data else {}
        self.role = multiroom.get("role", "solo")

    async def _register_ha_device(self, entry: ConfigEntry) -> None:
        """Register device in HA registry."""
        dev_reg = dr.async_get(self.hass)
        identifiers = {(DOMAIN, self.uuid)}

        device_entry = dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers=identifiers,
            manufacturer="WiiM",
            name=self.name,
            model=self.model,
            sw_version=self.firmware,
        )

        # Store DeviceInfo for entities
        self.device_info = DeviceInfo(
            identifiers=identifiers,
            manufacturer="WiiM",
            name=self.name,
            model=self.model,
            sw_version=self.firmware,
        )

    def async_write_entity_states(self) -> None:
        """Notify all entities of state changes (event-driven)."""
        async_dispatcher_send(self.hass, f"wiim_state_updated_{self.uuid}")

    def update_from_coordinator_data(self, data: dict) -> None:
        """Update speaker state from coordinator data."""
        status = data.get("status", {})
        multiroom = data.get("multiroom", {})

        # Update basic properties
        if device_name := status.get("DeviceName"):
            self.name = device_name

        # Update group state
        old_role = self.role
        self.role = multiroom.get("role", "solo")

        # If role changed, notify entities
        if old_role != self.role:
            self.async_write_entity_states()

    @property
    def available(self) -> bool:
        """Return if speaker is available."""
        return self._available and self.coordinator.last_update_success

    def get_playback_state(self) -> MediaPlayerState:
        """Calculate current playback state from coordinator data."""
        if not self.coordinator.data:
            return MediaPlayerState.OFF

        status = self.coordinator.data.get("status", {})
        state = status.get("state", "stop").lower()

        if state == "play":
            return MediaPlayerState.PLAYING
        elif state == "pause":
            return MediaPlayerState.PAUSED
        elif state == "stop":
            return MediaPlayerState.IDLE
        else:
            return MediaPlayerState.OFF

# Helper functions
def get_wiim_data(hass: HomeAssistant) -> WiimData:
    """Get the WiimData instance."""
    return hass.data[DOMAIN]["data"]

def get_or_create_speaker(hass: HomeAssistant, uuid: str, coordinator: WiiMCoordinator) -> Speaker:
    """Get existing speaker or create new one."""
    data = get_wiim_data(hass)
    if uuid not in data.speakers:
        data.speakers[uuid] = Speaker(hass, uuid, coordinator)
    return data.speakers[uuid]
```

### **Step 1.2: Update Integration Setup**

**File**: `custom_components/wiim/__init__.py`

```python
"""WiiM Media Player integration for Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WiiMClient
from .const import CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL, DOMAIN
from .coordinator import WiiMCoordinator
from .data import WiimData, get_or_create_speaker

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.MEDIA_PLAYER,
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.BINARY_SENSOR,
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WiiM from a config entry."""

    # Create central data registry
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN]["data"] = WiimData(hass)

    # Create client and coordinator
    session = async_get_clientsession(hass)
    client = WiiMClient(
        host=entry.data["host"],
        port=entry.data.get("port", 443),
        timeout=entry.data.get("timeout", 10),
        session=session,
    )

    coordinator = WiiMCoordinator(
        hass,
        client,
        poll_interval=entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
    )

    # Initial data fetch
    await coordinator.async_config_entry_first_refresh()

    # Create/update speaker
    status_dict = coordinator.data.get("status", {}) if coordinator.data else {}
    device_uuid = status_dict.get("uuid") or f"ip_{entry.data['host'].replace('.', '_')}"

    speaker = get_or_create_speaker(hass, device_uuid, coordinator)
    await speaker.async_setup(entry)

    # Store coordinator reference
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
        "speaker": speaker,
    }

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id, {})
    return unload_ok
```

### **Step 1.3: Update Coordinator**

**File**: `custom_components/wiim/coordinator.py` (modify existing)

```python
# Add to existing coordinator after the _async_update_data method:

async def _async_update_data(self) -> dict:
    """Fetch data from API endpoint."""
    try:
        # Existing API calls...
        data = await self.client.get_all_status()

        # NEW: Update speaker if it exists
        from .data import get_wiim_data
        wiim_data = get_wiim_data(self.hass)

        # Find speaker for this coordinator
        speaker = None
        for spk in wiim_data.speakers.values():
            if spk.coordinator is self:
                speaker = spk
                break

        if speaker:
            speaker.update_from_coordinator_data(data)

        return data

    except Exception as err:
        _LOGGER.error("Error fetching data: %s", err)
        raise
```

---

## 🎯 **Phase 2: Entity Framework**

### **Step 2.1: Create WiimEntity Base Class**

**File**: `custom_components/wiim/entity.py`

```python
"""Base entity class for WiiM integration."""

from __future__ import annotations

from abc import abstractmethod
import logging

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .data import Speaker, get_wiim_data

_LOGGER = logging.getLogger(__name__)

class WiimEntity(Entity):
    """Base class for all WiiM entities (like SonosEntity)."""

    _attr_should_poll = False  # Event-driven, no polling
    _attr_has_entity_name = True

    def __init__(self, speaker: Speaker) -> None:
        """Initialize with speaker reference."""
        self.speaker = speaker

    async def async_added_to_hass(self) -> None:
        """Set up event listening and entity registration."""
        # Register in central mapping
        data = get_wiim_data(self.hass)
        data.entity_id_mappings[self.entity_id] = self.speaker

        # Listen for speaker state changes
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"wiim_state_updated_{self.speaker.uuid}",
                self.async_write_ha_state,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Clean up entity registration."""
        data = get_wiim_data(self.hass)
        data.entity_id_mappings.pop(self.entity_id, None)

    @property
    def device_info(self) -> DeviceInfo:
        """Delegate to speaker (single source of truth)."""
        return self.speaker.device_info

    @property
    def available(self) -> bool:
        """Delegate to speaker."""
        return self.speaker.available
```

---

## 🎯 **Phase 3: Media Player**

### **Step 3.1: Create Clean Media Player**

**File**: `custom_components/wiim/platforms/media_player.py`

```python
"""WiiM media player platform."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import DOMAIN
from ..entity import WiimEntity
from ..data import Speaker

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM media player from a config entry."""
    speaker: Speaker = hass.data[DOMAIN][config_entry.entry_id]["speaker"]
    entity = WiiMMediaPlayer(speaker)
    async_add_entities([entity])

class WiiMMediaPlayer(WiimEntity, MediaPlayerEntity):
    """WiiM media player - thin wrapper around Speaker."""

    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.GROUPING
    )

    def __init__(self, speaker: Speaker) -> None:
        """Initialize the media player."""
        super().__init__(speaker)
        self._attr_unique_id = speaker.uuid
        self._attr_name = speaker.name

    # State properties (delegate to speaker)
    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the device."""
        return self.speaker.get_playback_state()

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        if not self.speaker.coordinator.data:
            return None
        status = self.speaker.coordinator.data.get("status", {})
        volume = status.get("vol")
        return int(volume) / 100 if volume is not None else None

    @property
    def is_volume_muted(self) -> bool | None:
        """Boolean if volume is currently muted."""
        if not self.speaker.coordinator.data:
            return None
        status = self.speaker.coordinator.data.get("status", {})
        return status.get("mute") == "1"

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        if not self.speaker.coordinator.data:
            return None
        status = self.speaker.coordinator.data.get("status", {})
        return status.get("Title")

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media."""
        if not self.speaker.coordinator.data:
            return None
        status = self.speaker.coordinator.data.get("status", {})
        return status.get("Artist")

    # Control methods (delegate to speaker coordinator)
    async def async_play(self) -> None:
        """Send play command."""
        await self.speaker.coordinator.client.play()
        await self.speaker.coordinator.async_request_refresh()

    async def async_pause(self) -> None:
        """Send pause command."""
        await self.speaker.coordinator.client.pause()
        await self.speaker.coordinator.async_request_refresh()

    async def async_stop(self) -> None:
        """Send stop command."""
        await self.speaker.coordinator.client.stop()
        await self.speaker.coordinator.async_request_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        vol_int = int(volume * 100)
        await self.speaker.coordinator.client.set_volume(vol_int)
        await self.speaker.coordinator.async_request_refresh()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        await self.speaker.coordinator.client.set_mute(mute)
        await self.speaker.coordinator.async_request_refresh()

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self.speaker.coordinator.client.next_track()
        await self.speaker.coordinator.async_request_refresh()

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self.speaker.coordinator.client.previous_track()
        await self.speaker.coordinator.async_request_refresh()
```

---

## 🎯 **Phase 4: Platform Entities**

### **Step 4.1: Create Sensor Platform**

**File**: `custom_components/wiim/platforms/sensor.py`

```python
"""WiiM sensor platform."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import DOMAIN
from ..entity import WiimEntity
from ..data import Speaker

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM sensors from a config entry."""
    speaker: Speaker = hass.data[DOMAIN][config_entry.entry_id]["speaker"]

    entities = [
        WiiMIPSensor(speaker),
        WiiMRoleSensor(speaker),
    ]
    async_add_entities(entities)

class WiiMIPSensor(WiimEntity, SensorEntity):
    """IP address sensor."""

    _attr_icon = "mdi:ip-network"

    def __init__(self, speaker: Speaker) -> None:
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_ip"
        self._attr_name = f"{speaker.name} IP Address"

    @property
    def native_value(self) -> str:
        """Return the IP address."""
        return self.speaker.ip

class WiiMRoleSensor(WiimEntity, SensorEntity):
    """Group role sensor."""

    _attr_icon = "mdi:account-group"

    def __init__(self, speaker: Speaker) -> None:
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_role"
        self._attr_name = f"{speaker.name} Group Role"

    @property
    def native_value(self) -> str:
        """Return the group role."""
        return self.speaker.role.title()
```

### **Step 4.2: Create Button Platform**

**File**: `custom_components/wiim/platforms/button.py`

```python
"""WiiM button platform."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import DOMAIN
from ..entity import WiimEntity
from ..data import Speaker

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM buttons from a config entry."""
    speaker: Speaker = hass.data[DOMAIN][config_entry.entry_id]["speaker"]

    entities = [
        WiiMRebootButton(speaker),
        WiiMSyncTimeButton(speaker),
    ]
    async_add_entities(entities)

class WiiMRebootButton(WiimEntity, ButtonEntity):
    """Reboot device button."""

    _attr_icon = "mdi:restart"

    def __init__(self, speaker: Speaker) -> None:
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_reboot"
        self._attr_name = f"{speaker.name} Reboot"

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.speaker.coordinator.client.reboot()

class WiiMSyncTimeButton(WiimEntity, ButtonEntity):
    """Sync time button."""

    _attr_icon = "mdi:clock-sync"

    def __init__(self, speaker: Speaker) -> None:
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_sync_time"
        self._attr_name = f"{speaker.name} Sync Time"

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.speaker.coordinator.client.sync_time()
```

---

## 🎯 **Phase 5: Services & Polish**

### **Step 5.1: Create Group Services**

**File**: `custom_components/wiim/services/group_services.py`

```python
"""Group management services."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er

from ..const import DOMAIN
from ..data import get_wiim_data, Speaker

_LOGGER = logging.getLogger(__name__)

class GroupServices:
    """Handle group-related services."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def async_join_speakers(self, call: ServiceCall) -> None:
        """Join speakers into a group."""
        entity_ids = call.data.get("entity_id", [])
        if not entity_ids:
            return

        # Get speakers from entity IDs
        data = get_wiim_data(self.hass)
        speakers = []

        for entity_id in entity_ids:
            if speaker := data.get_speaker_by_entity_id(entity_id):
                speakers.append(speaker)

        if len(speakers) < 2:
            _LOGGER.warning("Need at least 2 speakers to create a group")
            return

        # First speaker becomes master
        master = speakers[0]
        slaves = speakers[1:]

        await master.async_join_group(slaves)

    async def async_unjoin_speaker(self, call: ServiceCall) -> None:
        """Remove speaker from group."""
        entity_ids = call.data.get("entity_id", [])

        data = get_wiim_data(self.hass)
        for entity_id in entity_ids:
            if speaker := data.get_speaker_by_entity_id(entity_id):
                await speaker.async_leave_group()
```

### **Step 5.2: Register Services**

**File**: `custom_components/wiim/__init__.py` (add to async_setup_entry)

```python
# Add after platform setup:

# Register services
from .services.group_services import GroupServices
group_services = GroupServices(hass)

hass.services.async_register(
    DOMAIN,
    "join_speakers",
    group_services.async_join_speakers,
    schema=vol.Schema({
        vol.Required("entity_id"): cv.entity_ids,
    }),
)

hass.services.async_register(
    DOMAIN,
    "unjoin_speaker",
    group_services.async_unjoin_speaker,
    schema=vol.Schema({
        vol.Required("entity_id"): cv.entity_ids,
    }),
)
```

---

## ✅ **Testing & Validation**

### **Step 6.1: Basic Testing**

```bash
# Test integration loads
cd wiim
python -m pytest tests/test_init.py -v

# Test speaker creation
python -m pytest tests/test_speaker.py -v

# Test entity framework
python -m pytest tests/test_entity.py -v
```

### **Step 6.2: Integration Testing**

1. **Load in Home Assistant**

   - Copy to `custom_components/wiim/`
   - Restart HA
   - Add integration via UI

2. **Verify Entities Created**

   - Media player entity
   - IP and Role sensors
   - Reboot and Sync Time buttons

3. **Test Event System**
   - Change speaker state
   - Verify entities update automatically

---

## 🎊 **Success Criteria**

After completing all phases, you should have:

✅ **Clean Architecture**

- `WiimData` central registry
- Rich `Speaker` business objects
- Thin `WiimEntity` base class
- Event-driven communication

✅ **Working Entities**

- Media player (~200 LOC)
- Sensors (IP, Role)
- Buttons (Reboot, Sync Time)

✅ **Group Services**

- Join speakers service
- Unjoin speaker service

✅ **Performance**

- Event-driven updates (no polling entities)
- Smart polling in coordinator
- O(1) entity lookups

✅ **Maintainability**

- Small, focused files
- Clear separation of concerns
- Comprehensive documentation

This implementation provides a **solid foundation** that can be extended with additional platforms, services, and features while maintaining clean architecture throughout.
