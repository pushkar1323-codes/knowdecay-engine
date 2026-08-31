"""0004_add_auth_fields

Revision ID: 0004
Revises: 0003_add_retention_evolution_fields
Create Date: 2026-07-30

Phase 13: Authentication & Security
  - Add password_hash, role, is_active, updated_at to users table
  - Create refresh_tokens table
  - Set defaults for existing rows
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Add auth columns to users table ───────────────────────────────────────
    op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=True))
    op.add_column("users", sa.Column(
        "role",
        sa.String(50),
        nullable=False,
        server_default="student",
    ))
    op.add_column("users", sa.Column(
        "is_active",
        sa.Boolean(),
        nullable=False,
        server_default=sa.text("true"),
    ))
    op.add_column("users", sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=True,
    ))

    # Create index on role column
    op.create_index("ix_users_role", "users", ["role"])

    # ── Create refresh_tokens table ───────────────────────────────────────────
    op.create_table(
        "refresh_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("token_hash", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    # ── Drop refresh_tokens table ─────────────────────────────────────────────
    op.drop_table("refresh_tokens")

    # ── Remove auth columns from users ────────────────────────────────────────
    op.drop_index("ix_users_role", table_name="users")
    op.drop_column("users", "updated_at")
    op.drop_column("users", "is_active")
    op.drop_column("users", "role")
    op.drop_column("users", "password_hash")
