from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

MEMORY_FILE = Path(__file__).parent.parent / "memory" / "user_profile.json"
MAX_FACTS: int = 30  # cap to prevent unbounded profile growth

_lock = threading.Lock()


class UserMemory:
    """Persistent user profile that grows across sessions.

    File read-modify-write cycles are serialised with a module-level Lock
    so concurrent async tasks (via asyncio.to_thread) are safe.
    """

    def load(self) -> dict:
        if MEMORY_FILE.exists():
            try:
                return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"facts": []}

    def save(self, profile: dict) -> None:
        MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        MEMORY_FILE.write_text(
            json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def update_from_insights(self, insights: list[str], date_str: str) -> None:
        """Merge new personal insights into the profile.

        - Case-insensitive deduplication on normalised text.
        - Profile facts are capped at MAX_FACTS (most-recent retained).
        """
        if not insights:
            return

        with _lock:
            profile = self.load()
            existing_facts: list[dict] = profile.get("facts", [])
            existing_normalised = {f["fact"].lower().strip() for f in existing_facts}

            new_facts = [
                {"fact": insight, "learned": date_str}
                for insight in insights
                if insight.strip() and insight.lower().strip() not in existing_normalised
            ]

            if not new_facts:
                return

            combined = existing_facts + new_facts
            # Keep only the most-recent MAX_FACTS entries
            capped = combined[-MAX_FACTS:] if len(combined) > MAX_FACTS else combined

            updated_profile = {**profile, "facts": capped, "updated_at": date_str}
            self.save(updated_profile)
            logger.info(f"User memory updated with {len(new_facts)} new facts")

    def to_context_string(self) -> str:
        """Format memory as a context block for the system prompt."""
        profile = self.load()
        facts = profile.get("facts", [])
        if not facts:
            return ""

        lines = ["## What You Already Know About the User"]
        for f in facts:
            lines.append(f"- {f['fact']}")
        lines.append(
            "\nUse this naturally in conversation — don't announce it, "
            "just reference it when relevant. "
            "If you know their name, use it occasionally."
        )
        return "\n".join(lines)


# Singleton
user_memory = UserMemory()
