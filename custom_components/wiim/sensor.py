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
from .coordinator import WiiMCoordinator
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
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    entities = []

    # ALWAYS CREATE: Role sensor - ESSENTIAL for users to understand multiroom status
    entities.append(WiiMRoleSensor(coordinator, config_entry))

    # Current Input sensor - shows current source (including non-selectable like "Amazon Music")
    # Useful for automations that need to detect streaming service changes
    # Note: Media player source attribute also works, but sensor is simpler for automation triggers
    entities.append(WiiMInputSensor(coordinator, config_entry))

    # Bluetooth Output sensor (shows when audio is being sent to Bluetooth device)
    # Check if device supports audio output mode control using pywiim's capability property
    if coordinator.player.supports_audio_output:
        entities.append(WiiMBluetoothOutputSensor(coordinator, config_entry))
        _LOGGER.debug("Creating Bluetooth output sensor - device supports audio output")
    else:
        _LOGGER.debug("Skipping Bluetooth output sensor - device does not support audio output")

    # Always add diagnostic sensor
    entities.append(WiiMDiagnosticSensor(coordinator, config_entry))

    # Always add firmware version sensor (useful for support/troubleshooting)
    entities.append(WiiMFirmwareSensor(coordinator, config_entry))

    # Audio quality sensors (only if metadata is supported)
    # Check if metadata support has been determined and is not False
    metadata_supported = getattr(coordinator, "_metadata_supported", None)
    if metadata_supported is not False:
        entities.append(WiiMAudioQualitySensor(coordinator, config_entry))
        entities.append(WiiMSampleRateSensor(coordinator, config_entry))
        entities.append(WiiMBitDepthSensor(coordinator, config_entry))
        entities.append(WiiMBitRateSensor(coordinator, config_entry))

    async_add_entities(entities)
    device_name = coordinator.player.name or config_entry.title or "WiiM Speaker"
    _LOGGER.info(
        "Created %d sensor entities for %s (role sensor always included)",
        len(entities),
        device_name,
    )


