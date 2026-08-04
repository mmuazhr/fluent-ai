from __future__ import annotations
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Weakness, VocabGap
from models.schemas import ObservationsPayload

logger = logging.getLogger(__name__)


class AnalyticsEngine:
    """Processes LLM observations and persists weakness patterns to DB."""

    CATEGORY_MAP = {
        "grammar_errors": "grammar",
        "filler_words": "filler",
        "awkward_phrasing": "phrasing",
        "vocab_gaps": "vocab",
    }

    async def process_observations(
        self,
        db: AsyncSession,
        session_id: str,
        observations: ObservationsPayload,
    ):
        """Parse observations and upsert weakness records."""

        now = datetime.now(timezone.utc)

        # Process list-based categories
        for field_name, category in self.CATEGORY_MAP.items():
            items = getattr(observations, field_name, [])
            for pattern in items:
                if not pattern or not pattern.strip():
                    continue
                await self._upsert_weakness(db, session_id, category, pattern.strip(), now)

        # Process signal-based categories
        if observations.confidence_signal == "low":
            await self._upsert_weakness(db, session_id, "confidence", "low confidence detected", now)

        if observations.fluency_signal in ("hesitant", "choppy"):
            await self._upsert_weakness(db, session_id, "fluency", f"{observations.fluency_signal} speech pattern", now)

        if observations.tone_appropriateness != "appropriate":
            await self._upsert_weakness(db, session_id, "tone", f"tone: {observations.tone_appropriateness}", now)

        # Process vocab gaps separately into vocab_gaps table
        for word in observations.vocab_gaps:
            if word and word.strip():
                await self._upsert_vocab_gap(db, word.strip())

        await db.commit()

    async def _upsert_weakness(
        self,
        db: AsyncSession,
        session_id: str,
        category: str,
        pattern: str,
        now: datetime,
    ):
        """Increment frequency if pattern exists, else create new."""
        result = await db.execute(
            select(Weakness).where(
                Weakness.session_id == session_id,
                Weakness.category == category,
                Weakness.pattern == pattern,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.frequency += 1
            existing.last_seen = now
        else:
            db.add(Weakness(
                session_id=session_id,
                category=category,
                pattern=pattern,
                frequency=1,
                first_seen=now,
                last_seen=now,
            ))

    async def _upsert_vocab_gap(self, db: AsyncSession, word: str):
        """Track vocab gaps across all sessions."""
        result = await db.execute(
            select(VocabGap).where(VocabGap.word == word)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.times_surfaced += 1
        else:
            db.add(VocabGap(word=word))

    async def get_session_weaknesses_summary(
        self,
        db: AsyncSession,
        session_id: str,
    ) -> str:
        """Build a text summary of weaknesses for reflection prompt."""
        result = await db.execute(
            select(Weakness).where(Weakness.session_id == session_id)
        )
        weaknesses = result.scalars().all()

        if not weaknesses:
            return "No significant weaknesses detected this session."

        lines = []
        for w in weaknesses:
            lines.append(f"- [{w.category}] {w.pattern} (frequency: {w.frequency})")
        return "\n".join(lines)


# Singleton
analytics_engine = AnalyticsEngine()
