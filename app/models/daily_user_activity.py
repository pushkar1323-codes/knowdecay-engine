"""
app/models/daily_user_activity.py
───────────────────────────────────
Per-user daily activity summary, pre-aggregated from study_sessions,
quiz_attempts, and revision_logs.

Powers activity heatmaps, streak tracking, productivity analytics,
and institution dashboards.

Write pattern: Upserted daily by background aggregation job,
or updated incrementally on each learning event.
"""

import uuid
from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DailyUserActivity(Base):
    __tablename__ = "daily_user_activity"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "activity_date",
            name="uq_dua_user_date",
        ),
        Index("ix_dua_user_date", "user_id", "activity_date"),
        Index("ix_dua_date", "activity_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    activity_date: Mapped[date] = mapped_column(Date, nullable=False)

    # ── Study metrics ─────────────────────────────────────────────────────────
    study_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active_study_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sessions_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sessions_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Quiz metrics ──────────────────────────────────────────────────────────
    quizzes_taken: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quiz_avg_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Revision metrics ──────────────────────────────────────────────────────
    revisions_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Topic metrics ─────────────────────────────────────────────────────────
    topics_studied: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    topics_mastered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    topics_at_risk: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Event metrics ─────────────────────────────────────────────────────────
    learning_events_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return (
            f"<DailyUserActivity user={self.user_id} "
            f"date={self.activity_date} study={self.study_minutes}min>"
        )
