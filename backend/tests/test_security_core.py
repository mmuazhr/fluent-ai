"""Security-critical unit tests: auth gate + API rate limiter.

Run from the backend/ directory:
    ../.venv/bin/python -m pytest tests/ -q
"""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from middleware.auth import require_auth
from services.usage_tracker import RPM_LIMIT, UsageTracker


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


class _FakeSettings:
    def __init__(self, token: str) -> None:
        self.app_access_token = token


# ── require_auth ────────────────────────────────────────────────────────────


def test_auth_disabled_when_token_unset_allows_anonymous():
    # Arrange: no configured token == local-dev mode
    with patch("middleware.auth.get_settings", return_value=_FakeSettings("")):
        # Act / Assert: missing credentials must not raise
        assert require_auth(credentials=None) is None


def test_auth_allows_matching_bearer_token():
    with patch("middleware.auth.get_settings", return_value=_FakeSettings("s3cret")):
        assert require_auth(credentials=_creds("s3cret")) is None


def test_auth_rejects_missing_credentials_when_enabled():
    with patch("middleware.auth.get_settings", return_value=_FakeSettings("s3cret")):
        with pytest.raises(HTTPException) as err:
            require_auth(credentials=None)
        assert err.value.status_code == 401


def test_auth_rejects_wrong_token_when_enabled():
    with patch("middleware.auth.get_settings", return_value=_FakeSettings("s3cret")):
        with pytest.raises(HTTPException) as err:
            require_auth(credentials=_creds("nope"))
        assert err.value.status_code == 401


# ── usage_tracker.check_rate_limit (sliding window) ──────────────────────────


def test_rate_limit_allows_up_to_limit():
    tracker = UsageTracker()
    tracker._rpm_window.clear()
    assert all(tracker.check_rate_limit() for _ in range(RPM_LIMIT))


def test_rate_limit_blocks_request_over_limit():
    tracker = UsageTracker()
    tracker._rpm_window.clear()
    for _ in range(RPM_LIMIT):
        tracker.check_rate_limit()
    assert tracker.check_rate_limit() is False


def test_rate_limit_evicts_stale_timestamps():
    tracker = UsageTracker()
    tracker._rpm_window.clear()
    # Fill the window with timestamps already older than WINDOW_SECONDS
    stale = time.monotonic() - 61
    for _ in range(RPM_LIMIT):
        tracker._rpm_window.append(stale)
    # Next call should evict stale entries and allow the request
    assert tracker.check_rate_limit() is True
