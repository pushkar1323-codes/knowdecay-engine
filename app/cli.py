"""
app/cli.py
──────────
CLI utilities for KnowDecay Engine administration.

Usage:
  python -m app.cli create-superadmin
  python -m app.cli aggregate-daily [--user-id UUID]
  python -m app.cli generate-features --user-id UUID --topic-id UUID
"""

import getpass
import logging
import sys
import uuid as uuid_mod
from datetime import date

from app.core.logging import configure_logging


def create_superadmin() -> None:
    """Create the initial super_admin user interactively."""
    configure_logging()

    from app.core.enums import UserRole
    from app.core.security import hash_password
    from app.database.session import SessionLocal
    from app.models.user import User

    print("\n╔══════════════════════════════════════════╗")
    print("║   KnowDecay Engine — Create Super Admin  ║")
    print("╚══════════════════════════════════════════╝\n")

    # Collect input
    name = input("Full name: ").strip()
    if not name:
        print("Error: Name is required.")
        sys.exit(1)

    email = input("Email: ").strip()
    if not email:
        print("Error: Email is required.")
        sys.exit(1)

    password = getpass.getpass("Password (min 8 chars): ")
    if len(password) < 8:
        print("Error: Password must be at least 8 characters.")
        sys.exit(1)

    password_confirm = getpass.getpass("Confirm password: ")
    if password != password_confirm:
        print("Error: Passwords do not match.")
        sys.exit(1)

    # Create user
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            print(f"\nError: User with email '{email}' already exists.")
            if existing.role != UserRole.SUPER_ADMIN.value:
                promote = input("Promote to super_admin? (y/N): ").strip().lower()
                if promote == "y":
                    existing.role = UserRole.SUPER_ADMIN.value
                    existing.is_active = True
                    existing.password_hash = hash_password(password)
                    db.commit()
                    print(f"\n✓ User '{email}' promoted to super_admin.")
                else:
                    print("Aborted.")
            sys.exit(0)

        user = User(
            name=name,
            email=email,
            password_hash=hash_password(password),
            role=UserRole.SUPER_ADMIN.value,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        print(f"\n✓ Super admin created successfully.")
        print(f"  ID:    {user.id}")
        print(f"  Name:  {user.name}")
        print(f"  Email: {user.email}")
        print(f"  Role:  {user.role}")

    finally:
        db.close()


def aggregate_daily() -> None:
    """Run daily aggregation for all active users or a specific user."""
    configure_logging()
    logger = logging.getLogger("app.cli")

    from app.database.session import SessionLocal
    from app.services.aggregation_service import (
        run_daily_aggregation,
        aggregate_daily_activity,
    )

    user_id_str = None
    if len(sys.argv) > 2 and sys.argv[2] == "--user-id" and len(sys.argv) > 3:
        user_id_str = sys.argv[3]

    db = SessionLocal()
    try:
        if user_id_str:
            user_id = uuid_mod.UUID(user_id_str)
            today = date.today()
            logger.info("Aggregating daily activity for user=%s date=%s", user_id, today)
            result = aggregate_daily_activity(db, user_id, today)
            logger.info("Done: %s", result)
        else:
            logger.info("Running full daily aggregation for all active users")
            summary = run_daily_aggregation(db)
            logger.info("Aggregation complete: %s", summary)
    finally:
        db.close()


def generate_features() -> None:
    """Generate ML feature snapshots for a user×topic pair."""
    configure_logging()
    logger = logging.getLogger("app.cli")

    from app.database.session import SessionLocal
    from app.services.aggregation_service import generate_feature_snapshot

    # Parse --user-id and --topic-id
    user_id_str = None
    topic_id_str = None
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--user-id" and i + 1 < len(args):
            user_id_str = args[i + 1]
            i += 2
        elif args[i] == "--topic-id" and i + 1 < len(args):
            topic_id_str = args[i + 1]
            i += 2
        else:
            i += 1

    if not user_id_str or not topic_id_str:
        print("Usage: python -m app.cli generate-features --user-id UUID --topic-id UUID")
        sys.exit(1)

    db = SessionLocal()
    try:
        user_id = uuid_mod.UUID(user_id_str)
        topic_id = uuid_mod.UUID(topic_id_str)
        logger.info("Generating features for user=%s topic=%s", user_id, topic_id)
        result = generate_feature_snapshot(db, user_id, topic_id)
        logger.info("Feature snapshot: %s", result)
    finally:
        db.close()


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python -m app.cli <command>")
        print("\nAvailable commands:")
        print("  create-superadmin   — Create the initial super admin user")
        print("  aggregate-daily     — Run daily analytics aggregation")
        print("  generate-features   — Generate ML feature snapshot for user×topic")
        sys.exit(1)

    command = sys.argv[1]
    if command == "create-superadmin":
        create_superadmin()
    elif command == "aggregate-daily":
        aggregate_daily()
    elif command == "generate-features":
        generate_features()
    else:
        print(f"Unknown command: {command}")
        print("Available commands: create-superadmin, aggregate-daily, generate-features")
        sys.exit(1)


if __name__ == "__main__":
    main()

