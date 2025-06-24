"""Test coordinator backoff logic."""

from datetime import timedelta

from custom_components.wiim.coordinator_backoff import BackoffController


def test_backoff_initialization():
    """Test backoff controller initialization."""
    backoff = BackoffController()
    assert backoff.consecutive_failures == 0


def test_backoff_failure_tracking():
    """Test failure tracking and counting."""
    backoff = BackoffController()

    # Initially no failures
    assert backoff.consecutive_failures == 0

    # Record failures
    backoff.record_failure()
    assert backoff.consecutive_failures == 1

    backoff.record_failure()
    assert backoff.consecutive_failures == 2

    backoff.record_failure()
    assert backoff.consecutive_failures == 3


def test_backoff_success_reset():
    """Test that success resets failure counter."""
    backoff = BackoffController()

    # Record multiple failures
    backoff.record_failure()
    backoff.record_failure()
    backoff.record_failure()
    assert backoff.consecutive_failures == 3

    # Success should reset
    backoff.record_success()
    assert backoff.consecutive_failures == 0


def test_backoff_intervals():
    """Test backoff interval calculation."""
    backoff = BackoffController()
    default_interval = 5

    # No failures - should return default
    interval = backoff.next_interval(default_interval)
    assert interval == timedelta(seconds=default_interval)

    # 1 failure - should return default
    backoff.record_failure()
    interval = backoff.next_interval(default_interval)
    assert interval == timedelta(seconds=default_interval)

    # 2 failures - should return 10 seconds
    backoff.record_failure()
    interval = backoff.next_interval(default_interval)
    assert interval == timedelta(seconds=10)

    # 3 failures - should return 30 seconds
    backoff.record_failure()
    interval = backoff.next_interval(default_interval)
    assert interval == timedelta(seconds=30)

    # 4 failures - should return 30 seconds (stays at last threshold)
    backoff.record_failure()
    interval = backoff.next_interval(default_interval)
    assert interval == timedelta(seconds=30)

    # 5 failures - should return 60 seconds
    backoff.record_failure()
    interval = backoff.next_interval(default_interval)
    assert interval == timedelta(seconds=60)

    # 10 failures - should return 60 seconds (max)
    for _ in range(5):
        backoff.record_failure()
    interval = backoff.next_interval(default_interval)
    assert interval == timedelta(seconds=60)


def test_backoff_cycle():
    """Test complete backoff cycle with recovery."""
    backoff = BackoffController()
    default_interval = 5

    # Build up failures
    backoff.record_failure()
    backoff.record_failure()
    assert backoff.next_interval(default_interval) == timedelta(seconds=10)

    backoff.record_failure()
    assert backoff.next_interval(default_interval) == timedelta(seconds=30)

    backoff.record_failure()
    backoff.record_failure()
    assert backoff.next_interval(default_interval) == timedelta(seconds=60)

    # Recovery - should reset to default
    backoff.record_success()
    assert backoff.consecutive_failures == 0
    assert backoff.next_interval(default_interval) == timedelta(seconds=default_interval)
