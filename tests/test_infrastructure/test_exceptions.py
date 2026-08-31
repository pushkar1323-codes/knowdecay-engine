"""
tests/test_infrastructure/test_exceptions.py
──────────────────────────────────────────────
Tests for Phase 12 exception handling:
  - All custom exception types (status codes, messages)
  - Exception handlers return standardised responses
  - Request ID appears in error responses
  - Pydantic validation error handler
"""

import pytest
from fastapi import FastAPI, APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.core.constants import REQUEST_ID_HEADER
from app.core.exceptions import (
    ConfigurationError,
    ConflictError,
    DatabaseError,
    EngineError,
    InputValidationError,
    KnowDecayError,
    NotFoundError,
    ServiceError,
    register_exception_handlers,
)
from app.middleware.request_id import RequestIdMiddleware


# ── Exception Type Tests ──────────────────────────────────────────────────────

class TestExceptionTypes:
    """Verify all exception types have correct attributes."""

    def test_knowdecay_error_base(self):
        exc = KnowDecayError("test error", 500)
        assert exc.message == "test error"
        assert exc.status_code == 500
        assert str(exc) == "test error"

    def test_not_found_error(self):
        exc = NotFoundError("User", "abc-123")
        assert exc.status_code == 404
        assert "User" in exc.message
        assert "abc-123" in exc.message

    def test_conflict_error(self):
        exc = ConflictError("Email already exists")
        assert exc.status_code == 409
        assert "Email already exists" in exc.message

    def test_input_validation_error(self):
        exc = InputValidationError("Score must be between 0 and 1")
        assert exc.status_code == 422
        assert "Score must be" in exc.message

    def test_engine_error(self):
        exc = EngineError("retention", "Division by zero")
        assert exc.status_code == 500
        assert "retention" in exc.message
        assert "Division by zero" in exc.message

    def test_service_error(self):
        exc = ServiceError("priority_service", "State not found")
        assert exc.status_code == 500
        assert "priority_service" in exc.message
        assert "State not found" in exc.message

    def test_configuration_error(self):
        exc = ConfigurationError("DATABASE_URL is required")
        assert exc.status_code == 500
        assert "DATABASE_URL" in exc.message

    def test_database_error(self):
        exc = DatabaseError("Connection refused")
        assert exc.status_code == 500
        assert "Connection refused" in exc.message

    def test_database_error_default_message(self):
        exc = DatabaseError()
        assert exc.status_code == 500
        assert "Database error" in exc.message

    def test_all_inherit_from_base(self):
        """All exceptions must inherit from KnowDecayError."""
        for exc_class in [NotFoundError, ConflictError, InputValidationError,
                          EngineError, ServiceError, ConfigurationError, DatabaseError]:
            assert issubclass(exc_class, KnowDecayError)


# ── Exception Handler Tests ──────────────────────────────────────────────────

def _create_app_with_handlers() -> FastAPI:
    """Create a FastAPI app with exception handlers for testing."""
    app = FastAPI()

    # Register middleware for request ID
    app.add_middleware(RequestIdMiddleware)

    # Register exception handlers
    register_exception_handlers(app)

    router = APIRouter()

    @router.get("/raise-not-found")
    def raise_not_found():
        raise NotFoundError("Topic", "topic-xyz")

    @router.get("/raise-conflict")
    def raise_conflict():
        raise ConflictError("Resource already exists")

    @router.get("/raise-validation")
    def raise_validation():
        raise InputValidationError("Invalid score value")

    @router.get("/raise-engine")
    def raise_engine():
        raise EngineError("decay", "Negative stability")

    @router.get("/raise-service")
    def raise_service():
        raise ServiceError("scheduler", "No topics found")

    @router.get("/raise-unhandled")
    def raise_unhandled():
        raise RuntimeError("Something unexpected")

    class StrictModel(BaseModel):
        score: float = Field(ge=0.0, le=1.0)

    @router.post("/validate")
    def validate_input(body: StrictModel):
        return {"score": body.score}

    app.include_router(router)
    return app


class TestExceptionHandlers:
    """Verify exception handlers return correct responses."""

    def setup_method(self):
        self.app = _create_app_with_handlers()
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def test_not_found_handler(self):
        response = self.client.get("/raise-not-found")
        assert response.status_code == 404
        body = response.json()
        assert "error" in body
        assert "Topic" in body["error"]
        assert body["status_code"] == 404

    def test_conflict_handler(self):
        response = self.client.get("/raise-conflict")
        assert response.status_code == 409
        body = response.json()
        assert body["status_code"] == 409

    def test_validation_handler(self):
        response = self.client.get("/raise-validation")
        assert response.status_code == 422
        body = response.json()
        assert body["status_code"] == 422

    def test_engine_error_handler(self):
        response = self.client.get("/raise-engine")
        assert response.status_code == 500
        body = response.json()
        assert "decay" in body["error"]

    def test_service_error_handler(self):
        response = self.client.get("/raise-service")
        assert response.status_code == 500
        body = response.json()
        assert "scheduler" in body["error"]

    def test_unhandled_error_handler(self):
        response = self.client.get("/raise-unhandled")
        assert response.status_code == 500
        body = response.json()
        assert "Internal server error" in body["error"]
        # Must not leak internal details
        assert "RuntimeError" not in body["error"]
        assert "unexpected" not in body["error"]

    def test_request_id_in_error_response(self):
        """Error responses must include request_id."""
        custom_id = "err-trace-456"
        response = self.client.get(
            "/raise-not-found",
            headers={REQUEST_ID_HEADER: custom_id},
        )
        body = response.json()
        assert body.get("request_id") == custom_id

    def test_pydantic_validation_error(self):
        """Pydantic validation errors should return field-level details."""
        response = self.client.post(
            "/validate",
            json={"score": 5.0},  # exceeds max 1.0
        )
        assert response.status_code == 422
        body = response.json()
        assert "details" in body
        assert len(body["details"]) > 0
        assert "field" in body["details"][0]
        assert "message" in body["details"][0]

    def test_pydantic_missing_field(self):
        """Missing required fields should return 422 with details."""
        response = self.client.post("/validate", json={})
        assert response.status_code == 422
        body = response.json()
        assert body["status_code"] == 422
        assert "details" in body
