from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from middleware.auth import require_auth
from models.database import Message, Session, get_db
from services.llm_engine import llm_engine
from services.memory_manager import memory_manager
from services.reflection_engine import reflection_engine

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/sessions",
    tags=["sessions"],
    dependencies=[Depends(require_auth)],
)


@router.post("/start")
async def start_session(db: AsyncSession = Depends(get_db)):
    """Create a new conversation session."""
    session = Session()
    db.add(session)
    await db.commit()
    await db.refresh(session)

    logger.info(f"Session started: {session.id}")

    try:
        greeting = await llm_engine.generate_greeting(session_id=session.id)
        greeting_text = greeting.reply

        ai_msg = Message(
            session_id=session.id,
            role="assistant",
            content=greeting_text,
        )
        db.add(ai_msg)
        await db.commit()

        memory_manager.add_turn(session.id, "model", greeting_text)
    except Exception as exc:
        logger.error(f"Failed to generate greeting: {exc}")
        greeting_text = "Hey! How's it going? What's been on your mind lately?"

    return {
        "session_id": session.id,
        "started_at": session.started_at.isoformat(),
        "greeting": greeting_text,
    }


@router.post("/end")
async def end_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """End a session and trigger post-session reflection."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.ended_at = datetime.now(timezone.utc)
    await db.commit()

    memory_manager.clear_session(session_id)

    reflection_data = await reflection_engine.generate_reflection(db, session_id)

    logger.info(f"Session ended: {session_id}")
    return {
        "status": "ended",
        "reflection": reflection_data,
    }


@router.get("/")
async def list_sessions(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List all sessions, newest first."""
    result = await db.execute(
        select(Session)
        .order_by(Session.started_at.desc())
        .limit(limit)
        .offset(offset)
    )
    sessions = result.scalars().all()

    return [
        {
            "id": s.id,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            "topic": s.topic,
            "total_turns": s.total_turns,
            "fluency_score": s.fluency_score,
        }
        for s in sessions
    ]


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single session with its messages."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    msg_result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.timestamp)
    )
    messages = msg_result.scalars().all()

    return {
        "id": session.id,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "topic": session.topic,
        "total_turns": session.total_turns,
        "fluency_score": session.fluency_score,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp.isoformat() if m.timestamp else None,
                "correction": {
                    "original": m.correction_original,
                    "improved": m.correction_improved,
                    "note": m.correction_note,
                }
                if m.correction_original
                else None,
            }
            for m in messages
        ],
    }
