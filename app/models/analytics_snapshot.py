"""
app/models/analytics_snapshot.py
──────────────────────────────────
Stores pre-computed hierarchical analytics at any level of the knowledge hierarchy.

level values: 'subject' | 'module' | 'chapter' | 'topic'
ref_id: the UUID of the entity at that level

The analytics_engine populates this table on-demand.
Downstream consumers (institutional dashboards, API responses) read from here
rather than re-aggregating on every request.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class AnalyticsSnapshot(Base):
    __tablename__ = "analytics_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Hierarchy context
    level: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # 'subject' | 'module' | 'chapter' | 'topic'
    ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )  # UUID of the entity at this level

    # Aggregated retention metrics
    retention_avg: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    stability_avg: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    topics_total: Mapped[int] = mapped_column(
        nullable=False, default=0
    )
    topics_at_risk: Mapped[int] = mapped_column(
        nullable=False, default=0
    )  # topics where retention_score < 0.4

    # JSONB blobs for rich analytics data
    weakest_topics: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )  # [{topic_id, name, retention_score}, ...]
    retention_distribution: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )  # histogram buckets for heatmap rendering

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="analytics_snapshots")

    def __repr__(self) -> str:
        return (
            f"<AnalyticsSnapshot user={self.user_id} "
            f"level={self.level!r} ref={self.ref_id} "
            f"retention_avg={self.retention_avg:.3f}>"
        )
