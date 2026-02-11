"""Unit tests for compact error logging helpers."""

from custom_components.wiim.__init__ import _compact_connectivity_error
from custom_components.wiim.coordinator import _compact_wiim_error


def test_compact_connectivity_error_unreachable_message() -> None:
    """Unreachable errors are compacted to avoid large log dumps."""
    err = Exception(
        "Request failed after 2 attempts: Device unreachable at 192.168.6.221. "
        "Connection failed on all attempted protocols."
    )
    assert _compact_connectivity_error(err) == "device unreachable"


def test_compact_connectivity_error_non_unreachable_message() -> None:
    """Non-connectivity errors preserve detail."""
    err = Exception("API returned malformed response")
    assert _compact_connectivity_error(err) == "API returned malformed response"


def test_compact_wiim_error_unreachable_message() -> None:
    """Coordinator compacts unreachable errors for update logs."""
    err = Exception("Device unreachable at 192.168.6.221")
    assert _compact_wiim_error(err) == "device unreachable"


def test_compact_wiim_error_non_unreachable_message() -> None:
    """Coordinator preserves non-connectivity error detail."""
    err = Exception("Timeout waiting for response")
    assert _compact_wiim_error(err) == "Timeout waiting for response"
