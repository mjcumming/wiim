"""WiiM Firmware Capabilities Detection.

This module provides firmware detection and capability probing for different
WiiM and LinkPlay device types to handle compatibility issues between newer
WiiM devices and older Audio Pro units.
"""

from __future__ import annotations

import logging
from typing import Any

from .api import WiiMError
from .models import DeviceInfo

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "WiiMFirmwareCapabilities",
    "detect_device_capabilities",
    "is_wiim_device",
    "is_legacy_device",
    "detect_audio_pro_generation",
    "supports_standard_led_control",
    "get_led_command_format",
]


class WiiMFirmwareCapabilities:
    """Detect and cache firmware capabilities for different device types."""

    def __init__(self) -> None:
        """Initialize the capabilities detector."""
        self._capabilities: dict[str, dict[str, Any]] = {}
        self._firmware_versions: dict[str, str] = {}
        self._device_types: dict[str, str] = {}

    async def detect_capabilities(self, client, device_info: DeviceInfo) -> dict[str, Any]:
        """Probe device capabilities and cache results.

        Args:
            client: WiiM API client instance
            device_info: Device information from getStatusEx

        Returns:
            Dictionary of device capabilities
        """
        device_id = f"{client.host}:{device_info.uuid}"

        if device_id in self._capabilities:
            return self._capabilities[device_id]

        capabilities = {
            "firmware_version": device_info.firmware,
            "device_type": device_info.model,
            "supports_getstatuse": True,  # Assume yes, fallback if fails
            "supports_getslavelist": True,
            "supports_enhanced_grouping": False,
            "supports_metadata": True,
            "supports_audio_output": True,  # Assume yes, will be probed
            "supports_led_control": True,  # Assume yes, will be probed
            "led_command_format": "standard",  # Default format
            "response_timeout": 5.0,  # Default timeout
            "retry_count": 3,
            "is_legacy_device": False,
            "is_wiim_device": False,
        }

        # Detect device type
        capabilities["is_wiim_device"] = is_wiim_device(device_info)
        capabilities["is_legacy_device"] = is_legacy_device(device_info)

        # Detect Audio Pro generation for enhanced compatibility
        audio_pro_generation = detect_audio_pro_generation(device_info)
        capabilities["audio_pro_generation"] = audio_pro_generation

        # Detect LED support
        capabilities["supports_led_control"] = supports_standard_led_control(device_info)
        capabilities["led_command_format"] = get_led_command_format(device_info)

        # Set capabilities based on device type
        if capabilities["is_wiim_device"]:
            capabilities["supports_enhanced_grouping"] = True
            capabilities["supports_audio_output"] = True  # All WiiM devices support audio output control
            capabilities["response_timeout"] = 2.0  # Faster for WiiM
            capabilities["retry_count"] = 2
        elif capabilities["is_legacy_device"]:
            # Apply Audio Pro generation specific optimizations
            if audio_pro_generation == "mkii":
                capabilities["supports_enhanced_grouping"] = False
                capabilities["response_timeout"] = 6.0  # Medium timeout for MkII
                capabilities["retry_count"] = 3
                capabilities["supports_metadata"] = False  # getMetaInfo not supported
                capabilities["protocol_priority"] = ["https", "http"]  # HTTPS first for MkII
                # Audio Pro MkII specific: requires client certificate for mTLS on port 4443
                capabilities["requires_client_cert"] = True
                capabilities["preferred_ports"] = [4443, 8443, 443]  # Port 4443 primary
                capabilities["supports_player_status_ex"] = False  # Use getStatusEx instead
                capabilities["supports_presets"] = False  # getPresetInfo not supported
                capabilities["supports_eq"] = False  # EQ commands not supported
                capabilities["status_endpoint"] = "/httpapi.asp?command=getStatusEx"
            elif audio_pro_generation == "w_generation":
                capabilities["supports_enhanced_grouping"] = True  # W-gen supports enhanced features
                capabilities["response_timeout"] = 4.0  # Faster for W-gen
                capabilities["retry_count"] = 2
                capabilities["supports_metadata"] = True
                capabilities["protocol_priority"] = ["https", "http"]
            else:
                # Original Audio Pro devices
                capabilities["supports_enhanced_grouping"] = False
                capabilities["response_timeout"] = 8.0  # Slower for original
                capabilities["retry_count"] = 4
                capabilities["supports_metadata"] = False
                capabilities["protocol_priority"] = ["http", "https"]  # HTTP first for legacy

        # Probe for getStatusEx support
        try:
            await client.get_status()
        except WiiMError:
            capabilities["supports_getstatuse"] = False
            _LOGGER.debug("Device %s does not support getStatusEx", client.host)

        # Probe for getSlaveList support
        try:
            await client._request("/httpapi.asp?command=multiroom:getSlaveList")
        except WiiMError:
            capabilities["supports_getslavelist"] = False
            _LOGGER.debug("Device %s does not support getSlaveList", client.host)

        # Probe for metadata support (getMetaInfo)
        try:
            await client._request("/httpapi.asp?command=getMetaInfo")
        except WiiMError:
            capabilities["supports_metadata"] = False
            _LOGGER.debug("Device %s does not support getMetaInfo", client.host)

        # Probe for audio output support (getNewAudioOutputHardwareMode)
        # This is primarily a WiiM enhancement, but many devices support audio output modes
        try:
            result = await client._request("/httpapi.asp?command=getNewAudioOutputHardwareMode")
            capabilities["supports_audio_output"] = True
            _LOGGER.info(
                "[AUDIO OUTPUT DEBUG] Device %s supports getNewAudioOutputHardwareMode, result: %s", client.host, result
            )
        except WiiMError as e:
            # Only disable if not already determined to be supported (e.g., WiiM devices)
            if not capabilities.get("supports_audio_output", False):
                capabilities["supports_audio_output"] = False
                _LOGGER.warning(
                    "[AUDIO OUTPUT DEBUG] Device %s getNewAudioOutputHardwareMode probe failed: %s - audio output entities will not be created",
                    client.host,
                    e,
                )
            else:
                _LOGGER.debug(
                    "[AUDIO OUTPUT DEBUG] Device %s getNewAudioOutputHardwareMode probe failed but audio output already determined to be supported",
                    client.host,
                )

        self._capabilities[device_id] = capabilities
        _LOGGER.info(
            "Detected capabilities for %s (%s): %s",
            device_info.name or "Unknown",
            device_info.model or "Unknown",
            capabilities,
        )

        return capabilities

    def get_cached_capabilities(self, device_id: str) -> dict[str, Any] | None:
        """Get cached capabilities for a device.

        Args:
            device_id: Device identifier (host:uuid)

        Returns:
            Cached capabilities or None if not found
        """
        return self._capabilities.get(device_id)

    def clear_cache(self) -> None:
        """Clear all cached capabilities."""
        self._capabilities.clear()
        self._firmware_versions.clear()
        self._device_types.clear()


