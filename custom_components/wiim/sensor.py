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

# from .const import DOMAIN
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

    entities = []

    # ALWAYS CREATE: Role sensor - ESSENTIAL for users to understand multiroom status
    entities.append(WiiMRoleSensor(speaker))

    # Current Input sensor - shows current source (including non-selectable like "Amazon Music")
    # Useful for automations that need to detect streaming service changes
    # Note: Media player source attribute also works, but sensor is simpler for automation triggers
    entities.append(WiiMInputSensor(speaker))

    # Bluetooth Output sensor (shows when audio is being sent to Bluetooth device)
    # Only create if device supports audio output modes
    # Access capabilities from coordinator where they're properly stored
    capabilities = getattr(speaker.coordinator, "_capabilities", {})
    if capabilities:
        supports_audio_output = capabilities.get("supports_audio_output", True)  # Keep original default
        if supports_audio_output:
            entities.append(WiiMBluetoothOutputSensor(speaker))
            _LOGGER.debug("Creating Bluetooth output sensor - device supports audio output")
        else:
            _LOGGER.debug(
                "Skipping Bluetooth output sensor - device does not support audio output (capability=%s)",
                supports_audio_output,
            )
    else:
        if capabilities is None:
            return []

    # Always add diagnostic sensor
    entities.append(WiiMDiagnosticSensor(speaker))

    # Always add firmware version sensor (useful for support/troubleshooting)
    entities.append(WiiMFirmwareSensor(speaker))

    # Audio quality sensors (only if metadata is supported)
    # Check if metadata support has been determined and is not False
    metadata_supported = getattr(speaker.coordinator, "_metadata_supported", None)
    if metadata_supported is not False:
        entities.append(WiiMAudioQualitySensor(speaker))
        entities.append(WiiMSampleRateSensor(speaker))
        entities.append(WiiMBitDepthSensor(speaker))
        entities.append(WiiMBitRateSensor(speaker))

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
        # Get Player object from coordinator
        player = self.coordinator.data.get("player") if self.coordinator.data else None

        attrs = {}

        if player:
            # Use player.role as source of truth
            # Note: group.all_players may be empty even if device has slaves
            is_coordinator = player.is_master
            group_members_count = 0
            member_names = []

            # For now, just track that we're a coordinator
            # group.all_players is for operations, not for counting members
            # TODO: Use player.client.get_device_group_info() to get actual slave list

            attrs = {
                "is_group_coordinator": is_coordinator,
                "group_members_count": group_members_count,
            }

            # Only log attrs when they change to reduce log spam
            current_attrs = (is_coordinator, group_members_count)
            if not hasattr(self, "_last_logged_attrs"):
                self._last_logged_attrs = None
            if self._last_logged_attrs != current_attrs:
                _LOGGER.info(
                    "🎯 ROLE SENSOR ATTRS CHANGED for %s: is_coordinator=%s, group_count=%s, members=%s",
                    self.speaker.name,
                    is_coordinator,
                    group_members_count,
                    member_names,
                )
                self._last_logged_attrs = current_attrs

            # Get coordinator name from group object if slave
            if player.is_slave and player.group and player.group.master:
                master_name = getattr(player.group.master, "name", None)
                if master_name:
                    attrs["coordinator_name"] = master_name

            if group_members_count > 0:
                attrs["group_member_names"] = member_names

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

    def _device_info(self) -> dict[str, Any]:
        """Return *device_info* payload as a plain dict extracted from the DeviceInfo model."""

        if self.speaker.device_model is None:
            return {}

        return self.speaker.device_model.model_dump(exclude_none=True)

    # -------------------------- State ----------------------------

    @property  # type: ignore[override]
    def native_value(self) -> str:
        """Return Wi-Fi RSSI in dBm (negative integer)."""
        # Read directly from Player object (always up-to-date via pywiim)
        if self.coordinator.data:
            player = self.coordinator.data.get("player")
            if player:
                rssi = getattr(player, "wifi_rssi", None)
                if rssi is not None:
                    try:
                        return f"Wi-Fi {int(rssi)} dBm"
                    except (TypeError, ValueError):
                        pass

        # No RSSI → show basic connectivity status
        # Check for recent command failures for more specific status
        if hasattr(self.speaker.coordinator, "has_recent_command_failures"):
            if self.speaker.coordinator.has_recent_command_failures():
                return "Command Failed"

        return "Online" if self.speaker.available else "Offline"

    # ----------------------- Attributes -------------------------

    @property
    def extra_state_attributes(self) -> dict[str, Any]:  # noqa: D401
        info = self._device_info()

        # Get Player from coordinator
        player = self.coordinator.data.get("player") if self.coordinator.data else None

        # Read Player properties directly
        wifi_rssi = getattr(player, "wifi_rssi", None) if player else None

        # Get group info from player.group
        group_role = self.speaker.role
        slave_cnt = None
        # Note: group.all_players may be empty even if device has slaves
        # Just show role from device API

        # Get pywiim library version for diagnostics
        try:
            import pywiim

            pywiim_version = getattr(pywiim, "__version__", "unknown")
        except (ImportError, AttributeError):
            pywiim_version = "unknown"

        attrs: dict[str, Any] = {
            # Identifiers
            "mac": info.get("mac"),
            "uuid": info.get("uuid"),
            "project": info.get("project"),
            # Firmware / software
            "firmware": info.get("firmware"),
            "release": info.get("release") or info.get("Release"),
            "mcu_ver": info.get("mcu_ver"),
            "dsp_ver": info.get("dsp_ver"),
            "pywiim_version": pywiim_version,
            # Network
            "ssid": info.get("ssid"),
            "ap_mac": info.get("ap_mac"),
            "ip_address": self.speaker.ip_address,
            "wifi_rssi": wifi_rssi,
            "internet": _to_bool(info.get("internet")),
            "netstat": _to_int(info.get("netstat")),
            # System resources
            "uptime": _to_int(info.get("uptime")),
            "free_ram": _to_int(info.get("free_ram")),
            # Multi-room context
            "group": group_role,
            "master_uuid": info.get("master_uuid"),
            "slave_cnt": slave_cnt,
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


class WiiMFirmwareSensor(WiimEntity, SensorEntity):
    """Firmware version sensor - always visible for support and troubleshooting."""

    _attr_icon = "mdi:chip"
    _attr_device_class = None
    _attr_state_class = None
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(self, speaker: Speaker) -> None:
        """Initialize firmware sensor."""
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_firmware"
        self._attr_name = "Firmware"

    @property  # type: ignore[override]
    def native_value(self) -> str | None:
        """Return current firmware version."""
        # Primary source: device_model firmware field
        if self.speaker.device_model:
            firmware = getattr(self.speaker.device_model, "firmware", None)
            if firmware and str(firmware).strip() not in {"", "0", "-", "unknown"}:
                return str(firmware)

        if self.speaker.firmware and str(self.speaker.firmware).strip() not in {"", "0", "-", "unknown"}:
            return str(self.speaker.firmware)

        return "Unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Additional firmware-related information."""
        attrs: dict[str, Any] = {}

        if self.speaker.device_model:
            # MCU version (microcontroller firmware)
            if mcu_ver := getattr(self.speaker.device_model, "mcu_ver", None):
                attrs["mcu_version"] = str(mcu_ver)

            # DSP version (digital signal processor firmware)
            if dsp_ver := getattr(self.speaker.device_model, "dsp_ver", None):
                attrs["dsp_version"] = str(dsp_ver)

            # Release/build info
            if release := getattr(self.speaker.device_model, "release", None):
                attrs["release"] = str(release)

            # Update availability info (if present)
            if version_update := getattr(self.speaker.device_model, "version_update", None):
                # VersionUpdate can be "0" (no update) or "1" (update available)
                if str(version_update) == "1":
                    attrs["update_available"] = True
                    if latest := getattr(self.speaker.device_model, "latest_version", None):
                        attrs["latest_version"] = str(latest)

        # Prune None values
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
    except (TypeError, ValueError, OverflowError):
        return None


# ------------------- Input Source Sensor -------------------


class WiiMInputSensor(WiimEntity, SensorEntity):
    """Shows current input/source (AirPlay, Bluetooth, Amazon Music, etc.).

    This sensor shows the CURRENT source, including non-selectable streaming services
    like "Amazon Music", "Spotify", etc. This is useful for automations that need to
    detect when the source changes, regardless of whether it's selectable.

    Note: The media player entity's `source` attribute also provides this information,
    but a sensor is simpler for automation triggers and state-based conditions.
    """

    _attr_icon = "mdi:import"  # generic input symbol
    _attr_has_entity_name = True

    def __init__(self, speaker: Speaker) -> None:
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_current_input"
        self._attr_name = "Current Input"  # Generic label

    @property  # type: ignore[override]
    def native_value(self):
        """Return the current input source (can be selectable or non-selectable)."""
        # Read directly from Player object (always up-to-date via pywiim)
        if self.coordinator.data:
            player = self.coordinator.data.get("player")
            if player:
                return player.source
        return None


# ------------------- Bluetooth Output Sensor -------------------


class WiiMBluetoothOutputSensor(WiimEntity, SensorEntity):
    """Shows Bluetooth output status (whether audio is being sent to Bluetooth device)."""

    _attr_icon = "mdi:bluetooth"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(self, speaker: Speaker) -> None:
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_bluetooth_output"
        self._attr_name = "Bluetooth Output"

    @property  # type: ignore[override]
    def native_value(self) -> str:
        """Return 'on' if Bluetooth output is active, 'off' if not."""
        try:
            # Check if core device communication is working
            if (
                hasattr(self.speaker.coordinator, "_device_info_working")
                and not self.speaker.coordinator._device_info_working
            ):
                # Device communication is failing - return "unavailable" to indicate device issue
                return "unavailable"

            # Read directly from coordinator data
            audio_output = self.coordinator.data.get("audio_output", {}) if self.coordinator.data else {}
            bt_active = audio_output.get("source") == "1"
            return "on" if bt_active else "off"
        except Exception:
            # Return "unknown" if we can't determine the status
            # This prevents the entity from becoming unavailable
            _LOGGER.debug("Could not determine Bluetooth output status for %s", self.speaker.name)
            return "unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        try:
            # Read directly from coordinator data
            audio_output = self.coordinator.data.get("audio_output", {}) if self.coordinator.data else {}
            return {
                "hardware_output_mode": audio_output.get("mode", "Unknown"),
                "audio_cast_active": audio_output.get("cast_active", False),
            }
        except Exception:
            # Return minimal attributes if we can't get the full information
            _LOGGER.debug(
                "Could not get extra state attributes for Bluetooth output sensor on %s",
                self.speaker.name,
            )
            return {
                "hardware_output_mode": "unknown",
                "audio_cast_active": "unknown",
            }


# ------------------- Audio Quality Sensors -------------------


class WiiMAudioQualitySensor(WiimEntity, SensorEntity):
    """Audio quality sensor showing current track's audio specifications."""

    _attr_icon = "mdi:ear-hearing"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(self, speaker: Speaker) -> None:
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_audio_quality"
        self._attr_name = "Audio Quality"

    @property  # type: ignore[override]
    def native_value(self) -> str:
        """Return formatted audio quality string."""
        if not self.speaker.coordinator.data:
            return "Unknown"
        metadata = self.speaker.coordinator.data.get("metadata", {})

        if not metadata:
            return "Unknown"

        sample_rate = metadata.get("sample_rate")
        bit_depth = metadata.get("bit_depth")
        bit_rate = metadata.get("bit_rate")

        # If all values are None/empty, check if we have previous values to persist
        if not any([sample_rate, bit_depth, bit_rate]):
            # Try to get previous values from coordinator to avoid flickering during track changes
            if hasattr(self.speaker.coordinator, "_last_valid_metadata"):
                last_metadata = self.speaker.coordinator._last_valid_metadata
                if last_metadata:
                    sample_rate = last_metadata.get("sample_rate")
                    bit_depth = last_metadata.get("bit_depth")
                    bit_rate = last_metadata.get("bit_rate")

        if all([sample_rate, bit_depth, bit_rate]):
            return f"{sample_rate}Hz / {bit_depth}bit / {bit_rate}kbps"
        elif sample_rate and bit_depth:
            return f"{sample_rate}Hz / {bit_depth}bit"
        elif sample_rate:
            return f"{sample_rate}Hz"
        return "Unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed audio quality attributes."""
        metadata = self.speaker.coordinator.data.get("metadata", {})
        if not metadata:
            return {}

        attrs = {}
        if sample_rate := metadata.get("sample_rate"):
            attrs["sample_rate"] = sample_rate
        if bit_depth := metadata.get("bit_depth"):
            attrs["bit_depth"] = bit_depth
        if bit_rate := metadata.get("bit_rate"):
            attrs["bit_rate"] = bit_rate
        if codec := metadata.get("codec"):
            attrs["codec"] = codec

        return attrs


class WiiMSampleRateSensor(WiimEntity, SensorEntity):
    """Sample rate sensor showing current track's sample rate."""

    _attr_icon = "mdi:sine-wave"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "Hz"

    def __init__(self, speaker: Speaker) -> None:
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_sample_rate"
        self._attr_name = "Sample Rate"

    @property  # type: ignore[override]
    def native_value(self) -> int | None:
        """Return current track's sample rate in Hz."""
        if not self.speaker.coordinator.data:
            return None
        metadata = self.speaker.coordinator.data.get("metadata", {})
        sample_rate = metadata.get("sample_rate")

        # If no current value, try to get previous valid value to avoid flickering
        if sample_rate is None and hasattr(self.speaker.coordinator, "_last_valid_metadata"):
            last_metadata = self.speaker.coordinator._last_valid_metadata
            if last_metadata:
                sample_rate = last_metadata.get("sample_rate")

        return sample_rate


class WiiMBitDepthSensor(WiimEntity, SensorEntity):
    """Bit depth sensor showing current track's bit depth."""

    _attr_icon = "mdi:database"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "bit"

    def __init__(self, speaker: Speaker) -> None:
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_bit_depth"
        self._attr_name = "Bit Depth"

    @property  # type: ignore[override]
    def native_value(self) -> int | None:
        """Return current track's bit depth."""
        if not self.speaker.coordinator.data:
            return None
        metadata = self.speaker.coordinator.data.get("metadata", {})
        bit_depth = metadata.get("bit_depth")

        # If no current value, try to get previous valid value to avoid flickering
        if bit_depth is None and hasattr(self.speaker.coordinator, "_last_valid_metadata"):
            last_metadata = self.speaker.coordinator._last_valid_metadata
            if last_metadata:
                bit_depth = last_metadata.get("bit_depth")

        return bit_depth


class WiiMBitRateSensor(WiimEntity, SensorEntity):
    """Bit rate sensor showing current track's bit rate."""

    _attr_icon = "mdi:transmission-tower"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "kbps"

    def __init__(self, speaker: Speaker) -> None:
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_bit_rate"
        self._attr_name = "Bit Rate"

    @property  # type: ignore[override]
    def native_value(self) -> int | None:
        """Return current track's bit rate in kbps."""
        if not self.speaker.coordinator.data:
            return None
        metadata = self.speaker.coordinator.data.get("metadata", {})
        bit_rate = metadata.get("bit_rate")

        # If no current value, try to get previous valid value to avoid flickering
        if bit_rate is None and hasattr(self.speaker.coordinator, "_last_valid_metadata"):
            last_metadata = self.speaker.coordinator._last_valid_metadata
            if last_metadata:
                bit_rate = last_metadata.get("bit_rate")

        return bit_rate
