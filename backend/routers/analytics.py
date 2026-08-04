from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from middleware.auth import require_auth
from models.database import Reflection, Session, VocabGap, Weakness, get_db
from services.usage_tracker import usage_tracker

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
    dependencies=[Depends(require_auth)],
)


@router.get("/usage")
async def get_usage(session_id: Optional[str] = None):
    """Return current free-tier usage stats."""
    return usage_tracker.get_stats(session_id)


@router.get("/summary")
async def get_analytics_summary(db: AsyncSession = Depends(get_db)):
    """Aggregated analytics summary."""
    result = await db.execute(select(func.count(Session.id)))
    total_sessions = result.scalar() or 0

    result = await db.execute(select(func.sum(Session.total_turns)))
    total_turns = result.scalar() or 0

    result = await db.execute(
        select(func.avg(Session.fluency_score)).where(Session.fluency_score.isnot(None))
    )
    avg_fluency = result.scalar()
    avg_fluency = round(avg_fluency, 1) if avg_fluency else None

    result = await db.execute(
        select(
            Weakness.category,
            Weakness.pattern,
            func.sum(Weakness.frequency).label("total_freq"),
        )
        .group_by(Weakness.category, Weakness.pattern)
        .order_by(func.sum(Weakness.frequency).desc())
        .limit(10)
    )
    top_weaknesses = [
        {"category": row[0], "pattern": row[1], "frequency": row[2]}
        for row in result.all()
    ]

    result = await db.execute(
        select(func.count(VocabGap.id)).where(VocabGap.learned == False)  # noqa: E712
    )
    vocab_gap_count = result.scalar() or 0

    return {
        "total_sessions": total_sessions,
        "total_turns": total_turns,
        "avg_fluency_score": avg_fluency,
        "top_weaknesses": top_weaknesses,
        "vocab_gap_count": vocab_gap_count,
    }


@router.get("/weaknesses")
async def get_weaknesses(db: AsyncSession = Depends(get_db)):
    """All weakness records, sorted by frequency."""
    result = await db.execute(
        select(
            Weakness.category,
            Weakness.pattern,
            func.sum(Weakness.frequency).label("total_freq"),
            func.max(Weakness.last_seen).label("last_seen"),
        )
        .group_by(Weakness.category, Weakness.pattern)
        .order_by(func.sum(Weakness.frequency).desc())
    )

    return [
        {
            "category": row[0],
            "pattern": row[1],
            "frequency": row[2],
            "last_seen": row[3].isoformat() if row[3] else None,
        }
        for row in result.all()
    ]


@router.get("/vocab")
async def get_vocab_gaps(
    learned: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Vocab gap list, filterable by learned status."""
    query = select(VocabGap).order_by(VocabGap.times_surfaced.desc())
    if not learned:
        query = query.where(VocabGap.learned == False)  # noqa: E712

    result = await db.execute(query)
    gaps = result.scalars().all()

    return [
        {
            "id": g.id,
            "word": g.word,
            "meaning": g.meaning,
            "example": g.example,
            "times_surfaced": g.times_surfaced,
            "learned": g.learned,
        }
        for g in gaps
    ]


@router.patch("/vocab/{vocab_id}/learned")
async def mark_vocab_learned(
    vocab_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Toggle a vocab item as learned."""
    result = await db.execute(select(VocabGap).where(VocabGap.id == vocab_id))
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Vocab item not found")

    item.learned = not item.learned
    await db.commit()

    return {"id": item.id, "word": item.word, "learned": item.learned}


@router.get("/sessions/{session_id}/reflection")
async def get_session_reflection(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get reflection for a specific session."""
    result = await db.execute(
        select(Reflection).where(Reflection.session_id == session_id)
    )
    reflection = result.scalar_one_or_none()

    if not reflection:
        raise HTTPException(status_code=404, detail="Reflection not found")

    return {
        "session_id": reflection.session_id,
        "session_title": reflection.session_title,
        "went_well": json.loads(reflection.went_well) if reflection.went_well else [],
        "recurring_mistakes": (
            json.loads(reflection.recurring_mistakes) if reflection.recurring_mistakes else []
        ),
        "vocab_to_learn": (
            json.loads(reflection.vocab_to_learn) if reflection.vocab_to_learn else []
        ),
        "encouragement": reflection.encouragement,
        "fluency_score": reflection.fluency_score,
    }
