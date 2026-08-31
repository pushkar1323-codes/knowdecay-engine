"""
app/deps.py
────────────
FastAPI dependency functions shared across multiple routers.

This module centralises:
  • database session injection
  • settings injection
  • (future) auth / tenant resolution

Usage in any router:
    from app.deps import get_db, get_settings_dep
    from sqlalchemy.orm import Session
    from fastapi import Depends

    @router.get("/example")
    def example(db: Session = Depends(get_db)):
        ...
"""

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.session import get_db as _get_db


def get_db() -> Generator[Session, None, None]:
    """
    Database session dependency.
    Re-exported here so routers import from a single location.
    """
    yield from _get_db()


def get_settings_dep() -> Settings:
    """
    Settings dependency — injects the cached Settings singleton.
    Useful for routes that need to read engine configuration constants.
    """
    return get_settings()
