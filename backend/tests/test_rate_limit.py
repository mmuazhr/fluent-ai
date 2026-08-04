"""Unit tests for the in-process sliding-window rate limiter."""
from services.usage_tracker import UsageTracker, RPM_LIMIT


def test_allows_requests_up_to_the_limit():
    # Arrange
    tracker = UsageTracker()
    tracker._rpm_window.clear()

    # Act / Assert — every call within the limit is allowed
    for _ in range(RPM_LIMIT):
        assert tracker.check_rate_limit() is True


def test_blocks_the_request_that_exceeds_the_limit():
    # Arrange
    tracker = UsageTracker()
    tracker._rpm_window.clear()
    for _ in range(RPM_LIMIT):
        tracker.check_rate_limit()

    # Act
    blocked = tracker.check_rate_limit()

    # Assert
    assert blocked is False


def test_independent_trackers_do_not_share_a_window():
    # Arrange
    a = UsageTracker()
    b = UsageTracker()
    a._rpm_window.clear()
    b._rpm_window.clear()

    # Act — exhaust a
    for _ in range(RPM_LIMIT):
        a.check_rate_limit()

    # Assert — b is unaffected
    assert a.check_rate_limit() is False
    assert b.check_rate_limit() is True
