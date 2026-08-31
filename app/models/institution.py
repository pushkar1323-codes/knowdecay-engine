"""
app/models/institution.py
───────────────────────────
First-class tenant entity representing a school, university,
coaching institute, or enterprise organization.

Supports two operating modes:
  • Standalone KnowDecay Platform — users have no institution
  • Institution/Enterprise Mode — users belong to an institution tenant
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Institution(Base):
    __tablename__ = "institutions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Extensible config: timezone, branding, feature flags, subscription tier
    settings: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    users: Mapped[list["User"]] = relationship(
        "User", back_populates="institution"
    )
    courses: Mapped[list["Course"]] = relationship(
        "Course", back_populates="institution"
    )
    subjects: Mapped[list["Subject"]] = relationship(
        "Subject", back_populates="institution"
    )

    def __repr__(self) -> str:
        return f"<Institution id={self.id} slug={self.slug!r}>"
