from __future__ import annotations

"""In-process conversation history manager.

LIMITATION: History is stored in process memory (a plain dict). This means:
  - History is lost on server restart.
  - Multiple worker processes (e.g. gunicorn with --workers > 1) each maintain
    separate, non-shared history.

Upgrade path: replace ``self._sessions`` with a Redis hash
(e.g. ``redis.asyncio.Redis`` + JSON serialisation) so history is shared
across processes and survives restarts. The public interface (get_history,
add_turn, clear_session) would remain unchanged.
"""

import logging

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class MemoryManager:
    """In-memory conversation history per session with context-window trimming."""

    def __init__(self) -> None:
        self._sessions: dict[str, list[dict]] = {}

    def get_history(self, session_id: str) -> list[dict]:
        return self._sessions.get(session_id, [])

    def add_turn(self, session_id: str, role: str, content: str) -> None:
        """Append a turn and trim to the configured context window."""
        history = self._sessions.setdefault(session_id, [])
        history.append({"role": role, "content": content})

        max_turns = settings.context_window_turns
        if len(history) > max_turns:
            self._sessions[session_id] = history[-max_turns:]
            logger.debug(f"Trimmed session {session_id} to {max_turns} turns")

    def clear_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        logger.info(f"Cleared memory for session {session_id}")

    def session_exists(self, session_id: str) -> bool:
        return session_id in self._sessions

    def turn_count(self, session_id: str) -> int:
        return len(self._sessions.get(session_id, []))


# Singleton
memory_manager = MemoryManager()
