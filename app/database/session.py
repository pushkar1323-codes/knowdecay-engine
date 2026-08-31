"""
app/database/session.py
────────────────────────
SQLAlchemy engine and session factory.
`get_db` is the FastAPI dependency injected into all route handlers
that need database access.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

settings = get_settings()

# ── Engine ────────────────────────────────────────────────────────────────────
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,      # validates connections before handing them out
    pool_size=10,            # number of persistent connections
    max_overflow=20,         # additional connections allowed under load
    echo=(settings.app_env == "development"),  # logs SQL in dev only
)

# ── Session factory ───────────────────────────────────────────────────────────
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session.
    Guarantees the session is closed after the request completes,
    even if an exception is raised.

    Usage:
        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            ...
    """
    db: Session = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
