"""0003_add_retention_evolution_fields

Add retention evolution fields to memory_states:
  - Adaptive stability persistence (3 columns)
  - Decay parameters (3 columns)
  - Reinforcement behaviour (5 columns)
  - Retention history (4 columns)
  - Index on adaptive_stability

Revision ID: 0003
Revises: 0002
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Adaptive Stability Persistence ────────────────────────────────────
    op.add_column(
        "memory_states",
        sa.Column("adaptive_stability", sa.Float(), nullable=False, server_default="1.0"),
    )
    op.add_column(
        "memory_states",
        sa.Column("stability_growth_rate", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "memory_states",
        sa.Column("half_life_days", sa.Float(), nullable=False, server_default="0.0"),
    )

    # ── Decay Parameters ──────────────────────────────────────────────────
    op.add_column(
        "memory_states",
        sa.Column("effective_decay_rate", sa.Float(), nullable=False, server_default="0.1"),
    )
    op.add_column(
        "memory_states",
        sa.Column("time_to_critical", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "memory_states",
        sa.Column("days_until_target", sa.Float(), nullable=False, server_default="0.0"),
    )

    # ── Reinforcement Behaviour ───────────────────────────────────────────
    op.add_column(
        "memory_states",
        sa.Column("quality_variance", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "memory_states",
        sa.Column("effective_revision_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "memory_states",
        sa.Column("revision_effectiveness_ratio", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "memory_states",
        sa.Column("time_pattern_regularity", sa.Float(), nullable=False, server_default="0.5"),
    )
    op.add_column(
        "memory_states",
        sa.Column("confidence_calibration_error", sa.Float(), nullable=False, server_default="0.0"),
    )

    # ── Retention History ─────────────────────────────────────────────────
    op.add_column(
        "memory_states",
        sa.Column("peak_retention", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "memory_states",
        sa.Column("retention_at_last_revision", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "memory_states",
        sa.Column("total_forgetting_events", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "memory_states",
        sa.Column("last_forgetting_event_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── Index ─────────────────────────────────────────────────────────────
    op.create_index(
        "ix_memory_state_user_adaptive_stability",
        "memory_states",
        ["user_id", "adaptive_stability"],
    )


def downgrade() -> None:
    op.drop_index("ix_memory_state_user_adaptive_stability", table_name="memory_states")

    op.drop_column("memory_states", "last_forgetting_event_at")
    op.drop_column("memory_states", "total_forgetting_events")
    op.drop_column("memory_states", "retention_at_last_revision")
    op.drop_column("memory_states", "peak_retention")
    op.drop_column("memory_states", "confidence_calibration_error")
    op.drop_column("memory_states", "time_pattern_regularity")
    op.drop_column("memory_states", "revision_effectiveness_ratio")
    op.drop_column("memory_states", "effective_revision_count")
    op.drop_column("memory_states", "quality_variance")
    op.drop_column("memory_states", "days_until_target")
    op.drop_column("memory_states", "time_to_critical")
    op.drop_column("memory_states", "effective_decay_rate")
    op.drop_column("memory_states", "half_life_days")
    op.drop_column("memory_states", "stability_growth_rate")
    op.drop_column("memory_states", "adaptive_stability")
