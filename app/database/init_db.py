"""
app/database/init_db.py
────────────────────────
Database initialization and table creation utilities.

Usage modes:
  1. Development — direct table creation (no Alembic):
       python -m app.database.init_db

  2. Production — always use Alembic:
       alembic upgrade head

  3. Test fixtures — create_all / drop_all against test DB:
       from app.database.init_db import create_tables, drop_tables

Design note: This module is a convenience for local development.
In production, Alembic is the ONLY path to schema changes.
"""

import logging

from sqlalchemy import inspect, text

from app.database.base import Base
from app.database.session import engine

# Importing models populates Base.metadata — required for create_all()
import app.models  # noqa: F401

logger = logging.getLogger(__name__)


def create_tables() -> None:
    """
    Create all tables from ORM model metadata.
    Safe to call multiple times — existing tables are not dropped.
    """
    Base.metadata.create_all(bind=engine)
    logger.info("All tables created (or already exist).")


def drop_tables() -> None:
    """
    Drop ALL tables. Destructive — use only in dev/test.
    """
    Base.metadata.drop_all(bind=engine)
    logger.warning("All tables dropped.")


def verify_tables() -> list[str]:
    """
    List all table names currently in the database.
    Useful for health-check and post-migration verification.
    """
    inspector = inspect(engine)
    tables = sorted(inspector.get_table_names())
    logger.info("Tables in database: %s", tables)
    return tables


def check_connection() -> bool:
    """
    Verify the database connection is alive.
    Returns True if the connection succeeds.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection verified.")
        return True
    except Exception as exc:
        logger.error("Database connection failed: %s", exc)
        return False


# ── CLI entrypoint ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from app.core.logging import configure_logging
    configure_logging()

    logger.info("Initializing KnowDecay Engine database...")
    if check_connection():
        create_tables()
        tables = verify_tables()
        logger.info(
            "Database ready — %d tables: %s",
            len(tables),
            ", ".join(tables),
        )
    else:
        logger.error("Cannot initialize database — connection failed.")
        raise SystemExit(1)
