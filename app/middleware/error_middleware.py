"""
app/middleware/error_middleware.py
──────────────────────────────────
Global error catching middleware.

Catches any unhandled exception that escapes the endpoint handlers
and FastAPI exception handlers. Returns a standardised error response
and logs the full traceback at ERROR level.

Never leaks stack traces or internal details to the client.
"""

import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.middleware.request_id import get_request_id

logger = logging.getLogger("knowdecay.errors")


class ErrorMiddleware(BaseHTTPMiddleware):
    """
    Last-resort error handler.

    Catches exceptions that bypass FastAPI's exception handlers
    (e.g. middleware-level errors, streaming failures).
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        try:
            return await call_next(request)
        except Exception:
            rid = get_request_id()
            logger.exception(
                "Unhandled exception in %s %s [rid=%s]",
                request.method,
                request.url.path,
                rid,
            )
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": {
                        "code": "INTERNAL_SERVER_ERROR",
                        "message": "An unexpected error occurred.",
                    },
                    "request_id": rid,
                },
            )
