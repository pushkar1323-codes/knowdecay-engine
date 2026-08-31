"""
app/models/learning_event.py
──────────────────────────────
Extensible event log capturing all significant learning activities.
Primary data source for future ML training and analytics pipelines.

Design:
  • event_type is a plain string (not enum) — new types added without migration
  • payload is JSONB — event-specific structured data, no schema change needed
  • ref_id + ref_type enable polymorphic linking to any entity
  • Events use dot-notation namespacing: domain.entity.action
    e.g., 'learning.session.started', 'quiz.submitted', 'topic.mastered'
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class LearningEvent(Base):
    __tablename__ = "learning_events"
    __table_args__ = (
        # Analytics: fetch events for a user by type in time order
        Index("ix_event_user_type_time", "user_id", "event_type", "occurred_at"),
        # Time-range queries across all users
        Index("ix_event_occurred", "occurred_at"),
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
    event_type: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    # Context entity — the topic this event relates to (if any)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Polymorphic reference to any entity (session, quiz, revision, etc.)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    ref_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # 'study_session', 'quiz_attempt', 'revision_log', etc.
    # Event-specific structured data
    payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="learning_events")

    def __repr__(self) -> str:
        return (
            f"<LearningEvent type={self.event_type!r} "
            f"user={self.user_id} at={self.occurred_at}>"
        )
