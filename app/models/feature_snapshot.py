"""
app/models/feature_snapshot.py
────────────────────────────────
Pre-computed ML feature vectors for each user×topic pair.
Foundation of the future feature store.

Updated by background feature generation jobs.
Consumed by future batch/online inference.

The `features` JSONB field stores a versioned feature vector.
`feature_version` enables backward-compatible schema evolution
and A/B testing of different feature sets.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class FeatureSnapshot(Base):
    __tablename__ = "feature_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "topic_id", "feature_version",
            name="uq_fs_user_topic_version",
        ),
        Index("ix_fs_user_topic", "user_id", "topic_id"),
        Index("ix_fs_version", "feature_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
    )
    features: Mapped[dict] = mapped_column(JSONB, nullable=False)
    feature_version: Mapped[str] = mapped_column(
        String(20), nullable=False, default="v1"
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<FeatureSnapshot user={self.user_id} topic={self.topic_id} "
            f"version={self.feature_version!r}>"
        )
