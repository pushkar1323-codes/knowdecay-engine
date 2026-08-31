"""
alembic/env.py
───────────────
Alembic migration environment.

Key responsibilities:
  1. Load DATABASE_URL from .env via app.config.Settings
  2. Import all models (via app.models) so Base.metadata is fully populated
  3. Support both offline and online migration modes
  4. Production safety: compare_type, compare_server_default, transactional DDL

After adding new ORM models:
  alembic revision --autogenerate -m "add <table_name>"
  alembic upgrade head

Or use the management script:
  python scripts/migrate.py generate "add <table_name>"
  python scripts/migrate.py upgrade
"""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# ── Make project root importable ──────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import get_settings        # noqa: E402
from app.database.base import Base         # noqa: E402
import app.models  # noqa: E402, F401     # MUST import to populate Base.metadata

# ── Alembic Config object ─────────────────────────────────────────────────────
config = context.config
settings = get_settings()

# Override sqlalchemy.url from application settings
config.set_main_option("sqlalchemy.url", settings.database_url)

# Configure Python logging from alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target the full schema for autogenerate
target_metadata = Base.metadata


def include_name(name, type_, parent_names):
    """
    Filter callback for autogenerate.
    Excludes any tables not defined in our ORM models.
    Prevents Alembic from trying to drop tables it doesn't own.
    """
    if type_ == "table":
        return name in target_metadata.tables
    return True


# ── Offline mode ──────────────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    """
    Run migrations without a live DB connection.
    Outputs SQL to stdout — useful for review before applying.

    Usage: alembic upgrade head --sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online mode ───────────────────────────────────────────────────────────────
def run_migrations_online() -> None:
    """
    Run migrations with a live DB connection (default mode).

    Production safety features:
      • compare_type=True         — detects column type changes
      • compare_server_default    — detects default value drift
      • transaction_per_migration — each migration in its own transaction
                                    so a failure doesn't corrupt the chain
      • include_name              — only manages tables defined in our ORM
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,   # fresh connection per migration run
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            transaction_per_migration=True,
            include_name=include_name,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

