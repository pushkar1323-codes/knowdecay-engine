"""
tests/test_infrastructure/test_responses.py
─────────────────────────────────────────────
Tests for Phase 12 standard response envelope:
  - success_response() format
  - error_response() format
  - paginated_response() format
  - Timestamp and request_id inclusion
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from app.core.responses import success_response, error_response, paginated_response


# ── Helpers ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_request_id():
    """Mock the request ID for all tests in this module."""
    with patch("app.core.responses.get_request_id", return_value="test-rid-123"):
        yield


# ── Success Response ──────────────────────────────────────────────────────────

class TestSuccessResponse:
    """Verify success_response() envelope format."""

    def test_basic_shape(self):
        result = success_response(data={"key": "value"})
        assert result["success"] is True
        assert result["data"] == {"key": "value"}
        assert "request_id" in result
        assert "timestamp" in result

    def test_includes_request_id(self):
        result = success_response(data={})
        assert result["request_id"] == "test-rid-123"

    def test_timestamp_is_iso_format(self):
        result = success_response(data={})
        # Should parse as valid ISO 8601
        datetime.fromisoformat(result["timestamp"])

    def test_optional_message(self):
        result = success_response(data={}, message="Created successfully")
        assert result["message"] == "Created successfully"

    def test_no_message_when_none(self):
        result = success_response(data={})
        assert "message" not in result

    def test_data_can_be_none(self):
        result = success_response(data=None)
        assert result["success"] is True
        assert result["data"] is None

    def test_data_can_be_list(self):
        result = success_response(data=[1, 2, 3])
        assert result["data"] == [1, 2, 3]


# ── Error Response ────────────────────────────────────────────────────────────

class TestErrorResponse:
    """Verify error_response() envelope format."""

    def test_basic_shape(self):
        result = error_response(code="NOT_FOUND", message="Resource not found")
        assert result["success"] is False
        assert "error" in result
        assert result["error"]["code"] == "NOT_FOUND"
        assert result["error"]["message"] == "Resource not found"
        assert "request_id" in result
        assert "timestamp" in result

    def test_includes_request_id(self):
        result = error_response(code="ERR", message="test")
        assert result["request_id"] == "test-rid-123"

    def test_optional_details(self):
        details = [
            {"field": "score", "message": "Must be between 0 and 1"},
            {"field": "name", "message": "Required"},
        ]
        result = error_response(
            code="VALIDATION_ERROR",
            message="Input validation failed",
            details=details,
        )
        assert result["error"]["details"] == details
        assert len(result["error"]["details"]) == 2

    def test_no_details_when_none(self):
        result = error_response(code="ERR", message="test")
        assert "details" not in result["error"]


# ── Paginated Response ────────────────────────────────────────────────────────

class TestPaginatedResponse:
    """Verify paginated_response() envelope format."""

    def test_basic_shape(self):
        result = paginated_response(
            data=[{"id": 1}, {"id": 2}],
            total=100,
            page=1,
            page_size=50,
        )
        assert result["success"] is True
        assert len(result["data"]) == 2
        assert "pagination" in result
        assert "request_id" in result
        assert "timestamp" in result

    def test_pagination_fields(self):
        result = paginated_response(data=[], total=100, page=2, page_size=25)
        p = result["pagination"]
        assert p["page"] == 2
        assert p["page_size"] == 25
        assert p["total"] == 100
        assert p["total_pages"] == 4

    def test_total_pages_rounds_up(self):
        result = paginated_response(data=[], total=101, page=1, page_size=50)
        assert result["pagination"]["total_pages"] == 3  # ceil(101/50) = 3

    def test_total_pages_exact_division(self):
        result = paginated_response(data=[], total=100, page=1, page_size=50)
        assert result["pagination"]["total_pages"] == 2

    def test_total_pages_single_page(self):
        result = paginated_response(data=[], total=5, page=1, page_size=50)
        assert result["pagination"]["total_pages"] == 1

    def test_total_pages_empty_result(self):
        result = paginated_response(data=[], total=0, page=1, page_size=50)
        assert result["pagination"]["total_pages"] == 1  # min 1
