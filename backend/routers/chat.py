from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from middleware.auth import validate_ws_token
from models.database import Message, Session, get_db_context
from models.schemas import LLMResponse
from services.analytics_engine import analytics_engine
from services.llm_engine import llm_engine
from services.memory_manager import memory_manager
from services.usage_tracker import usage_tracker
from services.user_memory import user_memory

logger = logging.getLogger(__name__)
router = APIRouter()

_RATE_LIMITED_MSG = {
    "type": "error",
    "code": "rate_limited",
    "message": "Rate limit reached. Please wait a moment before sending another message.",
}


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket, token: str = "") -> None:
    """Real-time bidirectional chat over WebSocket.

    Auth: pass ``?token=<app_access_token>`` when APP_ACCESS_TOKEN is set
    (browsers cannot send custom headers on WebSocket upgrades).
    """
    if not await validate_ws_token(websocket, token):
        return

    await websocket.accept()
    logger.info("WebSocket client connected")

    try:
        while True:
            data = await websocket.receive_text()

            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = payload.get("type", "message")
            session_id = payload.get("session_id")
            content = payload.get("content", "").strip()

            if not session_id:
                await websocket.send_json({"type": "error", "message": "Missing session_id"})
                continue

            if msg_type == "message" and content:
                # Enforce per-minute rate limit before touching the LLM
                if not usage_tracker.check_rate_limit():
                    await websocket.send_json(_RATE_LIMITED_MSG)
                    continue

                await websocket.send_json({"type": "typing"})

                history = memory_manager.get_history(session_id)

                try:
                    response: LLMResponse = await llm_engine.chat(content, history, session_id)
                except Exception as exc:
                    logger.error(f"LLM error: {exc}")
                    await websocket.send_json({
                        "type": "error",
                        "message": "AI is temporarily unavailable. Please try again.",
                    })
                    continue

                memory_manager.add_turn(session_id, "user", content)
                memory_manager.add_turn(session_id, "model", response.reply)

                if response.learned_facts:
                    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    user_memory.update_from_insights(response.learned_facts, date_str)

                # Persist to DB using the context-manager helper (avoids generator leak)
                try:
                    async with get_db_context() as db:
                        user_msg = Message(
                            session_id=session_id,
                            role="user",
                            content=content,
                        )
                        db.add(user_msg)

                        ai_msg = Message(
                            session_id=session_id,
                            role="assistant",
                            content=response.reply,
                            correction_original=(
                                response.correction.original if response.correction else None
                            ),
                            correction_improved=(
                                response.correction.improved if response.correction else None
                            ),
                            correction_note=(
                                response.correction.note if response.correction else None
                            ),
                        )
                        db.add(ai_msg)

                        result = await db.execute(
                            select(Session).where(Session.id == session_id)
                        )
                        session_row = result.scalar_one_or_none()
                        if session_row:
                            session_row.total_turns = memory_manager.turn_count(session_id)

                        await db.commit()

                        await analytics_engine.process_observations(
                            db, session_id, response.observations
                        )
                except Exception as exc:
                    logger.error(f"DB persist error: {exc}")

                reply_event: dict = {
                    "type": "reply",
                    "text": response.reply,
                    "correction": None,
                }
                if response.correction:
                    reply_event["correction"] = {
                        "original": response.correction.original,
                        "improved": response.correction.improved,
                        "note": response.correction.note,
                    }

                await websocket.send_json(reply_event)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as exc:
        logger.error(f"WebSocket error: {exc}")
        try:
            await websocket.close()
        except Exception:
            pass
