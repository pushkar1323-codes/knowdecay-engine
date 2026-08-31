"""
tests/conftest.py
──────────────────
Shared pytest fixtures for KnowDecay Engine tests.

Test categories:
  • test_engine/   — pure Python unit tests, NO database required
  • test_api/      — integration tests, require a running PostgreSQL instance
                     set TEST_DATABASE_URL env var to override default

For CI without PostgreSQL, run engine-only tests:
    pytest tests/test_engine/ -v
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# ── Test Database ─────────────────────────────────────────────────────────────
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://knowdecay:knowdecay@localhost:5432/knowdecay_test",
)


@pytest.fixture(scope="session")
def test_engine():
    """
    Create a SQLAlchemy engine pointed at the test database.
    All tables are created at session start and dropped at session end.
    Requires a running PostgreSQL instance.
    """
    from app.database.base import Base
    import app.models  # noqa: F401 — populate Base.metadata

    engine = create_engine(TEST_DATABASE_URL, echo=False)

    # Verify connection before running tests
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(test_engine) -> Session:
    """
    Provide a transactional test database session.
    Each test runs inside a transaction that is rolled back after the test,
    keeping the database clean between tests.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    TestSessionLocal = sessionmaker(bind=connection)
    session = TestSessionLocal()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session: Session):
    """
    FastAPI TestClient with the database dependency overridden
    to use the transactional test session.
    """
    from app.database.session import get_db
    from app.main import app

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
