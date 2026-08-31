"""
0002_add_adaptive_forgetting_fields.py
──────────────────────────────────────
Phase 8.5 migration: Adaptive Forgetting Curve fields.

Adds to memory_states:
  - base_stability        (float, default 1.0)
  - revision_quality      (float, default 0.5)
  - difficulty_factor     (float, default 0.5)
  - performance_trend     (float, default 0.0)

These fields power the adaptive forgetting curve R = e^(-t/S_adaptive)
where S_adaptive is computed from base_stability and behavioral signals.

Revision ID: 0002
Revises: 0001
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "0002"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "memory_states",
        sa.Column("base_stability", sa.Float(), nullable=False, server_default="1.0"),
    )
    op.add_column(
        "memory_states",
        sa.Column("revision_quality", sa.Float(), nullable=False, server_default="0.5"),
    )
    op.add_column(
        "memory_states",
        sa.Column("difficulty_factor", sa.Float(), nullable=False, server_default="0.5"),
    )
    op.add_column(
        "memory_states",
        sa.Column("performance_trend", sa.Float(), nullable=False, server_default="0.0"),
    )


def downgrade() -> None:
    op.drop_column("memory_states", "performance_trend")
    op.drop_column("memory_states", "difficulty_factor")
    op.drop_column("memory_states", "revision_quality")
    op.drop_column("memory_states", "base_stability")
