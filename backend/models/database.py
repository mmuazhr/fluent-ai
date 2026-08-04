from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, relationship

from config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=settings.debug)


class Base(DeclarativeBase):
    pass


def new_uuid() -> str:
    return str(uuid.uuid4())


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=new_uuid)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime, nullable=True)
    topic = Column(String, nullable=True)
    total_turns = Column(Integer, default=0)
    fluency_score = Column(Float, nullable=True)

    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    weaknesses = relationship("Weakness", back_populates="session", cascade="all, delete-orphan")
    reflection = relationship(
        "Reflection", back_populates="session", uselist=False, cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=new_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    correction_original = Column(Text, nullable=True)
    correction_improved = Column(Text, nullable=True)
    correction_note = Column(Text, nullable=True)

    session = relationship("Session", back_populates="messages")


class Weakness(Base):
    __tablename__ = "weaknesses"

    id = Column(String, primary_key=True, default=new_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    category = Column(String, nullable=False)
    pattern = Column(Text, nullable=False)
    frequency = Column(Integer, default=1)
    first_seen = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_seen = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    session = relationship("Session", back_populates="weaknesses")


class VocabGap(Base):
    __tablename__ = "vocab_gaps"

    id = Column(String, primary_key=True, default=new_uuid)
    word = Column(String, nullable=False)
    meaning = Column(Text, nullable=True)
    example = Column(Text, nullable=True)
    times_surfaced = Column(Integer, default=1)
    learned = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Reflection(Base):
    __tablename__ = "reflections"

    id = Column(String, primary_key=True, default=new_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), unique=True, nullable=False)
    session_title = Column(String, nullable=True)
    went_well = Column(Text, nullable=True)
    recurring_mistakes = Column(Text, nullable=True)
    vocab_to_learn = Column(Text, nullable=True)
    encouragement = Column(Text, nullable=True)
    fluency_score = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    session = relationship("Session", back_populates="reflection")


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_db_context():
    """Async context manager for manual (non-DI) database sessions."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session


async def get_db():
    """FastAPI dependency that yields an AsyncSession."""
    async with get_db_context() as session:
        yield session
