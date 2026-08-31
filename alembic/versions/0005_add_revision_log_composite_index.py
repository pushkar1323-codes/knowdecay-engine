"""Add composite index on revision_logs(user_id, topic_id, revised_at).

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-09
"""
from alembic import op

# revision identifiers
revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_revision_log_user_topic_time",
        "revision_logs",
        ["user_id", "topic_id", "revised_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_revision_log_user_topic_time", table_name="revision_logs")