def detect_device_capabilities(device_info: DeviceInfo) -> dict[str, Any]:
    """Detect device capabilities from device info without API calls.

    Args:
        device_info: Device information from getStatusEx

    Returns:
        Dictionary of detected capabilities
    """
    capabilities = {
        "firmware_version": device_info.firmware,
        "device_type": device_info.model,
        "is_wiim_device": is_wiim_device(device_info),
        "is_legacy_device": is_legacy_device(device_info),
        "audio_pro_generation": detect_audio_pro_generation(device_info),
        "supports_enhanced_grouping": False,
        "supports_audio_output": False,  # Default to False, enable for WiiM devices
        "response_timeout": 5.0,
        "retry_count": 3,
        "protocol_priority": ["https", "http"],  # Default: try HTTPS first
    }

    if capabilities["is_wiim_device"]:
        capabilities["supports_enhanced_grouping"] = True
        capabilities["supports_audio_output"] = True  # All WiiM devices support audio output control
        capabilities["response_timeout"] = 2.0
        capabilities["retry_count"] = 2
        capabilities["protocol_priority"] = ["https", "http"]
    elif capabilities["is_legacy_device"]:
        # Apply Audio Pro generation specific optimizations
        generation = capabilities["audio_pro_generation"]
        if generation == "mkii":
            capabilities["response_timeout"] = 6.0
            capabilities["retry_count"] = 3
            capabilities["protocol_priority"] = ["https", "http"]  # HTTPS first for MkII
            # Audio Pro MkII specific: requires client certificate for mTLS on port 4443
            capabilities["requires_client_cert"] = True
            capabilities["preferred_ports"] = [4443, 8443, 443]  # Port 4443 primary
            capabilities["supports_player_status_ex"] = False  # Use getStatusEx instead
            capabilities["supports_presets"] = False  # getPresetInfo not supported
            capabilities["supports_eq"] = False  # EQ commands not supported
            capabilities["supports_metadata"] = False  # getMetaInfo not supported
            capabilities["status_endpoint"] = "/httpapi.asp?command=getStatusEx"
        elif generation == "w_generation":
            capabilities["supports_enhanced_grouping"] = True
            capabilities["response_timeout"] = 4.0
            capabilities["retry_count"] = 2
            capabilities["protocol_priority"] = ["https", "http"]
        else:
            # Original Audio Pro devices
            capabilities["response_timeout"] = 8.0
            capabilities["retry_count"] = 4
            capabilities["protocol_priority"] = ["http", "https"]  # HTTP first for legacy

    return capabilities


