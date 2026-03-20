"""Tests for subwoofer status helpers (dict vs SubwooferStatus)."""

from pywiim.api.subwoofer import SubwooferStatus

from custom_components.wiim.subwoofer_helpers import (
    subwoofer_enabled_from_status,
    subwoofer_level_from_status,
    subwoofer_plugged,
    subwoofer_status_for_diagnostics,
)


def _sample_status() -> SubwooferStatus:
    return SubwooferStatus(
        enabled=True,
        plugged=True,
        crossover=80,
        phase=0,
        level=3,
        main_filter_enabled=True,
        sub_filter_enabled=True,
        sub_delay=0,
        output_mode=0,
        mix_sub=0,
        linein_delay=0.0,
        delay_main_sub="",
    )


class TestSubwooferPlugged:
    """Test subwoofer_plugged."""

    def test_dict_plugged(self) -> None:
        assert subwoofer_plugged({"plugged": True}) is True
        assert subwoofer_plugged({"plugged": False}) is False

    def test_dataclass_plugged(self) -> None:
        assert subwoofer_plugged(_sample_status()) is True

    def test_none(self) -> None:
        assert subwoofer_plugged(None) is False


class TestSubwooferEnabled:
    """Test subwoofer_enabled_from_status."""

    def test_dict(self) -> None:
        assert subwoofer_enabled_from_status({"status": True}) is True
        assert subwoofer_enabled_from_status({"status": False}) is False

    def test_dataclass(self) -> None:
        assert subwoofer_enabled_from_status(_sample_status()) is True

    def test_none(self) -> None:
        assert subwoofer_enabled_from_status(None) is None


class TestSubwooferLevel:
    """Test subwoofer_level_from_status."""

    def test_dict(self) -> None:
        assert subwoofer_level_from_status({"level": 5}) == 5.0

    def test_dataclass(self) -> None:
        assert subwoofer_level_from_status(_sample_status()) == 3.0

    def test_none(self) -> None:
        assert subwoofer_level_from_status(None) is None


class TestSubwooferDiagnostics:
    """Test subwoofer_status_for_diagnostics."""

    def test_dict_legacy_keys(self) -> None:
        d = {
            "plugged": 1,
            "status": 1,
            "level": 2,
            "cross": 100,
            "phase": 180,
            "sub_delay": 10,
            "main_filter": 0,
            "sub_filter": 0,
        }
        out = subwoofer_status_for_diagnostics(d)
        assert out["connected"] is True
        assert out["enabled"] is True
        assert out["level_db"] == 2
        assert out["crossover_hz"] == 100

    def test_dataclass(self) -> None:
        out = subwoofer_status_for_diagnostics(_sample_status())
        assert out["connected"] is True
        assert out["enabled"] is True
        assert out["level_db"] == 3
        assert out["crossover_hz"] == 80
