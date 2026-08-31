"""
app/models/revision_log.py
────────────────────────────
Tracks every individual revision event for a user × topic pair.

This table answers the "last_revision" requirement from the master spec:
  • What was the last revision event for this topic?
  • How many revisions happened and when?
  • What was the quality of each revision?

The recalibration_engine reads the latest revision_log to update memory_state.
The scheduling_engine uses revision history to refine interval calculations.

Design decision — Why a separate table from memory_states?
  memory_states holds the CURRENT evolved state (one row per user×topic).
  revision_logs holds the HISTORY of every revision event (many rows per user×topic).
  This separation keeps memory_state reads fast (single row lookup)
  while preserving full audit trail for analytics and ML-readiness.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class RevisionLog(Base):
    __tablename__ = "revision_logs"
    __table_args__ = (
        # Recalibration engine: fetch revision history for a user×topic
        Index("ix_revision_log_user_topic_time", "user_id", "topic_id", "revised_at"),
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

    # ── Revision event data ───────────────────────────────────────────────────
    # What triggered this revision entry
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # 'quiz_submitted' | 'revision_completed' | 'study_session' | 'inactivity_decay'

    # Snapshot of scores AT THE TIME of this revision (for audit trail)
    retention_before: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )  # retention_score before this event
    retention_after: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )  # retention_score after recalibration
    stability_before: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0
    )
    stability_after: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0
    )

    # Optional — score of the quiz/revision that triggered this event
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Which revision number was this for this user×topic pair? (1-indexed)
    revision_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )

    # Computed interval since the previous revision (in days)
    interval_days: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # NULL for first revision

    # ── Enhanced revision tracking (Phase 16 — all nullable) ──────────────────
    revision_method: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # 'scheduled', 'manual', 'adaptive', 'spaced_repetition'
    revision_duration_minutes: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # how long the revision took
    completion_status: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )  # 'completed', 'partial', 'skipped'
    scheduler_decision: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # 'on_time', 'overdue', 'early'
    user_response: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # 'easy', 'good', 'hard', 'again'

    revised_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="revision_logs")
    topic: Mapped["Topic"] = relationship("Topic", back_populates="revision_logs")

    def __repr__(self) -> str:
        return (
            f"<RevisionLog user={self.user_id} topic={self.topic_id} "
            f"event={self.event_type!r} "
            f"retention={self.retention_before:.3f}→{self.retention_after:.3f} "
            f"#{self.revision_number}>"
        )
