"""WiiM sensor platform.

Provides clean, user-focused sensors with smart filtering based on user preferences.
Only creates sensors that users actually need, with advanced diagnostics optional.
"""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ENABLE_DIAGNOSTIC_ENTITIES,
    CONF_ENABLE_NETWORK_MONITORING,
    DOMAIN,
)
from .data import Speaker
from .entity import WiimEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM sensors from a config entry with smart filtering.

    Only creates sensors that are explicitly enabled by the user to avoid clutter.
    Most sensors are diagnostic and disabled by default.
    """
    speaker: Speaker = hass.data[DOMAIN][config_entry.entry_id]["speaker"]
    entry = hass.data[DOMAIN][config_entry.entry_id]["entry"]

    entities = []

    # Essential sensors (always enabled if any sensors are enabled)
    # Only create multiroom role sensor - it's the most useful for users
    entities.append(WiiMRoleSensor(speaker))

    # Network monitoring sensors (optional)
    if entry.options.get(CONF_ENABLE_NETWORK_MONITORING, False):
        entities.append(WiiMIPSensor(speaker))

    # Advanced diagnostic sensors (optional, mostly for developers/troubleshooting)
    if entry.options.get(CONF_ENABLE_DIAGNOSTIC_ENTITIES, False):
        entities.extend(
            [
                WiiMActivitySensor(speaker),
                WiiMPollingIntervalSensor(speaker),
            ]
        )

    async_add_entities(entities)
    _LOGGER.info("Created %d sensor entities for %s (filtering applied)", len(entities), speaker.name)


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
        self._attr_name = "Multiroom Role"  # Clean name without device duplication

    @property
    def native_value(self) -> str:
        """Return the current multiroom role of the device."""
        role = self.speaker.role.title()
        # Make it more user-friendly
        if role == "Solo":
            return "Not Grouped"
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


class WiiMIPSensor(WiimEntity, SensorEntity):
    """Device IP address sensor for network monitoring.

    Only created when network monitoring is explicitly enabled.
    Useful for network troubleshooting and device identification.
    """

    _attr_icon = "mdi:ip-network"
    _attr_state_class = None  # IP addresses don't have numeric state

    def __init__(self, speaker: Speaker) -> None:
        """Initialize IP address sensor."""
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_ip_address"
        self._attr_name = "IP Address"  # Clean name without device duplication

    @property
    def native_value(self) -> str:
        """Return the current IP address of the device."""
        return self.speaker.ip

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return network diagnostic attributes."""
        return {
            "mac_address": self.speaker.mac or "Unknown",
            "device_uuid": self.speaker.uuid,
            "firmware_version": getattr(self.speaker, "firmware", "Unknown"),
        }


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
        self._attr_name = "Activity Level"  # Clean name without device duplication

    @property
    def native_value(self) -> str | None:
        """Return the current smart polling activity level."""
        if not self.speaker.coordinator.data:
            return None

        smart_polling = self.speaker.coordinator.data.get("smart_polling", {})
        return smart_polling.get("activity_level", "UNKNOWN")

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return smart polling diagnostics for performance monitoring."""
        if not self.speaker.coordinator.data:
            return {}

        smart_polling = self.speaker.coordinator.data.get("smart_polling", {})

        return {
            "polling_interval": smart_polling.get("polling_interval"),
            "position_predicted": smart_polling.get("position_predicted", False),
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
        self._attr_name = "Polling Interval"  # Clean name without device duplication

    @property
    def native_value(self) -> int | None:
        """Return the current polling interval in seconds."""
        if not self.speaker.coordinator.data:
            return None

        smart_polling = self.speaker.coordinator.data.get("smart_polling", {})
        return smart_polling.get("polling_interval")

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return polling optimization diagnostics."""
        return {
            "base_interval": getattr(self.speaker.coordinator, "_base_poll_interval", "Unknown"),
            "smart_polling_enabled": True,
            "coordinator_available": self.speaker.coordinator.last_update_success,
        }
