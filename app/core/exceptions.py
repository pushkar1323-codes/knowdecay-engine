"""
app/core/exceptions.py
───────────────────────
Centralised exception hierarchy and FastAPI exception handlers.

All engine and service errors must raise a subclass of KnowDecayError.
`register_exception_handlers(app)` is called once in main.py.

Phase 12 enhancements:
  - Request ID included in all error responses
  - Pydantic RequestValidationError handler with field-level detail
  - ServiceError and ConfigurationError exception types
  - Structured logging with severity levels
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# ── Exception hierarchy ───────────────────────────────────────────────────────

class KnowDecayError(Exception):
    """Base exception for all KnowDecay Engine errors."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(KnowDecayError):
    """Raised when a requested resource does not exist in the database."""

    def __init__(self, resource: str, resource_id: str) -> None:
        super().__init__(
            message=f"{resource} with id '{resource_id}' not found.",
            status_code=404,
        )


class ConflictError(KnowDecayError):
    """Raised on unique constraint violations (e.g., duplicate user email)."""

    def __init__(self, detail: str) -> None:
        super().__init__(message=detail, status_code=409)


class InputValidationError(KnowDecayError):
    """Raised when caller-supplied data fails business-level validation."""

    def __init__(self, detail: str) -> None:
        super().__init__(message=detail, status_code=422)


class EngineError(KnowDecayError):
    """
    Raised when a core engine module (retention, decay, priority, etc.)
    encounters a calculation failure.
    """

    def __init__(self, module: str, detail: str) -> None:
        super().__init__(
            message=f"Engine error in [{module}]: {detail}",
            status_code=500,
        )


class ServiceError(KnowDecayError):
    """
    Raised when the service/orchestration layer encounters an error
    that is not attributable to a specific engine module.
    """

    def __init__(self, service: str, detail: str) -> None:
        super().__init__(
            message=f"Service error in [{service}]: {detail}",
            status_code=500,
        )


class ConfigurationError(KnowDecayError):
    """
    Raised when a required configuration value is missing or invalid.
    Typically raised at startup.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(
            message=f"Configuration error: {detail}",
            status_code=500,
        )


class DatabaseError(KnowDecayError):
    """Raised when a database operation fails."""

    def __init__(self, detail: str = "Database error") -> None:
        super().__init__(message=detail, status_code=500)


class AuthenticationError(KnowDecayError):
    """
    Raised when authentication fails: invalid credentials, expired token,
    missing or malformed Authorization header.
    """

    def __init__(self, detail: str = "Authentication required") -> None:
        super().__init__(message=detail, status_code=401)


class AuthorizationError(KnowDecayError):
    """
    Raised when an authenticated user lacks the required role or permission
    to access a resource.
    """

    def __init__(self, detail: str = "Insufficient permissions") -> None:
        super().__init__(message=detail, status_code=403)


class AccountDisabledError(KnowDecayError):
    """Raised when a deactivated user attempts to authenticate."""

    def __init__(self) -> None:
        super().__init__(message="Account is disabled", status_code=403)


# ── Handler registration ──────────────────────────────────────────────────────

def _get_request_id() -> str:
    """Safely get request ID without import errors."""
    try:
        from app.middleware.request_id import get_request_id
        return get_request_id()
    except Exception:
        return ""


def register_exception_handlers(app: FastAPI) -> None:
    """
    Attach all centralised exception handlers to the FastAPI app.
    Must be called before the first request is served.
    """

    @app.exception_handler(KnowDecayError)
    async def knowdecay_error_handler(
        request: Request, exc: KnowDecayError
    ) -> JSONResponse:
        rid = _get_request_id()
        logger.error(
            "KnowDecayError [%s] %s %s -> %s [rid=%s]",
            exc.status_code,
            request.method,
            request.url.path,
            exc.message,
            rid,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.message,
                "status_code": exc.status_code,
                "request_id": rid,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        rid = _get_request_id()
        errors = []
        for err in exc.errors():
            errors.append({
                "field": ".".join(str(loc) for loc in err.get("loc", [])),
                "message": err.get("msg", ""),
                "type": err.get("type", ""),
            })
        logger.warning(
            "Validation error %s %s -> %d field errors [rid=%s]",
            request.method,
            request.url.path,
            len(errors),
            rid,
        )
        return JSONResponse(
            status_code=422,
            content={
                "error": "Validation error",
                "status_code": 422,
                "details": errors,
                "request_id": rid,
            },
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        rid = _get_request_id()
        logger.exception(
            "Unhandled exception [500] %s %s [rid=%s]",
            request.method,
            request.url.path,
            rid,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error. Check engine logs for details.",
                "status_code": 500,
                "request_id": rid,
            },
        )
