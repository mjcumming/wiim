"""Unit tests for version helpers."""

from importlib import metadata
from unittest.mock import AsyncMock, MagicMock

import custom_components.wiim.version as version_module
from custom_components.wiim.version import (
    async_ensure_pywiim_version,
    get_pywiim_version,
    get_pywiim_version_label,
    is_pywiim_version_compatible,
)


class TestVersionHelpers:
    """Test pywiim version helper behavior."""

    def test_get_pywiim_version_prefers_cached_value(self, monkeypatch):
        """Use cached value when it has been resolved already."""
        monkeypatch.setattr(version_module, "_CACHED_PYWIIM_VERSION", "2.1.77")
        assert get_pywiim_version() == "2.1.77"
        assert get_pywiim_version_label() == "pywiim 2.1.77"

    def test_get_pywiim_version_falls_back_to_module_attr(self, monkeypatch):
        """Fall back to pywiim.__version__ when cache is empty."""
        import pywiim

        monkeypatch.setattr(version_module, "_CACHED_PYWIIM_VERSION", None)
        monkeypatch.setattr(pywiim, "__version__", "fallback-version")
        assert get_pywiim_version() == "fallback-version"

    async def test_async_ensure_pywiim_version_uses_executor_and_caches(self, monkeypatch):
        """Resolve version in executor and cache the result."""
        monkeypatch.setattr(version_module, "_CACHED_PYWIIM_VERSION", None)
        monkeypatch.setattr(metadata, "version", lambda _name: "2.1.99")

        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(side_effect=lambda func: func())

        resolved = await async_ensure_pywiim_version(hass)

        assert resolved == "2.1.99"
        assert get_pywiim_version() == "2.1.99"
        hass.async_add_executor_job.assert_awaited_once()

    def test_is_pywiim_version_compatible_true_for_newer(self) -> None:
        """Compatibility check accepts exact required version."""
        assert is_pywiim_version_compatible("2.1.80", "2.1.80") is True

    def test_is_pywiim_version_compatible_false_for_older(self) -> None:
        """Compatibility check rejects non-matching versions."""
        assert is_pywiim_version_compatible("2.1.79", "2.1.80") is False

    def test_is_pywiim_version_compatible_false_for_newer(self) -> None:
        """Compatibility check rejects newer but non-pinned versions."""
        assert is_pywiim_version_compatible("2.1.81", "2.1.80") is False

    def test_is_pywiim_version_compatible_false_for_invalid(self) -> None:
        """Compatibility check rejects invalid version strings."""
        assert is_pywiim_version_compatible("unknown", "2.1.80") is False
