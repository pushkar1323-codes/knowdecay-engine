"""
app/core/responses.py
──────────────────────
Standard API response envelope for infrastructure endpoints.

Phase 12: Applied to new infrastructure endpoints only.
Existing engine API endpoints retain their current response format.
Designed for easy migration to /api/v2 in a future phase.

Usage in infrastructure endpoints:
    from app.core.responses import success_response, error_response

    @router.get("/health/detailed")
    def detailed_health():
        return success_response(data={...})
"""

from datetime import datetime, timezone
from typing import Any

from app.middleware.request_id import get_request_id


def success_response(
    data: Any = None,
    message: str | None = None,
) -> dict:
    """
    Build a standard success response envelope.

    Shape:
    {
        "success": true,
        "data": { ... },
        "message": "optional",
        "request_id": "uuid",
        "timestamp": "ISO 8601"
    }
    """
    body: dict[str, Any] = {
        "success": True,
        "data": data,
        "request_id": get_request_id(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if message:
        body["message"] = message
    return body


def error_response(
    code: str,
    message: str,
    details: list[dict] | None = None,
    status_code: int = 500,
) -> dict:
    """
    Build a standard error response envelope.

    Shape:
    {
        "success": false,
        "error": {
            "code": "ERROR_CODE",
            "message": "Human-readable message",
            "details": [ ... ]
        },
        "request_id": "uuid",
        "timestamp": "ISO 8601"
    }
    """
    error: dict[str, Any] = {
        "code": code,
        "message": message,
    }
    if details:
        error["details"] = details

    return {
        "success": False,
        "error": error,
        "request_id": get_request_id(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def paginated_response(
    data: list,
    total: int,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """
    Build a standard paginated response envelope.
    Prepared for future use — not used by any current endpoint.

    Shape:
    {
        "success": true,
        "data": [ ... ],
        "pagination": {
            "page": 1,
            "page_size": 50,
            "total": 150,
            "total_pages": 3
        },
        "request_id": "uuid",
        "timestamp": "ISO 8601"
    }
    """
    total_pages = max(1, (total + page_size - 1) // page_size)
    return {
        "success": True,
        "data": data,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        },
        "request_id": get_request_id(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
