from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

USAGE_FILE = Path(__file__).parent.parent / "memory" / "usage_log.json"

RPM_LIMIT: int = 10          # max requests per minute
WINDOW_SECONDS: int = 60     # sliding-window width in seconds


class UsageTracker:
    """Tracks daily Gemini API usage and enforces a per-minute rate limit.

    All mutable state is protected by a single threading.Lock so the tracker
    is safe to call from multiple asyncio tasks (via asyncio.to_thread) and
    any background threads.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._day: date = datetime.now(timezone.utc).date()
        self._daily_requests: int = 0
        self._daily_tokens_in: int = 0
        self._daily_tokens_out: int = 0
        self._session_tokens: dict[str, int] = {}
        self._model_requests: dict[str, int] = {}
        self.daily_limit: int = 1500
        # Sliding-window rate-limit: stores monotonic timestamps of recent requests
        self._rpm_window: deque[float] = deque()
        self._load()

    # ── Persistence ────────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not USAGE_FILE.exists():
            return
        try:
            data = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
            stored_date = date.fromisoformat(data.get("date", "2000-01-01"))
            if stored_date == datetime.now(timezone.utc).date():
                self._daily_requests = data.get("daily_requests", 0)
                self._daily_tokens_in = data.get("daily_tokens_in", 0)
                self._daily_tokens_out = data.get("daily_tokens_out", 0)
                self._model_requests = data.get("model_requests", {})
                logger.info(f"Usage restored: {self._daily_requests} requests today")
        except Exception as exc:
            logger.warning(f"Could not load usage log: {exc}")

    def _save(self) -> None:
        """Persist counters — must be called while holding self._lock."""
        try:
            USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
            USAGE_FILE.write_text(
                json.dumps(
                    {
                        "date": self._day.isoformat(),
                        "daily_requests": self._daily_requests,
                        "daily_tokens_in": self._daily_tokens_in,
                        "daily_tokens_out": self._daily_tokens_out,
                        "model_requests": self._model_requests,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning(f"Could not save usage log: {exc}")

    def _check_rollover(self) -> None:
        """Reset daily counters when the UTC date changes. Caller holds lock."""
        today = datetime.now(timezone.utc).date()
        if today != self._day:
            self._day = today
            self._daily_requests = 0
            self._daily_tokens_in = 0
            self._daily_tokens_out = 0
            self._model_requests = {}
            self._save()
            logger.info("Usage counters rolled over for new day")

    # ── Public API ─────────────────────────────────────────────────────────────

    def check_rate_limit(self) -> bool:
        """Sliding-window RPM check.

        Returns True (allowed) or False (rate-limited).
        Records the request timestamp when allowed.
        """
        now = time.monotonic()
        cutoff = now - WINDOW_SECONDS

        with self._lock:
            # Evict timestamps older than the window
            while self._rpm_window and self._rpm_window[0] < cutoff:
                self._rpm_window.popleft()

            if len(self._rpm_window) >= RPM_LIMIT:
                logger.warning("Rate limit exceeded — request blocked")
                return False

            self._rpm_window.append(now)
            return True

    def record(
        self,
        session_id: str,
        tokens_in: int,
        tokens_out: int,
        model_name: str = "",
    ) -> None:
        with self._lock:
            self._check_rollover()
            self._daily_requests += 1
            self._daily_tokens_in += tokens_in
            self._daily_tokens_out += tokens_out
            self._session_tokens[session_id] = (
                self._session_tokens.get(session_id, 0) + tokens_in + tokens_out
            )
            if model_name:
                self._model_requests[model_name] = (
                    self._model_requests.get(model_name, 0) + 1
                )
            self._save()

    def get_stats(self, session_id: Optional[str] = None) -> dict:
        with self._lock:
            self._check_rollover()
            return {
                "daily_requests": self._daily_requests,
                "daily_request_limit": self.daily_limit,
                "daily_request_pct": round(
                    self._daily_requests / max(self.daily_limit, 1) * 100, 1
                ),
                "daily_tokens_in": self._daily_tokens_in,
                "daily_tokens_out": self._daily_tokens_out,
                "session_tokens": (
                    self._session_tokens.get(session_id, 0) if session_id else 0
                ),
                "rpm_limit": RPM_LIMIT,
                "model_requests": dict(self._model_requests),
            }

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            self._session_tokens.pop(session_id, None)


# Singleton
usage_tracker = UsageTracker()
