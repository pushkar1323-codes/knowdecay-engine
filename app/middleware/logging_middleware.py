"""
app/middleware/logging_middleware.py
────────────────────────────────────
Request/response logging middleware.

Logs every HTTP request with:
  - method, path, status code, duration (ms)
  - request ID (from request_id middleware)
  - never logs request/response bodies (avoids leaking secrets)
"""

import time
import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.middleware.request_id import get_request_id

logger = logging.getLogger("knowdecay.access")


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs every request with method, path, status, and duration.
    Uses INFO level for successful requests, WARNING for 4xx, ERROR for 5xx.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.perf_counter()

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start) * 1000.0
        rid = get_request_id()

        status = response.status_code
        if status >= 500:
            log_fn = logger.error
        elif status >= 400:
            log_fn = logger.warning
        else:
            log_fn = logger.info

        log_fn(
            "%s %s -> %d (%.1fms) [rid=%s]",
            request.method,
            request.url.path,
            status,
            duration_ms,
            rid,
        )

        return response
