"""
Phase 16 — Learning Data & Analytics Foundation
Creates 9 new tables, enhances 3 existing tables, converts
institution_id columns from String to UUID FK.

Revision ID: 0006
Revises: 0005
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Phase A: New tables (no dependencies on existing data) ────────────────

    # 1. institutions
    op.create_table(
        "institutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("settings", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_institution_slug", "institutions", ["slug"], unique=True)
    op.create_index("ix_institution_is_active", "institutions", ["is_active"])

    # 2. courses
    op.create_table(
        "courses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_course_institution", "courses", ["institution_id"])
    op.create_index("ix_course_code", "courses", ["code"])

    # 3. course_enrollments
    op.create_table(
        "course_enrollments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(30), nullable=False, server_default="student"),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "course_id", name="uq_enrollment_user_course"),
    )
    op.create_index("ix_enrollment_user", "course_enrollments", ["user_id"])
    op.create_index("ix_enrollment_course", "course_enrollments", ["course_id"])
    op.create_index("ix_enrollment_course_role", "course_enrollments", ["course_id", "role"])

    # 4. learning_resources
    op.create_table(
        "learning_resources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subtopic_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("resource_metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subtopic_id"], ["subtopics.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_resource_topic", "learning_resources", ["topic_id"])
    op.create_index("ix_resource_subtopic", "learning_resources", ["subtopic_id"])
    op.create_index("ix_resource_type", "learning_resources", ["resource_type"])

    # 5. learning_events
    op.create_table(
        "learning_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ref_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ref_type", sa.String(50), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_event_user", "learning_events", ["user_id"])
    op.create_index("ix_event_type", "learning_events", ["event_type"])
    op.create_index("ix_event_topic", "learning_events", ["topic_id"])
    op.create_index("ix_event_ref", "learning_events", ["ref_id"])
    op.create_index("ix_event_occurred", "learning_events", ["occurred_at"])
    op.create_index("ix_event_user_type_time", "learning_events", ["user_id", "event_type", "occurred_at"])

    # 6. quiz_question_responses
    op.create_table(
        "quiz_question_responses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("quiz_attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_number", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=True),
        sa.Column("question_type", sa.String(50), nullable=False, server_default="mcq"),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("difficulty", sa.Float(), nullable=True),
        sa.Column("response_time_seconds", sa.Float(), nullable=True),
        sa.Column("confidence_rating", sa.Float(), nullable=True),
        sa.Column("bloom_level", sa.String(30), nullable=True),
        sa.Column("marks_possible", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("marks_earned", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("response_metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.ForeignKeyConstraint(["quiz_attempt_id"], ["quiz_attempts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("quiz_attempt_id", "question_number", name="uq_qqr_attempt_question"),
    )
    op.create_index("ix_qqr_attempt", "quiz_question_responses", ["quiz_attempt_id"])
    op.create_index("ix_qqr_attempt_number", "quiz_question_responses", ["quiz_attempt_id", "question_number"])

    # 7. retention_time_series
    op.create_table(
        "retention_time_series",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("retention_score", sa.Float(), nullable=False),
        sa.Column("stability_score", sa.Float(), nullable=False),
        sa.Column("decay_rate", sa.Float(), nullable=False),
        sa.Column("revision_count", sa.Integer(), nullable=False),
        sa.Column("days_since_last_revision", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "topic_id", "snapshot_date", name="uq_rts_user_topic_date"),
    )
    op.create_index("ix_rts_user_topic_date", "retention_time_series", ["user_id", "topic_id", "snapshot_date"])
    op.create_index("ix_rts_date", "retention_time_series", ["snapshot_date"])

    # 8. daily_user_activity
    op.create_table(
        "daily_user_activity",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("activity_date", sa.Date(), nullable=False),
        sa.Column("study_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active_study_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sessions_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sessions_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quizzes_taken", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quiz_avg_score", sa.Float(), nullable=True),
        sa.Column("revisions_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("topics_studied", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("topics_mastered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("topics_at_risk", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("learning_events_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "activity_date", name="uq_dua_user_date"),
    )
    op.create_index("ix_dua_user_date", "daily_user_activity", ["user_id", "activity_date"])
    op.create_index("ix_dua_date", "daily_user_activity", ["activity_date"])

    # 9. feature_snapshots
    op.create_table(
        "feature_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("features", postgresql.JSONB(), nullable=False),
        sa.Column("feature_version", sa.String(20), nullable=False, server_default="v1"),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "topic_id", "feature_version", name="uq_fs_user_topic_version"),
    )
    op.create_index("ix_fs_user_topic", "feature_snapshots", ["user_id", "topic_id"])
    op.create_index("ix_fs_version", "feature_snapshots", ["feature_version"])

    # ── Phase B: Add nullable columns to existing tables ──────────────────────

    # study_sessions — enhanced session tracking
    op.add_column("study_sessions", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("study_sessions", sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("study_sessions", sa.Column("active_minutes", sa.Integer(), nullable=True))
    op.add_column("study_sessions", sa.Column("idle_minutes", sa.Integer(), nullable=True))
    op.add_column("study_sessions", sa.Column("completion_status", sa.String(30), nullable=True))
    op.add_column("study_sessions", sa.Column("device_type", sa.String(30), nullable=True))
    op.add_column("study_sessions", sa.Column("platform", sa.String(50), nullable=True))
    op.add_column("study_sessions", sa.Column("session_metadata", postgresql.JSONB(), nullable=True))

    # quiz_attempts — enhanced quiz tracking
    op.add_column("quiz_attempts", sa.Column("attempt_number", sa.Integer(), nullable=True))
    op.add_column("quiz_attempts", sa.Column("time_taken_seconds", sa.Integer(), nullable=True))
    op.add_column("quiz_attempts", sa.Column("total_marks", sa.Float(), nullable=True))
    op.add_column("quiz_attempts", sa.Column("earned_marks", sa.Float(), nullable=True))
    op.add_column("quiz_attempts", sa.Column("bloom_level", sa.String(30), nullable=True))
    op.add_column("quiz_attempts", sa.Column("question_count", sa.Integer(), nullable=True))
    op.add_column("quiz_attempts", sa.Column("quiz_metadata", postgresql.JSONB(), nullable=True))

    # revision_logs — enhanced revision tracking
    op.add_column("revision_logs", sa.Column("revision_method", sa.String(50), nullable=True))
    op.add_column("revision_logs", sa.Column("revision_duration_minutes", sa.Float(), nullable=True))
    op.add_column("revision_logs", sa.Column("completion_status", sa.String(30), nullable=True))
    op.add_column("revision_logs", sa.Column("scheduler_decision", sa.String(50), nullable=True))
    op.add_column("revision_logs", sa.Column("user_response", sa.String(50), nullable=True))

    # subjects — add course_id FK
    op.add_column("subjects", sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_subjects_course_id", "subjects", "courses", ["course_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_subjects_course_id", "subjects", ["course_id"])

    # ── Phase C: institution_id String → UUID FK conversion ───────────────────
    # Safety guard: abort if any non-NULL institution_id values exist
    # (these columns were reserved hooks and should always be NULL in production)
    conn = op.get_bind()
    users_with_inst = conn.execute(
        sa.text("SELECT COUNT(*) FROM users WHERE institution_id IS NOT NULL")
    ).scalar()
    if users_with_inst > 0:
        raise RuntimeError(
            f"Cannot convert users.institution_id: {users_with_inst} row(s) have "
            "non-NULL values. Migrate data manually before running this migration."
        )
    subjects_with_inst = conn.execute(
        sa.text("SELECT COUNT(*) FROM subjects WHERE institution_id IS NOT NULL")
    ).scalar()
    if subjects_with_inst > 0:
        raise RuntimeError(
            f"Cannot convert subjects.institution_id: {subjects_with_inst} row(s) have "
            "non-NULL values. Migrate data manually before running this migration."
        )

    # users.institution_id: String(255) → UUID FK
    op.drop_index("ix_users_institution_id", table_name="users", if_exists=True)
    op.drop_column("users", "institution_id")
    op.add_column("users", sa.Column("institution_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_users_institution_id", "users", "institutions", ["institution_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_users_institution_id", "users", ["institution_id"])

    # subjects.institution_id: String(255) → UUID FK
    op.drop_index("ix_subjects_institution_id", table_name="subjects", if_exists=True)
    op.drop_column("subjects", "institution_id")
    op.add_column("subjects", sa.Column("institution_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_subjects_institution_id", "subjects", "institutions", ["institution_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_subjects_institution_id", "subjects", ["institution_id"])


def downgrade() -> None:
    # ── Reverse Phase C ──────────────────────────────────────────────────────
    op.drop_constraint("fk_subjects_institution_id", "subjects", type_="foreignkey")
    op.drop_index("ix_subjects_institution_id", table_name="subjects")
    op.drop_column("subjects", "institution_id")
    op.add_column("subjects", sa.Column("institution_id", sa.String(255), nullable=True))
    op.create_index("ix_subjects_institution_id", "subjects", ["institution_id"])

    op.drop_constraint("fk_users_institution_id", "users", type_="foreignkey")
    op.drop_index("ix_users_institution_id", table_name="users")
    op.drop_column("users", "institution_id")
    op.add_column("users", sa.Column("institution_id", sa.String(255), nullable=True))
    op.create_index("ix_users_institution_id", "users", ["institution_id"])

    # ── Reverse Phase B ──────────────────────────────────────────────────────
    op.drop_index("ix_subjects_course_id", table_name="subjects")
    op.drop_constraint("fk_subjects_course_id", "subjects", type_="foreignkey")
    op.drop_column("subjects", "course_id")

    for col in ["user_response", "scheduler_decision", "completion_status",
                "revision_duration_minutes", "revision_method"]:
        op.drop_column("revision_logs", col)

    for col in ["quiz_metadata", "question_count", "bloom_level",
                "earned_marks", "total_marks", "time_taken_seconds", "attempt_number"]:
        op.drop_column("quiz_attempts", col)

    for col in ["session_metadata", "platform", "device_type", "completion_status",
                "idle_minutes", "active_minutes", "ended_at", "started_at"]:
        op.drop_column("study_sessions", col)

    # ── Reverse Phase A ──────────────────────────────────────────────────────
    op.drop_table("feature_snapshots")
    op.drop_table("daily_user_activity")
    op.drop_table("retention_time_series")
    op.drop_table("quiz_question_responses")
    op.drop_table("learning_events")
    op.drop_table("learning_resources")
    op.drop_table("course_enrollments")
    op.drop_table("courses")
    op.drop_table("institutions")
