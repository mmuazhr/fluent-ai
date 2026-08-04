from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Session, Message, Reflection
from models.schemas import LLMResponse
from services.llm_engine import llm_engine
from services.analytics_engine import analytics_engine
from services.vault_writer import vault_writer
from services.user_memory import user_memory
from prompts.reflection_prompt import REFLECTION_PROMPT

logger = logging.getLogger(__name__)

MIN_TURNS_FOR_REFLECTION = 4  # Skip reflection on very short sessions


class ReflectionEngine:
    """Generates post-session reflection using Gemini."""

    async def generate_reflection(
        self,
        db: AsyncSession,
        session_id: str,
    ) -> Optional[dict]:
        """Generate and save a reflection for the completed session."""

        # Fetch session
        result = await db.execute(
            select(Session).where(Session.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            logger.warning(f"Session {session_id} not found for reflection")
            return None

        # Fetch messages
        result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.timestamp)
        )
        messages = result.scalars().all()

        if len(messages) < MIN_TURNS_FOR_REFLECTION:
            logger.info(f"Session {session_id} too short ({len(messages)} msgs), skipping reflection")
            return None

        # Build transcript
        transcript_lines = []
        for msg in messages:
            role_label = "User" if msg.role == "user" else "AI"
            transcript_lines.append(f"{role_label}: {msg.content}")
        transcript = "\n".join(transcript_lines)

        # Get weakness summary
        weaknesses_summary = await analytics_engine.get_session_weaknesses_summary(db, session_id)

        # Call Gemini for reflection
        try:
            reflection_data = await llm_engine.generate_reflection(
                transcript=transcript,
                weaknesses_summary=weaknesses_summary,
                reflection_prompt=REFLECTION_PROMPT,
            )
        except Exception as e:
            logger.error(f"Failed to generate reflection: {e}")
            return None

        if not reflection_data:
            return None

        # Save to DB
        reflection = Reflection(
            session_id=session_id,
            session_title=reflection_data.get("session_title"),
            went_well=json.dumps(reflection_data.get("went_well", [])),
            recurring_mistakes=json.dumps(reflection_data.get("recurring_mistakes", [])),
            vocab_to_learn=json.dumps(reflection_data.get("vocab_to_learn", [])),
            encouragement=reflection_data.get("encouragement", ""),
            fluency_score=reflection_data.get("fluency_score"),
        )
        db.add(reflection)

        # Update session fluency score
        if reflection_data.get("fluency_score"):
            session.fluency_score = reflection_data["fluency_score"]
            session.topic = reflection_data.get("session_title")

        await db.commit()

        # Update persistent user memory
        date_str = session.started_at.strftime("%Y-%m-%d") if session.started_at else "unknown"
        user_memory.update_from_insights(
            reflection_data.get("personal_insights", []),
            date_str,
        )

        # Write to Obsidian vault
        vault_writer.write_session(
            session_date=session.started_at,
            reflection_data=reflection_data,
            transcript=transcript,
        )

        logger.info(f"Reflection generated for session {session_id}")
        return reflection_data


# Singleton
reflection_engine = ReflectionEngine()
