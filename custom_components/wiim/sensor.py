"""WiiM sensor platform.

Provides clean, user-focused sensors with smart filtering based on user preferences.
Only creates sensors that users actually need, with advanced diagnostics optional.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
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
    hass.data[DOMAIN][config_entry.entry_id]["entry"]

    entities = []

    # ALWAYS CREATE: Role sensor - ESSENTIAL for users to understand multiroom status
    entities.append(WiiMRoleSensor(speaker))

    # Current Input sensor (always useful)
    entities.append(WiiMInputSensor(speaker))

    # Always add diagnostic sensor
    entities.append(WiiMDiagnosticSensor(speaker))

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
        # Only log when role actually changes to reduce log spam
        last_role = getattr(self, "_last_logged_role", None)
        if last_role != role:
            _LOGGER.info(
                "🎯 ROLE SENSOR VALUE CHANGED for %s: %s -> %s",
                self.speaker.name,
                last_role or "unknown",
                role,
            )
            self._last_logged_role = role
        return role

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return group-related information."""
        attrs = {
            "is_group_coordinator": self.speaker.is_group_coordinator,
            "group_members_count": len(self.speaker.group_members),
        }

        # Only log attrs when they change to reduce log spam
        current_attrs = (
            self.speaker.is_group_coordinator,
            len(self.speaker.group_members),
        )
        if not hasattr(self, "_last_logged_attrs") or self._last_logged_attrs != current_attrs:
            _LOGGER.info(
                "🎯 ROLE SENSOR ATTRS CHANGED for %s: is_coordinator=%s, group_count=%s, members=%s",
                self.speaker.name,
                self.speaker.is_group_coordinator,
                len(self.speaker.group_members),
                [m.name for m in self.speaker.group_members],
            )
            self._last_logged_attrs = current_attrs

        if self.speaker.coordinator_speaker:
            attrs["coordinator_name"] = self.speaker.coordinator_speaker.name

        if len(self.speaker.group_members) > 1:
            attrs["group_member_names"] = [member.name for member in self.speaker.group_members]

        return attrs


# -----------------------------------------------------------------------------
# New consolidated diagnostic sensor
# -----------------------------------------------------------------------------


