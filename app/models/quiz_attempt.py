"""
app/models/quiz_attempt.py
───────────────────────────
A quiz attempt is the STRONGEST signal for the retention engine.
• score       — objective recall quality (0.0 = total failure, 1.0 = perfect)
• confidence  — self-reported certainty (0.0 = guessing, 1.0 = very sure)

The combination of score + confidence informs:
  • retention_engine  → retention and stability updates
  • decay_engine      → calibrated decay rate
  • recalibration_engine → urgency re-weighting

Enhanced with richer quiz tracking: attempt numbering, timing, marks,
Bloom's taxonomy, and extensible metadata. All new columns are nullable
for backward compatibility.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"
    __table_args__ = (
        # Recalibration engine: fetch latest quiz for a user×topic
        Index("ix_quiz_attempt_user_topic_time", "user_id", "topic_id", "attempted_at"),
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
    score: Mapped[float] = mapped_column(
        Float, nullable=False
    )  # 0.0 – 1.0  (objective recall quality)
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5
    )  # 0.0 – 1.0  (self-reported certainty)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # ── Enhanced quiz tracking (Phase 16 — all nullable) ──────────────────────
    attempt_number: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # which attempt for this user×topic? (1st, 2nd, etc.)
    time_taken_seconds: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # total time to complete the quiz
    total_marks: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # maximum possible marks
    earned_marks: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # marks achieved (supports partial credit)
    bloom_level: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )  # overall quiz Bloom's taxonomy level
    question_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # number of questions in this attempt
    quiz_metadata: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )  # quiz type, source, tags, adaptive difficulty params

    # ── Relationships ─────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="quiz_attempts")
    topic: Mapped["Topic"] = relationship("Topic", back_populates="quiz_attempts")
    question_responses: Mapped[list["QuizQuestionResponse"]] = relationship(
        "QuizQuestionResponse", back_populates="quiz_attempt", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<QuizAttempt id={self.id} "
            f"user={self.user_id} topic={self.topic_id} "
            f"score={self.score:.2f} confidence={self.confidence:.2f}>"
        )
