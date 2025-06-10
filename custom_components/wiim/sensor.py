"""WiiM sensor platform.

Provides clean, user-focused sensors with smart filtering based on user preferences.
Only creates sensors that users actually need, with advanced diagnostics optional.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ENABLE_DIAGNOSTIC_ENTITIES,
    DOMAIN,
    DSP_VERSION_KEY,
    FIRMWARE_DATE_KEY,
    FIRMWARE_KEY,
    HARDWARE_KEY,
    MCU_VERSION_KEY,
    PRESET_SLOTS_KEY,
    PROJECT_KEY,
    WMRM_VERSION_KEY,
)
from .data import Speaker, get_speaker_from_config_entry
from .entity import WiimEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM sensor entities.

    CRITICAL: Role sensor is ALWAYS created - essential for multiroom understanding.
    Diagnostic sensors only created when user enables them.
    """
    speaker = get_speaker_from_config_entry(hass, config_entry)
    entry = hass.data[DOMAIN][config_entry.entry_id]["entry"]

    entities = []

    # ALWAYS CREATE: Role sensor - ESSENTIAL for users to understand multiroom status
    entities.append(WiiMRoleSensor(speaker))

    # Current Input sensor (always useful)
    entities.append(WiiMInputSensor(speaker))

    # Only add diagnostic sensors if the option is enabled
    if entry.options.get("enable_diagnostic_entities", False):
        diag_info_defs = [
            (FIRMWARE_KEY, "Firmware Version", "mdi:chip", None, False),
            (PRESET_SLOTS_KEY, "Preset Slots", "mdi:numeric", "slots", False),
            (WMRM_VERSION_KEY, "WMRM Version", "mdi:radio-tower", None, False),
            (FIRMWARE_DATE_KEY, "Firmware Build Date", "mdi:calendar-clock", None, False),
            (HARDWARE_KEY, "Hardware", "mdi:memory", None, False),
            (PROJECT_KEY, "Project", "mdi:cube", None, False),
            (MCU_VERSION_KEY, "MCU Version", "mdi:chip", None, False),
            (DSP_VERSION_KEY, "DSP Version", "mdi:chip", None, False),
        ]
        for key, label, icon, unit, default_on in diag_info_defs:
            entities.append(
                WiiMDeviceInfoSensor(
                    speaker,
                    key=key,
                    label=label,
                    icon=icon,
                    unit=unit,
                    default_enabled=True,
                )
            )
        entities.extend([
            WiiMActivitySensor(speaker),
            WiiMPollingIntervalSensor(speaker),
            WiiMPerformanceSensor(speaker),
        ])

    async_add_entities(entities)
    _LOGGER.info(
        "Created %d sensor entities for %s (role sensor always included)",
        len(entities),
        speaker.name,
    )


class WiiMRoleSensor(WiimEntity, SensorEntity):
    """Device role sensor for multiroom group monitoring.

    This is the most useful sensor for users as it shows multiroom status clearly.
    Always created when sensor platform is enabled.
    """

    _attr_icon = "mdi:account-group"
    _attr_state_class = None  # Roles are categorical, not numeric

    def __init__(self, speaker: Speaker) -> None:
        """Initialize multiroom role sensor."""
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_multiroom_role"
        # Use None so entity_id is generated from the cleaned device name
        self._attr_name = None

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return f"{self.speaker.name} Multiroom Role"  # Display name includes description

    @property
    def native_value(self) -> str:
        """Return the current multiroom role of the device."""
        role = self.speaker.role.title()
        # Return the role directly - Solo/Master/Slave is clear
        return role

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return group-related information."""
        attrs = {
            "is_group_coordinator": self.speaker.is_group_coordinator,
            "group_members_count": len(self.speaker.group_members),
        }

        if self.speaker.coordinator_speaker:
            attrs["coordinator_name"] = self.speaker.coordinator_speaker.name

        if len(self.speaker.group_members) > 1:
            attrs["group_member_names"] = [member.name for member in self.speaker.group_members]

        return attrs


class WiiMActivitySensor(WiimEntity, SensorEntity):
    """Smart polling activity level sensor.

    Advanced diagnostic sensor only shown when diagnostic entities are enabled.
    Useful for developers and advanced troubleshooting.
    """

    _attr_icon = "mdi:activity"
    _attr_state_class = None  # Activity levels are categorical

    def __init__(self, speaker: Speaker) -> None:
        """Initialize activity level sensor."""
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_activity_level"
        self._attr_name = "Activity Level"  # Generic label; HA will prefix device name
        self._attr_has_entity_name = True

    @property
    def native_value(self) -> str | None:
        """Return the current defensive polling state."""
        if not self.speaker.coordinator.data:
            return None

        polling_info = self.speaker.coordinator.data.get("polling", {})
        is_playing = polling_info.get("is_playing", False)
        return "PLAYING" if is_playing else "IDLE"

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return defensive polling diagnostics for performance monitoring."""
        if not self.speaker.coordinator.data:
            return {}

        polling_info = self.speaker.coordinator.data.get("polling", {})
        api_capabilities = polling_info.get("api_capabilities", {})

        return {
            "polling_interval": polling_info.get("interval"),
            "playing_interval": getattr(self.speaker.coordinator, "_playing_interval", 1),
            "idle_interval": getattr(self.speaker.coordinator, "_idle_interval", 5),
            "statusex_supported": api_capabilities.get("statusex_supported"),
            "metadata_supported": api_capabilities.get("metadata_supported"),
            "eq_supported": api_capabilities.get("eq_supported"),
            "coordinator_ip": self.speaker.coordinator.client.host,
        }


