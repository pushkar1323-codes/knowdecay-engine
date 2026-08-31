"""
app/models/hierarchy.py
────────────────────────
Full 5-level knowledge hierarchy ORM models:

    Subject → Module → Chapter → Topic → Subtopic

Retention is calculated at the Topic level (memory_states.topic_id)
and aggregated upward through this hierarchy for analytics.

Topic carries the two engine-critical fields:
  • difficulty        (0.0–1.0) — affects decay rate and priority score
  • importance_weight (0.0–N)  — scales urgency when exam is nearby
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Multi-tenant FK — subjects belong to an institution
    institution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Curriculum FK — subjects belong to a course
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    institution: Mapped["Institution | None"] = relationship(
        "Institution", back_populates="subjects"
    )
    course: Mapped["Course | None"] = relationship(
        "Course", back_populates="subjects"
    )
    modules: Mapped[list["Module"]] = relationship(
        "Module", back_populates="subject", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Subject id={self.id} name={self.name!r}>"


class Module(Base):
    __tablename__ = "modules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    subject: Mapped["Subject"] = relationship("Subject", back_populates="modules")
    chapters: Mapped[list["Chapter"]] = relationship(
        "Chapter", back_populates="module", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Module id={self.id} name={self.name!r}>"


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    module_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("modules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    module: Mapped["Module"] = relationship("Module", back_populates="chapters")
    topics: Mapped[list["Topic"]] = relationship(
        "Topic", back_populates="chapter", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Chapter id={self.id} name={self.name!r}>"


class Topic(Base):
    """
    The primary unit of retention tracking.
    All memory_states, quiz_attempts, and study_sessions reference a topic_id.
    """

    __tablename__ = "topics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Engine-critical fields
    difficulty: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5
    )  # 0.0 (easy) → 1.0 (very hard)
    importance_weight: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0
    )  # scales urgency; higher = prioritised more under exam pressure
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    chapter: Mapped["Chapter"] = relationship("Chapter", back_populates="topics")
    subtopics: Mapped[list["Subtopic"]] = relationship(
        "Subtopic", back_populates="topic", cascade="all, delete-orphan"
    )
    study_sessions: Mapped[list["StudySession"]] = relationship(
        "StudySession", back_populates="topic", cascade="all, delete-orphan", passive_deletes=True
    )
    quiz_attempts: Mapped[list["QuizAttempt"]] = relationship(
        "QuizAttempt", back_populates="topic", cascade="all, delete-orphan", passive_deletes=True
    )
    memory_states: Mapped[list["MemoryState"]] = relationship(
        "MemoryState", back_populates="topic", cascade="all, delete-orphan", passive_deletes=True
    )
    revision_logs: Mapped[list["RevisionLog"]] = relationship(
        "RevisionLog", back_populates="topic", cascade="all, delete-orphan", passive_deletes=True
    )
    learning_resources: Mapped[list["LearningResource"]] = relationship(
        "LearningResource", back_populates="topic", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return (
            f"<Topic id={self.id} name={self.name!r} "
            f"difficulty={self.difficulty} weight={self.importance_weight}>"
        )


class Subtopic(Base):
    __tablename__ = "subtopics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    topic: Mapped["Topic"] = relationship("Topic", back_populates="subtopics")

    def __repr__(self) -> str:
        return f"<Subtopic id={self.id} name={self.name!r}>"
