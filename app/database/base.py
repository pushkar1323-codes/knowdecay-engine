"""
app/database/base.py
─────────────────────
Declares the SQLAlchemy DeclarativeBase shared by ALL ORM models.
Import Base from here — never re-declare it elsewhere.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Shared declarative base for all KnowDecay ORM models.
    Alembic's env.py imports Base.metadata to auto-detect migrations.
    """
    pass
