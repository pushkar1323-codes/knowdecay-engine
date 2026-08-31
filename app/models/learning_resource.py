"""
app/models/learning_resource.py
─────────────────────────────────
Study materials attached to topics or subtopics.
Represents videos, articles, documents, exercises, and external links.

Hierarchy position:
    Topic → LearningResource
    Subtopic → LearningResource (optional finer scope)
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class LearningResource(Base):
    __tablename__ = "learning_resources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subtopic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subtopics.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    resource_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # 'video', 'article', 'document', 'exercise', 'link', 'note'
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Extensible: duration, page_count, difficulty, author, storage_key, etc.
    resource_metadata: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    topic: Mapped["Topic"] = relationship("Topic", back_populates="learning_resources")

    def __repr__(self) -> str:
        return f"<LearningResource id={self.id} type={self.resource_type!r} title={self.title!r}>"
