"""initial schema — all 11 tables

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-06-06

Creates:
  users, subjects, modules, chapters, topics, subtopics,
  study_sessions, quiz_attempts, revision_logs,
  memory_states, analytics_snapshots

Plus all indexes, constraints, and foreign keys.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. users ──────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("institution_id", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_institution_id", "users", ["institution_id"])

    # ── 2. subjects ───────────────────────────────────────────────────────────
    op.create_table(
        "subjects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("institution_id", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_subjects_institution_id", "subjects", ["institution_id"])

    # ── 3. modules ────────────────────────────────────────────────────────────
    op.create_table(
        "modules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "subject_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("subjects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_modules_subject_id", "modules", ["subject_id"])

    # ── 4. chapters ───────────────────────────────────────────────────────────
    op.create_table(
        "chapters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "module_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("modules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_chapters_module_id", "chapters", ["module_id"])

    # ── 5. topics ─────────────────────────────────────────────────────────────
    op.create_table(
        "topics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "chapter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chapters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("difficulty", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("importance_weight", sa.Float, nullable=False, server_default="1.0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_topics_chapter_id", "topics", ["chapter_id"])

    # ── 6. subtopics ──────────────────────────────────────────────────────────
    op.create_table(
        "subtopics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "topic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("topics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_subtopics_topic_id", "subtopics", ["topic_id"])

    # ── 7. study_sessions ─────────────────────────────────────────────────────
    op.create_table(
        "study_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "topic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("topics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("duration_minutes", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_study_sessions_user_id", "study_sessions", ["user_id"])
    op.create_index("ix_study_sessions_topic_id", "study_sessions", ["topic_id"])
    op.create_index("ix_study_sessions_created_at", "study_sessions", ["created_at"])
    op.create_index(
        "ix_study_session_user_topic_time",
        "study_sessions",
        ["user_id", "topic_id", "created_at"],
    )

    # ── 8. quiz_attempts ──────────────────────────────────────────────────────
    op.create_table(
        "quiz_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "topic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("topics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.5"),
        sa.Column(
            "attempted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_quiz_attempts_user_id", "quiz_attempts", ["user_id"])
    op.create_index("ix_quiz_attempts_topic_id", "quiz_attempts", ["topic_id"])
    op.create_index("ix_quiz_attempts_attempted_at", "quiz_attempts", ["attempted_at"])
    op.create_index(
        "ix_quiz_attempt_user_topic_time",
        "quiz_attempts",
        ["user_id", "topic_id", "attempted_at"],
    )

    # ── 9. revision_logs ──────────────────────────────────────────────────────
    op.create_table(
        "revision_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "topic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("topics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("retention_before", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("retention_after", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("stability_before", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("stability_after", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("revision_number", sa.Integer, nullable=False, server_default="1"),
        sa.Column("interval_days", sa.Float, nullable=True),
        sa.Column(
            "revised_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_revision_logs_user_id", "revision_logs", ["user_id"])
    op.create_index("ix_revision_logs_topic_id", "revision_logs", ["topic_id"])
    op.create_index("ix_revision_logs_event_type", "revision_logs", ["event_type"])
    op.create_index("ix_revision_logs_revised_at", "revision_logs", ["revised_at"])

    # ── 10. memory_states (MOST IMPORTANT TABLE) ──────────────────────────────
    op.create_table(
        "memory_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "topic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("topics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("retention_score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("stability_score", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("decay_rate", sa.Float, nullable=False, server_default="0.1"),
        sa.Column("confidence_score", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("revision_strength", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("revision_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "forgetting_probability", sa.Float, nullable=False, server_default="1.0"
        ),
        sa.Column("urgency_score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("last_revision_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_revision_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "topic_id", name="uq_memory_state_user_topic"),
    )
    op.create_index("ix_memory_states_user_id", "memory_states", ["user_id"])
    op.create_index("ix_memory_states_topic_id", "memory_states", ["topic_id"])
    op.create_index(
        "ix_memory_state_user_urgency",
        "memory_states",
        ["user_id", "urgency_score"],
    )
    op.create_index(
        "ix_memory_state_user_schedule",
        "memory_states",
        ["user_id", "next_revision_at"],
    )
    op.create_index(
        "ix_memory_state_user_retention",
        "memory_states",
        ["user_id", "retention_score"],
    )

    # ── 11. analytics_snapshots ───────────────────────────────────────────────
    op.create_table(
        "analytics_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("level", sa.String(50), nullable=False),
        sa.Column("ref_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("retention_avg", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("stability_avg", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("topics_total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("topics_at_risk", sa.Integer, nullable=False, server_default="0"),
        sa.Column("weakest_topics", postgresql.JSONB, nullable=True),
        sa.Column("retention_distribution", postgresql.JSONB, nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_analytics_snapshots_user_id", "analytics_snapshots", ["user_id"]
    )
    op.create_index("ix_analytics_snapshots_level", "analytics_snapshots", ["level"])
    op.create_index("ix_analytics_snapshots_ref_id", "analytics_snapshots", ["ref_id"])


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_table("analytics_snapshots")
    op.drop_table("memory_states")
    op.drop_table("revision_logs")
    op.drop_table("quiz_attempts")
    op.drop_table("study_sessions")
    op.drop_table("subtopics")
    op.drop_table("topics")
    op.drop_table("chapters")
    op.drop_table("modules")
    op.drop_table("subjects")
    op.drop_table("users")
