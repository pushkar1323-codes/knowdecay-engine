"""
app/models/memory_state.py
───────────────────────────
THIS IS THE MOST IMPORTANT TABLE IN THE SYSTEM.

Each row represents the current memory state for one user × one topic pair.
The engine continuously evolves this state — it does NOT recalculate from scratch.

Architecture principle:
  • New quiz/session/revision event → recalibration_engine updates this row
  • Schedule generation reads from this row
  • Priority ranking reads from this row
  • Analytics aggregates from this row upward through the hierarchy

The unique constraint (user_id, topic_id) enforces one state row per pair.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime, Float, ForeignKey, Index, Integer, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class MemoryState(Base):
    __tablename__ = "memory_states"
    __table_args__ = (
        UniqueConstraint("user_id", "topic_id", name="uq_memory_state_user_topic"),
        # Priority engine: rank all topics for a user by urgency DESC
        Index("ix_memory_state_user_urgency", "user_id", "urgency_score"),
        # Scheduling engine: find overdue items for a user ordered by next_revision_at
        Index("ix_memory_state_user_schedule", "user_id", "next_revision_at"),
        # Analytics engine: aggregate retention for a user
        Index("ix_memory_state_user_retention", "user_id", "retention_score"),
        # Adaptive stability lookups
        Index("ix_memory_state_user_adaptive_stability", "user_id", "adaptive_stability"),
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

    # ── Retention Intelligence Fields ─────────────────────────────────────────
    # Probability that the learner can correctly recall this topic right now
    retention_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    # Memory stability in days — how long until retention drops to threshold
    stability_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0
    )
    # Forgetting curve decay rate (λ) — higher = faster forgetting
    decay_rate: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.1
    )
    # Blended confidence: self-reported + quiz-inferred
    confidence_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5
    )
    # Accumulated reinforcement from successful revisions (0.0 → ∞, diminishing returns)
    revision_strength: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    # Total number of revision events for this user × topic
    revision_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    # Probability that this topic has been substantially forgotten (0=safe, 1=forgotten)
    forgetting_probability: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0
    )
    # Composite urgency score — drives priority ranking
    urgency_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )

    # ── Adaptive Forgetting Curve Fields ──────────────────────────────────────
    # Base stability in days — evolves with each learning event (grows on success)
    base_stability: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0
    )
    # Running average quality of revision events (0–1)
    revision_quality: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5
    )
    # Learner-specific difficulty adjustment for this topic (0–1)
    difficulty_factor: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5
    )
    # Recent performance trajectory: −1.0 (declining) to +1.0 (improving)
    performance_trend: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )

    # ── Adaptive Stability Persistence ────────────────────────────────────────
    # Last-computed S_adaptive — the real stability used in R(t) = e^(−t/S)
    adaptive_stability: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0
    )
    # Average base_stability growth per revision event
    stability_growth_rate: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    # Days until retention drops to 50%
    half_life_days: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )

    # ── Decay Parameters ──────────────────────────────────────────────────────
    # Composite decay rate after all modifiers (stability × ML × reinforcement)
    effective_decay_rate: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.1
    )
    # Days until retention drops below critical threshold (0.3)
    time_to_critical: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    # Days until retention drops below revision threshold (0.7)
    days_until_target: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )

    # ── Reinforcement Behaviour ───────────────────────────────────────────────
    # Variance in revision quality (0 = perfectly consistent)
    quality_variance: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    # Number of revisions that actually improved retention
    effective_revision_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    # effective_revision_count / revision_count — what fraction of effort "stuck"
    revision_effectiveness_ratio: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    # Inter-revision timing regularity (0 = chaotic, 1 = perfectly regular)
    # Computed as exponential moving average over revision gaps
    time_pattern_regularity: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5
    )
    # |confidence − actual_performance| averaged over time
    confidence_calibration_error: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )

    # ── Retention History ─────────────────────────────────────────────────────
    # Highest retention ever achieved for this topic
    peak_retention: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    # Retention at the moment of the last revision (snapshot)
    retention_at_last_revision: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    # Count of times retention dropped below critical threshold (0.3)
    total_forgetting_events: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    # When retention last dropped below critical threshold
    last_forgetting_event_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Scheduling Timestamps ─────────────────────────────────────────────────
    last_revision_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_revision_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Auto-updated each time the engine writes to this row
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=_utcnow,      # Python-side onupdate for portability
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="memory_states")
    topic: Mapped["Topic"] = relationship("Topic", back_populates="memory_states")

    def __repr__(self) -> str:
        return (
            f"<MemoryState user={self.user_id} topic={self.topic_id} "
            f"retention={self.retention_score:.3f} "
            f"adaptive_s={self.adaptive_stability:.3f} "
            f"urgency={self.urgency_score:.3f} "
            f"revisions={self.revision_count}>"
        )

