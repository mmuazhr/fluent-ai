from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ── Inbound ────────────────────────────────────────────────

class TextMessage(BaseModel):
    session_id: str
    content: str


class AudioMessage(BaseModel):
    session_id: str
    audio_b64: str                  # base64-encoded WAV/WebM


class EndSessionRequest(BaseModel):
    session_id: str


# ── LLM Internal ───────────────────────────────────────────

class CorrectionPayload(BaseModel):
    original: str
    improved: str
    note: str


class ObservationsPayload(BaseModel):
    grammar_errors: list[str] = []
    filler_words: list[str] = []
    awkward_phrasing: list[str] = []
    vocab_gaps: list[str] = []
    confidence_signal: str = "medium"   # high | medium | low
    fluency_signal: str = "smooth"      # smooth | hesitant | choppy
    tone_appropriateness: str = "appropriate"


class LLMResponse(BaseModel):
    reply: str
    correction: Optional[CorrectionPayload] = None
    learned_facts: list[str] = []
    observations: ObservationsPayload = Field(default_factory=ObservationsPayload)


# ── Outbound (WebSocket events) ────────────────────────────

class ReplyEvent(BaseModel):
    event: str = "reply"
    session_id: str
    text: str
    audio_url: Optional[str] = None
    correction: Optional[CorrectionPayload] = None


class ReflectionEvent(BaseModel):
    event: str = "reflection"
    session_id: str
    session_title: Optional[str]
    went_well: list[str]
    recurring_mistakes: list[dict]
    vocab_to_learn: list[dict]
    encouragement: str
    fluency_score: float


# ── REST Response Models ────────────────────────────────────

class SessionOut(BaseModel):
    id: str
    started_at: datetime
    ended_at: Optional[datetime]
    topic: Optional[str]
    total_turns: int
    fluency_score: Optional[float]

    class Config:
        from_attributes = True


class WeaknessOut(BaseModel):
    category: str
    pattern: str
    frequency: int
    last_seen: datetime

    class Config:
        from_attributes = True


class AnalyticsSummary(BaseModel):
    total_sessions: int
    total_turns: int
    avg_fluency_score: Optional[float]
    top_weaknesses: list[WeaknessOut]
    vocab_gap_count: int
