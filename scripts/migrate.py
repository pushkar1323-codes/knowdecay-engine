"""
scripts/migrate.py
───────────────────
Migration management CLI for KnowDecay Engine.

Wraps common Alembic workflows into a single entrypoint with
safety guards for production environments.

Usage:
    python scripts/migrate.py upgrade          # Apply all pending migrations
    python scripts/migrate.py downgrade        # Roll back one migration
    python scripts/migrate.py downgrade --to base   # Roll back to empty schema
    python scripts/migrate.py status           # Show current revision and pending
    python scripts/migrate.py history          # Show full migration history
    python scripts/migrate.py generate "msg"   # Auto-generate a new migration
    python scripts/migrate.py verify           # Verify tables match ORM models
"""

import argparse
import logging
import os
import sys

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from app.config import get_settings
from app.core.logging import configure_logging
from app.database.session import engine

configure_logging()
logger = logging.getLogger(__name__)


def get_alembic_config() -> Config:
    """Build an Alembic Config with DATABASE_URL injected from app settings."""
    settings = get_settings()
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ini_path = os.path.join(project_root, "alembic.ini")

    alembic_cfg = Config(ini_path)
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    alembic_cfg.set_main_option(
        "script_location", os.path.join(project_root, "alembic")
    )
    return alembic_cfg


def cmd_upgrade(args: argparse.Namespace) -> None:
    """Apply all pending migrations (or up to a specific revision)."""
    target = args.to if args.to else "head"
    settings = get_settings()

    if settings.app_env == "production" and not args.force:
        logger.warning(
            "Production environment detected. Use --force to confirm migration."
        )
        print("⚠️  Production environment detected.")
        print("    Re-run with --force to apply migrations in production.")
        return

    logger.info("Upgrading database to: %s", target)
    cfg = get_alembic_config()
    command.upgrade(cfg, target)
    logger.info("✅ Upgrade complete.")


def cmd_downgrade(args: argparse.Namespace) -> None:
    """Roll back one migration (or to a specific revision)."""
    target = args.to if args.to else "-1"
    settings = get_settings()

    if settings.app_env == "production" and not args.force:
        logger.error(
            "Downgrade blocked in production. Use --force to override."
        )
        print("🚫 Downgrade is blocked in production.")
        print("    Re-run with --force to override (DANGEROUS).")
        return

    logger.info("Downgrading database to: %s", target)
    cfg = get_alembic_config()
    command.downgrade(cfg, target)
    logger.info("✅ Downgrade complete.")


def cmd_status(args: argparse.Namespace) -> None:
    """Show current migration revision and pending migrations."""
    cfg = get_alembic_config()
    print("─── Current Revision ───")
    command.current(cfg, verbose=True)
    print("\n─── Pending Migrations ───")
    command.heads(cfg, verbose=True)


def cmd_history(args: argparse.Namespace) -> None:
    """Show full migration history."""
    cfg = get_alembic_config()
    command.history(cfg, verbose=True)


def cmd_generate(args: argparse.Namespace) -> None:
    """Auto-generate a new migration from ORM model changes."""
    message = args.message
    if not message:
        print("❌ Migration message is required.")
        print("   Usage: python scripts/migrate.py generate \"add exam_dates table\"")
        return

    logger.info("Generating migration: %s", message)
    cfg = get_alembic_config()
    command.revision(cfg, message=message, autogenerate=True)
    logger.info("✅ Migration generated. Review the file before applying!")


def cmd_verify(args: argparse.Namespace) -> None:
    """
    Verify the database tables match the expected ORM schema.
    Lists all tables and checks for missing expected tables.
    """
    import app.models  # noqa: F401 — populate Base.metadata
    from app.database.base import Base

    # Check connection first
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ Database connection: OK")
    except Exception as exc:
        print(f"❌ Database connection failed: {exc}")
        return

    inspector = inspect(engine)
    db_tables = set(inspector.get_table_names())
    orm_tables = set(Base.metadata.tables.keys())

    # Exclude alembic_version from comparison
    db_tables.discard("alembic_version")

    print(f"\n─── Tables in Database ({len(db_tables)}) ───")
    for t in sorted(db_tables):
        status = "✅" if t in orm_tables else "⚠️  (not in ORM)"
        print(f"  {status} {t}")

    missing = orm_tables - db_tables
    if missing:
        print(f"\n❌ Missing tables (in ORM but not in DB): {sorted(missing)}")
        print("   Run: python scripts/migrate.py upgrade")
    else:
        print(f"\n✅ All {len(orm_tables)} ORM tables present in database.")

    extra = db_tables - orm_tables
    if extra:
        print(f"\n⚠️  Extra tables (in DB but not in ORM): {sorted(extra)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="KnowDecay Engine — Migration Management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Migration command")

    # upgrade
    p_up = subparsers.add_parser("upgrade", help="Apply pending migrations")
    p_up.add_argument("--to", default=None, help="Target revision (default: head)")
    p_up.add_argument(
        "--force", action="store_true", help="Allow in production environment"
    )

    # downgrade
    p_down = subparsers.add_parser("downgrade", help="Roll back migrations")
    p_down.add_argument("--to", default=None, help="Target revision (default: -1)")
    p_down.add_argument(
        "--force", action="store_true", help="Allow in production environment"
    )

    # status
    subparsers.add_parser("status", help="Show current revision")

    # history
    subparsers.add_parser("history", help="Show migration history")

    # generate
    p_gen = subparsers.add_parser("generate", help="Auto-generate a migration")
    p_gen.add_argument("message", nargs="?", help="Migration description")

    # verify
    subparsers.add_parser("verify", help="Verify DB tables match ORM models")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    commands = {
        "upgrade": cmd_upgrade,
        "downgrade": cmd_downgrade,
        "status": cmd_status,
        "history": cmd_history,
        "generate": cmd_generate,
        "verify": cmd_verify,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
