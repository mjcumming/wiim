"""WiiM Services Package.

This package contains all service implementations separated by domain:
- media_services: Media playback and control services
- group_services: Group management and coordination services
- diagnostic_services: Entity diagnostics and maintenance services
- device_services: Device-specific services (reboot, sync, etc.)
"""

from .device_services import WiiMDeviceServices
from .diagnostic_services import WiiMDiagnosticServices
from .group_services import WiiMGroupServices
from .media_services import WiiMMediaServices

__all__ = [
    "WiiMMediaServices",
    "WiiMGroupServices",
    "WiiMDiagnosticServices",
    "WiiMDeviceServices",
]