class WiiMDiagnosticSensor(WiimEntity, SensorEntity):
    """Primary diagnostic sensor – state = Wi-Fi RSSI, attributes = rich status."""

    _attr_icon = "mdi:wifi"
    _attr_device_class = None
    _attr_state_class = None
    _attr_native_unit_of_measurement = None
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(self, speaker: Speaker) -> None:  # noqa: D401
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_diagnostic"
        self._attr_name = "Device Status"  # HA will prefix device name automatically

    # Force Home Assistant to treat this as non-numeric regardless of legacy
    # registry values that might still carry a device class or unit.

    @property
    def device_class(self):  # type: ignore[override]
        return None

    @property
    def state_class(self):  # type: ignore[override]
        return None

    @property
    def native_unit_of_measurement(self):  # type: ignore[override]
        return None

    # -------------------------- Helpers --------------------------

    def _status(self) -> dict[str, Any]:
        """Return *status* payload as a plain dict extracted from the PlayerStatus model."""

        if self.speaker.status_model is None:
            return {}

        return self.speaker.status_model.model_dump(exclude_none=True)

    def _device_info(self) -> dict[str, Any]:
        """Return *device_info* payload as a plain dict extracted from the DeviceInfo model."""

        if self.speaker.device_model is None:
            return {}

        return self.speaker.device_model.model_dump(exclude_none=True)

    def _multiroom(self) -> dict[str, Any]:
        return self.speaker.coordinator.data.get("multiroom", {}) if self.speaker.coordinator.data else {}

    # -------------------------- State ----------------------------

    @property  # type: ignore[override]
    def native_value(self) -> str:
        """Return Wi-Fi RSSI in dBm (negative integer)."""
        status = self._status()
        rssi = status.get("wifi_rssi") or status.get("RSSI")

        # If we have a usable RSSI value → show Wi-Fi strength
        if rssi not in (None, "", "unknown", "unknow"):
            try:
                return f"Wi-Fi {int(rssi)} dBm"
            except (TypeError, ValueError):
                pass  # fall through to generic state

        # No RSSI → show basic connectivity status
        # Check for recent command failures for more specific status
        if hasattr(self.speaker.coordinator, "has_recent_command_failures"):
            if self.speaker.coordinator.has_recent_command_failures():
                return "Command Failed"

        return "Online" if self.speaker.available else "Offline"

    # ----------------------- Attributes -------------------------

    @property
    def extra_state_attributes(self) -> dict[str, Any]:  # noqa: D401
        status = self._status()
        info = self._device_info()
        multi = self._multiroom()

        attrs: dict[str, Any] = {
            # Identifiers
            "mac": info.get("mac") or status.get("mac_address"),
            "uuid": info.get("uuid"),
            "project": info.get("project"),
            # Firmware / software
            "firmware": info.get("firmware"),
            "release": info.get("release") or info.get("Release"),
            "mcu_ver": info.get("mcu_ver"),
            "ble_fw_ver": info.get("ble_fw_ver"),
            "dsp_ver": info.get("dsp_ver"),
            # Network
            "ssid": info.get("ssid"),
            "ap_mac": info.get("ap_mac"),
            "ip_address": self.speaker.ip_address,
            "wifi_rssi": status.get("wifi_rssi"),
            "wifi_channel": status.get("wifi_channel"),
            "internet": _to_bool(info.get("internet")),
            "netstat": _to_int(info.get("netstat")),
            # System resources
            "uptime": _to_int(info.get("uptime")),
            "free_ram": _to_int(info.get("free_ram")),
            # Multi-room context
            "group": multi.get("role") or self.speaker.role,
            "master_uuid": info.get("master_uuid") or status.get("master_uuid"),
            "slave_cnt": multi.get("slaves") or multi.get("slave_count"),
            "preset_key": _to_int(info.get("preset_key")),
        }

        # Add command failure diagnostics
        if hasattr(self.speaker.coordinator, "_last_command_failure"):
            if self.speaker.coordinator._last_command_failure is not None:
                import time

                time_since_failure = time.time() - self.speaker.coordinator._last_command_failure
                attrs.update(
                    {
                        "last_command_failure": int(time_since_failure),  # seconds ago
                        "command_failure_count": getattr(self.speaker.coordinator, "_command_failure_count", 0),
                        "has_recent_failures": (
                            self.speaker.coordinator.has_recent_command_failures()
                            if hasattr(self.speaker.coordinator, "has_recent_command_failures")
                            else False
                        ),
                    }
                )

        # Add adaptive polling diagnostics
        polling_data = self.speaker.coordinator.data.get("polling", {}) if self.speaker.coordinator.data else {}
        if polling_data:
            attrs.update(
                {
                    "polling_interval": polling_data.get("interval", 5),
                    "polling_reason": polling_data.get("interval_reason", "unknown"),
                    "fast_polling_active": polling_data.get("fast_polling_active", False),
                    "adaptive_polling": polling_data.get("adaptive_polling", False),
                    "is_playing": polling_data.get("is_playing", False),
                }
            )

        # Prune None values for cleanliness
        return {k: v for k, v in attrs.items() if v is not None}


# -----------------------------------------------------------------------------
# Utility helpers (local – simple, avoids polluting other modules)
# -----------------------------------------------------------------------------


# Converts a value to a boolean if possible, otherwise returns None.
def _to_bool(val: Any) -> bool | None:  # noqa: D401
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    if isinstance(val, int | float):
        return bool(val)
    try:
        return str(val).strip().lower() in {"1", "true", "yes", "on"}
    except Exception:
        return None


# Converts a value to an integer if possible, otherwise returns None.
def _to_int(val: Any) -> int | None:  # noqa: D401
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


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
