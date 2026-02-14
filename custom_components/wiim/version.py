"""Version helpers for integration and diagnostics."""

from __future__ import annotations

from importlib import metadata, resources

from homeassistant.core import HomeAssistant
from packaging.version import InvalidVersion, Version

_CACHED_PYWIIM_VERSION: str | None = None


def _load_required_pywiim_version() -> str:
    """Load the required pywiim version from our packaged version file.

    We keep a single source of truth in `pywiim-version.txt` and sync other pins
    (manifest/dev requirements) from it during development/release.
    """
    try:
        version = (resources.files(__package__) / "pywiim-version.txt").read_text(encoding="ascii").strip()
        # Normalize accidental trailing newlines/spaces; keep the exact version string.
        return version
    except Exception:  # noqa: BLE001
        # Fail safe: if the resource file is missing for some reason, keep setup
        # failure behavior deterministic rather than crashing imports.
        return "unknown"


REQUIRED_PYWIIM_VERSION = _load_required_pywiim_version()


def _fallback_pywiim_version() -> str:
    """Return best-effort version from module attribute."""
    try:
        import pywiim

        return str(getattr(pywiim, "__version__", "unknown"))
    except Exception:  # noqa: BLE001
        return "unknown"


def _resolve_pywiim_version_sync() -> str:
    """Resolve installed pywiim package version (blocking)."""
    try:
        return metadata.version("pywiim")
    except metadata.PackageNotFoundError:
        return _fallback_pywiim_version()


async def async_ensure_pywiim_version(hass: HomeAssistant) -> str:
    """Resolve and cache pywiim package version without blocking the loop."""
    global _CACHED_PYWIIM_VERSION  # noqa: PLW0603

    if _CACHED_PYWIIM_VERSION is None:
        _CACHED_PYWIIM_VERSION = await hass.async_add_executor_job(_resolve_pywiim_version_sync)
    return _CACHED_PYWIIM_VERSION


def get_pywiim_version() -> str:
    """Return cached pywiim version without blocking the event loop."""
    if _CACHED_PYWIIM_VERSION is not None:
        return _CACHED_PYWIIM_VERSION
    return _fallback_pywiim_version()


def get_pywiim_version_label() -> str:
    """Return display label for Home Assistant device info."""
    return f"pywiim {get_pywiim_version()}"


def is_pywiim_version_compatible(installed_version: str, required_version: str = REQUIRED_PYWIIM_VERSION) -> bool:
    """Return True when installed pywiim matches required version exactly."""
    try:
        return Version(installed_version) == Version(required_version)
    except InvalidVersion:
        return False