class WiiMRoleSensor(WiimEntity, SensorEntity):
    """Device role sensor for multiroom group monitoring.

    This is the most useful sensor for users as it shows multiroom status clearly.
    Always created when sensor platform is enabled.
    """

    _attr_icon = "mdi:account-group"
    _attr_state_class = None  # Roles are categorical, not numeric

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize multiroom role sensor."""
        super().__init__(coordinator, config_entry)
        uuid = config_entry.unique_id or coordinator.player.host
        self._attr_unique_id = f"{uuid}_multiroom_role"
        # Use None so entity_id is generated from the cleaned device name
        self._attr_name = None

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        device_name = self.player.name or self._config_entry.title or "WiiM Speaker"
        return f"{device_name} Multiroom Role"  # Display name includes description

    @property
    def native_value(self) -> str:
        """Return the current multiroom role of the device."""
        if not self.available or not self.player:
            return "Unknown"
        role = self.player.role
        if role is None:
            return "Unknown"
        return role.title()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return group-related information."""
        player = self.coordinator.player

        attrs = {
            "is_group_coordinator": player.is_master,
        }

        # Get coordinator name from group object if slave
        if player.is_slave and player.group and player.group.master:
            attrs["coordinator_name"] = player.group.master.name

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

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:  # noqa: D401
        super().__init__(coordinator, config_entry)
        uuid = config_entry.unique_id or coordinator.player.host
        self._attr_unique_id = f"{uuid}_diagnostic"
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
        player = self.coordinator.player
        if not player.device_info:
            return {}

        # For diagnostics we want the raw-ish API keys (aliases) like "MAC", "Release",
        # and also any extra fields that were preserved by the model.
        return player.device_info.model_dump(by_alias=True, exclude_none=True)

    # -------------------------- State ----------------------------

    @property  # type: ignore[override]
    def native_value(self) -> str:
        """Return Wi-Fi RSSI in dBm (negative integer)."""
        # Read directly from Player object (pywiim manages state)
        player = self.coordinator.player
        if player.wifi_rssi is not None:
            return f"Wi-Fi {player.wifi_rssi} dBm"

        # No RSSI → show basic connectivity status
        return "Online" if self.coordinator.last_update_success else "Offline"

    # ----------------------- Attributes -------------------------

    @property
    def extra_state_attributes(self) -> dict[str, Any]:  # noqa: D401
        info = self._device_info()
        player = self.coordinator.player

        # Get pywiim library version for diagnostics
        import pywiim

        pywiim_version = pywiim.__version__

        attrs: dict[str, Any] = {
            # Identifiers
            "mac": getattr(player, "mac_address", None) or info.get("mac") or info.get("MAC"),
            "uuid": getattr(player, "uuid", None) or info.get("uuid") or info.get("UUID"),
            "model": getattr(player, "model", None) or info.get("model") or info.get("project"),
            # Firmware / software
            "firmware": getattr(player, "firmware", None) or info.get("firmware"),
            "release": info.get("release_date") or info.get("Release"),
            "mcu_ver": info.get("mcu_ver"),
            "dsp_ver": info.get("dsp_ver"),
            "pywiim_version": pywiim_version,
            # Network
            "ssid": info.get("ssid"),
            "ap_mac": info.get("AP_MAC") or info.get("ap_mac"),
            "ip_address": player.host,
            "wifi_rssi": player.wifi_rssi,
            "internet": _to_bool(info.get("internet")),
            "netstat": _to_int(info.get("netstat")),
            # System resources
            "uptime": _to_int(info.get("uptime")),
            "free_ram": _to_int(info.get("free_ram")),
            # Multi-room context
            "group": player.role,
            "master_uuid": info.get("master_uuid"),
            "preset_key": _to_int(info.get("preset_key")),
            # Firmware update state (pywiim Player properties)
            "firmware_update_available": getattr(player, "firmware_update_available", None),
            "latest_firmware_version": getattr(player, "latest_firmware_version", None),
            "supports_firmware_install": getattr(player, "supports_firmware_install", None),
        }

        # Add adaptive polling diagnostics
        if self.coordinator.update_interval:
            polling_interval = self.coordinator.update_interval.total_seconds()
            attrs.update(
                {
                    "polling_interval": polling_interval,
                    "is_playing": player.is_playing,  # pywiim v2.1.37+ provides bool directly
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

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize firmware sensor."""
        super().__init__(coordinator, config_entry)
        uuid = config_entry.unique_id or coordinator.player.host
        self._attr_unique_id = f"{uuid}_firmware"
        self._attr_name = "Firmware"

    @property  # type: ignore[override]
    def native_value(self) -> str | None:
        """Return current firmware version."""
        player = self.coordinator.player
        # Primary source: device_info firmware field (DeviceInfo is a Pydantic model)
        if player.device_info:
            firmware = player.device_info.firmware
            if firmware and str(firmware).strip() not in {"", "0", "-", "unknown"}:
                return str(firmware)

        if player.firmware and str(player.firmware).strip() not in {"", "0", "-", "unknown"}:
            return str(player.firmware)

        return "Unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Additional firmware-related information."""
        attrs: dict[str, Any] = {}
        player = self.coordinator.player

        # DeviceInfo is a Pydantic model - access attributes directly
        if player.device_info:
            device_info = player.device_info

            # MCU version (microcontroller firmware)
            if device_info.mcu_ver:
                attrs["mcu_version"] = str(device_info.mcu_ver)

            # DSP version (digital signal processor firmware)
            if device_info.dsp_ver:
                attrs["dsp_version"] = str(device_info.dsp_ver)

            # Release/build info
            if device_info.release_date:
                attrs["release"] = str(device_info.release_date)

            # Update availability info (if present)
            attrs["update_available"] = bool(getattr(player, "firmware_update_available", False))
            latest = getattr(player, "latest_firmware_version", None)
            if latest:
                attrs["latest_version"] = str(latest)
            attrs["supports_firmware_install"] = bool(getattr(player, "supports_firmware_install", False))

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

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator, config_entry)
        uuid = config_entry.unique_id or coordinator.player.host
        self._attr_unique_id = f"{uuid}_current_input"
        self._attr_name = "Current Input"  # Generic label

    @property  # type: ignore[override]
    def native_value(self):
        """Return the current input source (can be selectable or non-selectable)."""
        return self.coordinator.player.source


# ------------------- Bluetooth Output Sensor -------------------


class WiiMBluetoothOutputSensor(WiimEntity, SensorEntity):
    """Shows Bluetooth output status (whether audio is being sent to Bluetooth device)."""

    _attr_icon = "mdi:bluetooth"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator, config_entry)
        uuid = config_entry.unique_id or coordinator.player.host
        self._attr_unique_id = f"{uuid}_bluetooth_output"
        self._attr_name = "Bluetooth Output"

    @property  # type: ignore[override]
    def native_value(self) -> str:
        """Return 'on' if Bluetooth output is active, 'off' if not."""
        return "on" if self.coordinator.player.is_bluetooth_output_active else "off"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        player = self.coordinator.player
        return {
            "hardware_output_mode": player.audio_output_mode or "Unknown",
            "audio_cast_active": player.is_bluetooth_output_active,
        }


