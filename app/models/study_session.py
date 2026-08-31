"""
app/models/study_session.py
────────────────────────────
A study session records that a user studied a topic for a duration.
The recalibration engine uses study sessions as a 'learning exposure' event
that modestly strengthens memory state without the full boost of a quiz.

Enhanced with rich session tracking: timing, completion, device/platform,
and extensible metadata. All new columns are nullable for backward
compatibility with existing code.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Float, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class StudySession(Base):
    __tablename__ = "study_sessions"
    __table_args__ = (
        # Recalibration engine: fetch sessions for a user×topic in time order
        Index("ix_study_session_user_topic_time", "user_id", "topic_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    duration_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )  # total study time in minutes

    # ── Enhanced session tracking (Phase 16 — all nullable) ───────────────────
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # explicit start time
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # when session ended
    active_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # active study time (excluding idle)
    idle_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # detected idle time
    completion_status: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )  # 'completed', 'abandoned', 'in_progress'
    device_type: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )  # 'desktop', 'mobile', 'tablet'
    platform: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # 'web', 'ios', 'android', 'api'
    session_metadata: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )  # pages viewed, resources accessed, notes taken

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    user: Mapped["User"] = relationship("User", back_populates="study_sessions")
    topic: Mapped["Topic"] = relationship("Topic", back_populates="study_sessions")

    def __repr__(self) -> str:
        return (
            f"<StudySession id={self.id} "
            f"user={self.user_id} topic={self.topic_id} "
            f"duration={self.duration_minutes}min>"
        )
