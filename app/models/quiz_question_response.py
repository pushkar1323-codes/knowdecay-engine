"""
app/models/quiz_question_response.py
──────────────────────────────────────
Individual question-level responses within a quiz attempt.
Enables question-level difficulty analysis, Bloom's taxonomy tracking,
partial credit scoring, and future adaptive quiz generation.
"""

import uuid

from sqlalchemy import Boolean, Float, Integer, String, Text, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class QuizQuestionResponse(Base):
    __tablename__ = "quiz_question_responses"
    __table_args__ = (
        UniqueConstraint(
            "quiz_attempt_id", "question_number",
            name="uq_qqr_attempt_question",
        ),
        Index("ix_qqr_attempt_number", "quiz_attempt_id", "question_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    quiz_attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("quiz_attempts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_number: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # Order within the attempt (1-indexed)
    question_text: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Optional — may reference external question bank
    question_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="mcq"
    )  # 'mcq', 'true_false', 'short_answer', 'fill_blank', 'essay'
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    difficulty: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # Question difficulty (0.0–1.0)
    response_time_seconds: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # How long the student took
    confidence_rating: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # Self-reported confidence (0.0–1.0)
    bloom_level: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )  # 'remember', 'understand', 'apply', 'analyze', 'evaluate', 'create'
    marks_possible: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0
    )
    marks_earned: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )  # Supports partial credit
    # Extensible: selected_option, correct_answer, tags, hints_used, etc.
    response_metadata: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    quiz_attempt: Mapped["QuizAttempt"] = relationship(
        "QuizAttempt", back_populates="question_responses"
    )

    def __repr__(self) -> str:
        return (
            f"<QuizQuestionResponse attempt={self.quiz_attempt_id} "
            f"q={self.question_number} correct={self.is_correct}>"
        )