class WiiMPollingIntervalSensor(WiimEntity, SensorEntity):
    """Current polling interval sensor.

    Advanced diagnostic sensor only shown when diagnostic entities are enabled.
    Shows current adaptive polling interval for performance optimization.
    """

    _attr_icon = "mdi:timer"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "s"

    def __init__(self, speaker: Speaker) -> None:
        """Initialize polling interval sensor."""
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_polling_interval"
        self._attr_name = "Polling Interval"  # Generic label
        self._attr_has_entity_name = True

    @property
    def native_value(self) -> int | None:
        """Return the current polling interval in seconds."""
        if not self.speaker.coordinator.data:
            return None

        polling_info = self.speaker.coordinator.data.get("polling", {})
        return polling_info.get("interval")

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return defensive polling configuration."""
        return {
            "playing_rate": getattr(self.speaker.coordinator, "_playing_interval", 1),
            "idle_rate": getattr(self.speaker.coordinator, "_idle_interval", 5),
            "defensive_polling_enabled": True,
            "coordinator_available": self.speaker.coordinator.last_update_success,
        }


class WiiMPerformanceSensor(WiimEntity, SensorEntity):
    """Sensor providing coordinator performance diagnostics."""

    _attr_icon = "mdi:speedometer"
    _attr_native_unit_of_measurement = "ms"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, speaker: Speaker) -> None:
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_performance"
        self._attr_name = "Update Latency"  # HA will prefix device name automatically
        self._attr_has_entity_name = True

    @property
    def native_value(self) -> float | None:  # type: ignore[override]
        """Return the last coordinator update duration in milliseconds."""
        return self.speaker.coordinator._last_response_time  # noqa: SLF001 – intentional private access

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed performance attributes."""
        coord = self.speaker.coordinator
        return {
            "api_response_time_ms": coord._last_response_time,  # noqa: SLF001
            "consecutive_failures": getattr(coord, "_consecutive_failures", 0),
            "update_frequency": coord.update_interval.total_seconds() if coord.update_interval else None,
            "endpoints_working": {
                "player_status": getattr(coord, "_player_status_working", None),
                "device_info": getattr(coord, "_device_info_working", None),
                "multiroom": getattr(coord, "_multiroom_working", None),
            },
        }


class WiiMDeviceInfoSensor(WiimEntity, SensorEntity):
    """Generic sensor for a single key under coordinator.data['device_info']."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        speaker: Speaker,
        *,
        key: str,
        label: str,
        icon: str | None = None,
        unit: str | None = None,
        default_enabled: bool = True,
    ) -> None:
        super().__init__(speaker)
        self._key = key
        self._attr_icon = icon
        self._attr_name = label  # Generic label; HA will prepend device name automatically
        self._attr_native_unit_of_measurement = unit
        self._attr_unique_id = f"{speaker.uuid}_{key}"
        self._attr_has_entity_name = True
        if not default_enabled:
            self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self):  # type: ignore[override]
        if not self.speaker.coordinator.data:
            return None
        return self.speaker.coordinator.data.get("device_info", {}).get(self._key)


# ------------------- Input Source Sensor -------------------

class WiiMInputSensor(WiimEntity, SensorEntity):
    """Shows current input/source (AirPlay, Bluetooth, etc.)."""

    _attr_icon = "mdi:import"  # generic input symbol

    def __init__(self, speaker: Speaker) -> None:
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_current_input"
        self._attr_name = "Current Input"  # Generic label
        self._attr_has_entity_name = True

    @property  # type: ignore[override]
    def native_value(self):
        return self.speaker.get_current_source()
