"""
app/middleware/request_id.py
─────────────────────────────
Request ID middleware for correlation/tracing.

Assigns a UUID4 correlation ID to every incoming request.
Clients can supply their own ID via the X-Request-ID header.
The ID is stored in a contextvars.ContextVar for use across
the entire request lifecycle (logging, error responses, etc.).
"""

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.constants import REQUEST_ID_HEADER

# ── Context variable ──────────────────────────────────────────────────────────
# Accessible from any code running within a request context.
# Usage: from app.middleware.request_id import request_id_ctx
#        current_id = request_id_ctx.get("")
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Return the current request ID (empty string if not in a request context)."""
    return request_id_ctx.get("")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that ensures every request has a unique correlation ID.

    Behaviour:
      1. Check for client-supplied X-Request-ID header
      2. If missing, generate a UUID4
      3. Store in contextvars for downstream use
      4. Add X-Request-ID to response headers
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Use client-supplied ID or generate a new one
        rid = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())

        # Store in context for logging, exceptions, etc.
        token = request_id_ctx.set(rid)

        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = rid
            return response
        finally:
            request_id_ctx.reset(token)