def is_wiim_device(device_info: DeviceInfo) -> bool:
    """Check if device is a WiiM device.

    Args:
        device_info: Device information

    Returns:
        True if device is a WiiM device
    """
    if not device_info.model:
        return False

    model_lower = device_info.model.lower()
    wiim_models = [
        "wiim",
        "wiim mini",
        "wiim pro",
        "wiim pro plus",
        "wiim amp",
        "wiim ultra",
        "wiimu",
    ]

    return any(wiim_model in model_lower for wiim_model in wiim_models)


def detect_audio_pro_generation(device_info: DeviceInfo) -> str:
    """Detect Audio Pro device generation for optimized handling.

    Args:
        device_info: Device information

    Returns:
        Generation string: "original", "mkii", "w_generation", or "unknown"
    """
    if not device_info.model:
        return "unknown"

    model_lower = device_info.model.lower()

    # Audio Pro generation patterns
    if any(gen in model_lower for gen in ["mkii", "mk2", "mk ii", "mark ii"]):
        return "mkii"
    elif any(gen in model_lower for gen in ["w-", "w series", "w generation", "w gen"]):
        return "w_generation"
    elif any(model in model_lower for model in ["a10", "a15", "a28", "c10", "audio pro"]):
        # Modern Audio Pro devices (assume MkII if not specified)
        if device_info.firmware:
            # Try to determine from firmware version if available
            firmware_lower = device_info.firmware.lower()
            if any(version in firmware_lower for version in ["1.56", "1.57", "1.58", "1.59", "1.60"]):
                return "mkii"  # MkII firmware range
            elif any(version in firmware_lower for version in ["2.0", "2.1", "2.2", "2.3"]):
                return "w_generation"  # W-generation firmware range

        return "mkii"  # Default to MkII for modern Audio Pro models
    else:
        return "original"


def is_legacy_device(device_info: DeviceInfo) -> bool:
    """Check if device is a legacy Audio Pro or older LinkPlay device.

    Args:
        device_info: Device information

    Returns:
        True if device is a legacy device
    """
    if not device_info.model:
        return False

    model_lower = device_info.model.lower()
    legacy_models = [
        "audio pro",
        "a10",  # Audio Pro A10 (including MkII)
        "a15",  # Audio Pro A15 (including MkII)
        "a28",  # Audio Pro A28
        "c10",  # Audio Pro C10 (including MkII)
        "arylic",
        "doss",
        "dayton audio",
        "ieast",
        "linkplay",
        "smart zone",
    ]

    return any(legacy_model in model_lower for legacy_model in legacy_models)


def supports_standard_led_control(device_info: DeviceInfo) -> bool:
    """Check if device supports standard LinkPlay LED commands.

    Args:
        device_info: Device information

    Returns:
        True if device supports standard LED commands
    """
    if not device_info.model:
        return True  # Assume yes for unknown devices

    model_lower = device_info.model.lower()

    # Devices known to NOT support standard LED commands
    non_standard_led_devices = [
        "arylic",
        "up2stream",
        "s10+",
        "amp 2.0",
        "amp 2.1",
    ]

    return not any(device_type in model_lower for device_type in non_standard_led_devices)


def get_led_command_format(device_info: DeviceInfo) -> str:
    """Get the LED command format for a specific device type.

    Args:
        device_info: Device information

    Returns:
        LED command format: "standard" or "arylic"
    """
    if not device_info.model:
        return "standard"  # Default to standard for unknown devices

    model_lower = device_info.model.lower()

    # Arylic devices use different LED commands
    if any(arylic_type in model_lower for arylic_type in ["arylic", "up2stream"]):
        return "arylic"

    return "standard"


def get_optimal_polling_interval(capabilities: dict[str, Any], role: str, is_playing: bool) -> int:
    """Get optimal polling interval based on device capabilities.

    Args:
        capabilities: Device capabilities
        role: Device role (master/slave/solo)
        is_playing: Whether device is currently playing

    Returns:
        Polling interval in seconds
    """
    if capabilities.get("is_legacy_device", False):
        # Legacy devices need longer intervals
        if role == "slave":
            return 10  # 10 seconds for legacy slaves
        elif is_playing:
            return 3  # 3 seconds for legacy devices during playback
        else:
            return 15  # 15 seconds for legacy devices when idle
    else:
        # Modern WiiM devices
        if role == "slave":
            return 5  # 5 seconds for slaves
        elif is_playing:
            return 1  # 1 second for real-time updates
        else:
            return 5  # 5 seconds when idle


def is_legacy_firmware_error(error: Exception) -> bool:
    """Detect errors specific to legacy firmware.

    Args:
        error: Exception to check

    Returns:
        True if error is typical of legacy firmware
    """
    error_str = str(error).lower()
    legacy_error_indicators = [
        "empty response",
        "invalid json",
        "expecting value",
        "timeout",
        "connection refused",
        "unknown command",
    ]
    return any(indicator in error_str for indicator in legacy_error_indicators)
