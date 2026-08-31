"""
tests/test_infrastructure/test_health.py
──────────────────────────────────────────
Tests for Phase 12 health endpoints:
  - GET /health backward compatibility
  - GET /health/live always returns 200
  - GET /health/ready returns status
  - GET /health/detailed includes all fields

These tests use the production app from app.main but do NOT require
a running database — they use FastAPI's dependency override.
"""

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.constants import REQUEST_ID_HEADER


def _make_client(db_available: bool = True):
    """Create a test client with mocked DB dependency."""
    from app.main import app
    from app.deps import get_db

    mock_session = MagicMock()
    if db_available:
        mock_session.execute.return_value = None  # SELECT 1 succeeds
    else:
        mock_session.execute.side_effect = Exception("DB unavailable")

    def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def client_db_ok():
    """TestClient with DB available."""
    yield from _make_client(db_available=True)


@pytest.fixture
def client_db_down():
    """TestClient with DB unavailable."""
    yield from _make_client(db_available=False)


# ── GET /health (backward compatibility) ─────────────────────────────────────

class TestHealthEndpoint:
    """The existing /health endpoint must remain backward compatible."""

    def test_health_returns_200(self, client_db_ok):
        response = client_db_ok.get("/health")
        assert response.status_code == 200

    def test_health_response_shape(self, client_db_ok):
        body = client_db_ok.get("/health").json()
        # All original fields must be present
        assert "status" in body
        assert "engine" in body
        assert "version" in body
        assert "environment" in body
        assert "timestamp" in body
        assert "uptime_seconds" in body
        assert "database" in body
        assert "capabilities" in body

    def test_health_status_ok_when_db_up(self, client_db_ok):
        body = client_db_ok.get("/health").json()
        assert body["status"] == "ok"
        assert body["database"] == "connected"

    def test_health_degraded_when_db_down(self, client_db_down):
        body = client_db_down.get("/health").json()
        assert body["status"] == "degraded"
        assert body["database"] == "unavailable"

    def test_health_includes_request_id_header(self, client_db_ok):
        response = client_db_ok.get("/health")
        assert REQUEST_ID_HEADER in response.headers

    def test_health_capabilities_list(self, client_db_ok):
        body = client_db_ok.get("/health").json()
        caps = body["capabilities"]
        assert isinstance(caps, list)
        assert len(caps) >= 5
        assert "retention_prediction" in caps


# ── GET /health/live ──────────────────────────────────────────────────────────

class TestLivenessEndpoint:
    """Liveness probe must always return 200."""

    def test_live_returns_200(self, client_db_ok):
        response = client_db_ok.get("/health/live")
        assert response.status_code == 200

    def test_live_status_alive(self, client_db_ok):
        body = client_db_ok.get("/health/live").json()
        assert body["status"] == "alive"

    def test_live_no_db_dependency(self, client_db_down):
        """Liveness must succeed even when DB is down."""
        response = client_db_down.get("/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    def test_live_includes_request_id(self, client_db_ok):
        response = client_db_ok.get("/health/live")
        assert REQUEST_ID_HEADER in response.headers


# ── GET /health/ready ─────────────────────────────────────────────────────────

class TestReadinessEndpoint:
    """Readiness probe checks dependencies."""

    def test_ready_when_db_up(self, client_db_ok):
        response = client_db_ok.get("/health/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ready"
        assert body["database"] == "connected"
        assert "checks" in body

    def test_not_ready_when_db_down(self, client_db_down):
        response = client_db_down.get("/health/ready")
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "not_ready"
        assert body["database"] == "unavailable"


# ── GET /health/detailed ──────────────────────────────────────────────────────

class TestDetailedHealthEndpoint:
    """Detailed health includes infrastructure status."""

    def test_detailed_returns_200(self, client_db_ok):
        response = client_db_ok.get("/health/detailed")
        assert response.status_code == 200

    def test_detailed_includes_standard_fields(self, client_db_ok):
        body = client_db_ok.get("/health/detailed").json()
        for field in ["status", "engine", "version", "environment",
                      "timestamp", "uptime_seconds", "database", "capabilities"]:
            assert field in body, f"Missing field: {field}"

    def test_detailed_includes_infrastructure(self, client_db_ok):
        body = client_db_ok.get("/health/detailed").json()
        assert "infrastructure" in body
        infra = body["infrastructure"]
        assert infra["request_id_middleware"] == "active"
        assert infra["logging_middleware"] == "active"
        assert infra["error_middleware"] == "active"
        assert infra["structured_logging"] == "active"
        assert infra["exception_handlers"] == "active"

    def test_detailed_includes_configuration(self, client_db_ok):
        body = client_db_ok.get("/health/detailed").json()
        assert "configuration" in body
        config = body["configuration"]
        assert "log_level" in config
        assert "ml_enabled" in config
        # Must not contain secrets
        assert "database_url" not in str(config).lower()
        assert "password" not in str(config).lower()

    def test_detailed_no_secrets(self, client_db_ok):
        """Configuration section must never contain sensitive data."""
        body = client_db_ok.get("/health/detailed").json()
        body_str = str(body).lower()
        for secret in ["password", "secret", "token", "api_key"]:
            assert secret not in body_str
