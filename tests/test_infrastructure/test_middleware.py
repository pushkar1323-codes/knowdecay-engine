"""
tests/test_infrastructure/test_middleware.py
─────────────────────────────────────────────
Tests for Phase 12 middleware pipeline:
  - Request ID generation and propagation
  - Client-supplied request ID pass-through
  - Logging middleware captures method/path/status/duration
  - Error middleware catches unhandled exceptions
"""

import uuid

import pytest
from fastapi import FastAPI, APIRouter
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.constants import REQUEST_ID_HEADER
from app.middleware.request_id import RequestIdMiddleware, request_id_ctx, get_request_id
from app.middleware.logging_middleware import LoggingMiddleware
from app.middleware.error_middleware import ErrorMiddleware


# ── Helpers ───────────────────────────────────────────────────────────────────

def _create_test_app(
    *,
    raise_error: bool = False,
    capture_rid: bool = False,
) -> tuple[FastAPI, list]:
    """Create a minimal FastAPI app with middleware for testing."""
    captured = []
    test_router = APIRouter()

    @test_router.get("/test")
    def test_endpoint():
        if capture_rid:
            captured.append(get_request_id())
        return {"status": "ok"}

    @test_router.get("/error")
    def error_endpoint():
        raise RuntimeError("Simulated unhandled error")

    app = FastAPI()
    app.include_router(test_router)

    # Add middleware in reverse order (last added = first executed)
    app.add_middleware(ErrorMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestIdMiddleware)

    return app, captured


# ── Request ID Tests ──────────────────────────────────────────────────────────

class TestRequestIdMiddleware:
    """Tests for request ID generation and propagation."""

    def test_generates_request_id(self):
        """Every response should include an X-Request-ID header."""
        app, _ = _create_test_app()
        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200
        assert REQUEST_ID_HEADER in response.headers
        # Should be a valid UUID
        rid = response.headers[REQUEST_ID_HEADER]
        uuid.UUID(rid)  # raises ValueError if not valid

    def test_unique_request_ids(self):
        """Each request should get a unique ID."""
        app, _ = _create_test_app()
        client = TestClient(app)
        ids = set()
        for _ in range(10):
            response = client.get("/test")
            ids.add(response.headers[REQUEST_ID_HEADER])
        assert len(ids) == 10

    def test_client_supplied_request_id(self):
        """Client-supplied X-Request-ID should be preserved."""
        app, _ = _create_test_app()
        client = TestClient(app)
        custom_id = "my-custom-trace-id-12345"
        response = client.get("/test", headers={REQUEST_ID_HEADER: custom_id})
        assert response.headers[REQUEST_ID_HEADER] == custom_id

    def test_request_id_available_in_context(self):
        """Request ID should be accessible via contextvars during request."""
        app, captured = _create_test_app(capture_rid=True)
        client = TestClient(app)
        response = client.get("/test")
        rid = response.headers[REQUEST_ID_HEADER]
        assert len(captured) == 1
        assert captured[0] == rid

    def test_request_id_default_empty(self):
        """Outside request context, get_request_id returns empty string."""
        assert get_request_id() == ""


# ── Logging Middleware Tests ──────────────────────────────────────────────────

class TestLoggingMiddleware:
    """Tests for request/response logging."""

    def test_successful_request_logged(self, caplog):
        """Successful requests should be logged at INFO level."""
        app, _ = _create_test_app()
        client = TestClient(app)
        with caplog.at_level("INFO", logger="knowdecay.access"):
            response = client.get("/test")
        assert response.status_code == 200
        # Check that the log contains method, path, and status
        log_messages = [r.message for r in caplog.records if "knowdecay.access" in r.name]
        assert any("GET" in m and "/test" in m and "200" in m for m in log_messages)

    def test_404_logged_as_warning(self, caplog):
        """404 responses should be logged at WARNING level."""
        app, _ = _create_test_app()
        client = TestClient(app)
        with caplog.at_level("WARNING", logger="knowdecay.access"):
            response = client.get("/nonexistent")
        assert response.status_code == 404

    def test_log_includes_duration(self, caplog):
        """Log messages should include duration in ms."""
        app, _ = _create_test_app()
        client = TestClient(app)
        with caplog.at_level("INFO", logger="knowdecay.access"):
            client.get("/test")
        log_messages = [r.message for r in caplog.records if "knowdecay.access" in r.name]
        assert any("ms" in m for m in log_messages)


# ── Error Middleware Tests ────────────────────────────────────────────────────

class TestErrorMiddleware:
    """Tests for global error catching middleware."""

    def test_catches_unhandled_exception(self):
        """Unhandled exceptions should return 500 with standardised body."""
        app, _ = _create_test_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/error")
        assert response.status_code == 500
        body = response.json()
        assert body["success"] is False
        assert "error" in body
        assert body["error"]["code"] == "INTERNAL_SERVER_ERROR"
        # Request ID should be included
        assert "request_id" in body

    def test_error_includes_request_id(self):
        """Error responses should include the request ID."""
        app, _ = _create_test_app()
        client = TestClient(app, raise_server_exceptions=False)
        custom_id = "error-trace-123"
        response = client.get("/error", headers={REQUEST_ID_HEADER: custom_id})
        body = response.json()
        assert body["request_id"] == custom_id

    def test_no_stack_trace_in_response(self):
        """Stack traces should never leak to client."""
        app, _ = _create_test_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/error")
        body_str = response.text
        assert "Traceback" not in body_str
        assert "RuntimeError" not in body_str
        assert "Simulated" not in body_str
