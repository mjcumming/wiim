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
            "response_timeout": 5.0,  # Default timeout
            "retry_count": 3,
            "is_legacy_device": False,
            "is_wiim_device": False,
        }

        # Detect device type
        capabilities["is_wiim_device"] = is_wiim_device(device_info)
        capabilities["is_legacy_device"] = is_legacy_device(device_info)

        # Set capabilities based on device type
        if capabilities["is_wiim_device"]:
            capabilities["supports_enhanced_grouping"] = True
            capabilities["response_timeout"] = 2.0  # Faster for WiiM
            capabilities["retry_count"] = 2
        elif capabilities["is_legacy_device"]:
            capabilities["supports_enhanced_grouping"] = False
            capabilities["response_timeout"] = 8.0  # Slower for legacy
            capabilities["retry_count"] = 4
            capabilities["supports_metadata"] = False

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
        "supports_enhanced_grouping": False,
        "response_timeout": 5.0,
        "retry_count": 3,
    }

    if capabilities["is_wiim_device"]:
        capabilities["supports_enhanced_grouping"] = True
        capabilities["response_timeout"] = 2.0
        capabilities["retry_count"] = 2
    elif capabilities["is_legacy_device"]:
        capabilities["response_timeout"] = 8.0
        capabilities["retry_count"] = 4

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
        "arylic",
        "doss",
        "dayton audio",
        "ieast",
        "linkplay",
        "smart zone",
    ]

    return any(legacy_model in model_lower for legacy_model in legacy_models)


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