# ------------------- Audio Quality Sensors -------------------


class WiiMAudioQualitySensor(WiimEntity, SensorEntity):
    """Audio quality sensor showing current track's audio specifications."""

    _attr_icon = "mdi:ear-hearing"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator, config_entry)
        uuid = config_entry.unique_id or coordinator.player.host
        self._attr_unique_id = f"{uuid}_audio_quality"
        self._attr_name = "Audio Quality"

    @property  # type: ignore[override]
    def native_value(self) -> str:
        """Return formatted audio quality string."""
        player = self.coordinator.player
        sample_rate = player.media_sample_rate
        bit_depth = player.media_bit_depth
        bit_rate = player.media_bit_rate

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
        player = self.coordinator.player
        attrs = {}
        if player.media_sample_rate:
            attrs["sample_rate"] = player.media_sample_rate
        if player.media_bit_depth:
            attrs["bit_depth"] = player.media_bit_depth
        if player.media_bit_rate:
            attrs["bit_rate"] = player.media_bit_rate
        if player.media_codec:
            attrs["codec"] = player.media_codec
        return attrs


class WiiMSampleRateSensor(WiimEntity, SensorEntity):
    """Sample rate sensor showing current track's sample rate."""

    _attr_icon = "mdi:sine-wave"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "Hz"

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator, config_entry)
        uuid = config_entry.unique_id or coordinator.player.host
        self._attr_unique_id = f"{uuid}_sample_rate"
        self._attr_name = "Sample Rate"

    @property  # type: ignore[override]
    def native_value(self) -> int | None:
        """Return current track's sample rate in Hz."""
        return self.coordinator.player.media_sample_rate


class WiiMBitDepthSensor(WiimEntity, SensorEntity):
    """Bit depth sensor showing current track's bit depth."""

    _attr_icon = "mdi:database"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "bit"

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator, config_entry)
        uuid = config_entry.unique_id or coordinator.player.host
        self._attr_unique_id = f"{uuid}_bit_depth"
        self._attr_name = "Bit Depth"

    @property  # type: ignore[override]
    def native_value(self) -> int | None:
        """Return current track's bit depth."""
        return self.coordinator.player.media_bit_depth


class WiiMBitRateSensor(WiimEntity, SensorEntity):
    """Bit rate sensor showing current track's bit rate."""

    _attr_icon = "mdi:transmission-tower"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "kbps"

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator, config_entry)
        uuid = config_entry.unique_id or coordinator.player.host
        self._attr_unique_id = f"{uuid}_bit_rate"
        self._attr_name = "Bit Rate"

    @property  # type: ignore[override]
    def native_value(self) -> int | None:
        """Return current track's bit rate in kbps."""
        return self.coordinator.player.media_bit_rate
