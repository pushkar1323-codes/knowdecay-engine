"""
tests/test_api/test_intelligence_auth.py
─────────────────────────────────────────
Integration tests for authentication and ownership enforcement on
all 6 intelligence route groups:

  • Memory   — /v1/memory/*
  • Retention — /v1/retention/*
  • Priority  — /v1/priority/*
  • Schedule  — /v1/schedule/*
  • Recalibration — /v1/recalibrate/*
  • Analytics — /v1/analytics/*

Validates:
  • Unauthenticated access returns 401
  • Student accessing own data succeeds (passes auth, reaches service)
  • Student accessing another user's data returns 403
  • API_CLIENT accessing any user's data succeeds
  • SUPER_ADMIN accessing any user's data succeeds
  • Teacher has same ownership restrictions as student
"""

import os
import uuid

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-unit-tests-minimum-length-required-64-chars-long")
os.environ.setdefault("APP_ENV", "testing")

from app.config import get_settings  # noqa: E402
get_settings.cache_clear()

import pytest  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from unittest.mock import MagicMock, patch  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.deps import get_db  # noqa: E402
from app.deps_auth import get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User  # noqa: E402


# ── Helpers ───────────────────────────────────────────────────────────────────

STUDENT_ID = uuid.uuid4()
OTHER_STUDENT_ID = uuid.uuid4()
ADMIN_ID = uuid.uuid4()
API_CLIENT_ID = uuid.uuid4()
TOPIC_ID = uuid.uuid4()


def _make_user(role, user_id):
    """Create a mock User ORM object with given role and id."""
    user = MagicMock(spec=User)
    user.id = user_id
    user.email = f"{role}@test.com"
    user.name = f"Test {role}"
    user.role = role
    user.is_active = True
    user.institution_id = None
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    return user


STUDENT = _make_user("student", STUDENT_ID)
OTHER_STUDENT = _make_user("student", OTHER_STUDENT_ID)
ADMIN = _make_user("super_admin", ADMIN_ID)
API_CLIENT = _make_user("api_client", API_CLIENT_ID)


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def unauthed_client(mock_db):
    """TestClient with NO auth override — for 401 tests."""
    def override_get_db():
        yield mock_db
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _authed_client(mock_db, user):
    """Create a TestClient authenticated as the given user."""
    def override_get_db():
        yield mock_db
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


@pytest.fixture
def student_client(mock_db):
    """TestClient authenticated as STUDENT."""
    c = _authed_client(mock_db, STUDENT)
    with c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def admin_client(mock_db):
    """TestClient authenticated as SUPER_ADMIN."""
    c = _authed_client(mock_db, ADMIN)
    with c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def api_client_client(mock_db):
    """TestClient authenticated as API_CLIENT."""
    c = _authed_client(mock_db, API_CLIENT)
    with c:
        yield c
    app.dependency_overrides.clear()


# ══════════════════════════════════════════════════════════════════════════════
# 1. UNAUTHENTICATED ACCESS — ALL ROUTE GROUPS MUST RETURN 401
# ══════════════════════════════════════════════════════════════════════════════

class TestUnauthenticatedAccess:
    """All intelligence endpoints must reject unauthenticated requests."""

    def test_memory_get_state_401(self, unauthed_client):
        resp = unauthed_client.get(f"/v1/memory/{STUDENT_ID}/{TOPIC_ID}")
        assert resp.status_code == 401

    def test_memory_list_401(self, unauthed_client):
        resp = unauthed_client.get(f"/v1/memory/{STUDENT_ID}")
        assert resp.status_code == 401

    def test_memory_init_401(self, unauthed_client):
        resp = unauthed_client.post("/v1/memory/init", json={
            "user_id": str(STUDENT_ID), "topic_id": str(TOPIC_ID),
        })
        assert resp.status_code == 401

    def test_memory_batch_401(self, unauthed_client):
        resp = unauthed_client.post("/v1/memory/batch", json={
            "user_id": str(STUDENT_ID), "topic_ids": [str(TOPIC_ID)],
        })
        assert resp.status_code == 401

    def test_memory_overview_401(self, unauthed_client):
        resp = unauthed_client.get(f"/v1/memory/{STUDENT_ID}/overview")
        assert resp.status_code == 401

    def test_retention_predict_401(self, unauthed_client):
        resp = unauthed_client.post("/v1/retention/predict", json={
            "user_id": str(STUDENT_ID), "topic_id": str(TOPIC_ID),
        })
        assert resp.status_code == 401

    def test_retention_predict_batch_401(self, unauthed_client):
        resp = unauthed_client.post("/v1/retention/predict/batch", json={
            "user_id": str(STUDENT_ID), "topic_ids": [str(TOPIC_ID)],
        })
        assert resp.status_code == 401

    def test_priority_rank_401(self, unauthed_client):
        resp = unauthed_client.post("/v1/priority/rank", json={
            "user_id": str(STUDENT_ID), "topic_id": str(TOPIC_ID),
        })
        assert resp.status_code == 401

    def test_priority_rank_batch_401(self, unauthed_client):
        resp = unauthed_client.post("/v1/priority/rank/batch", json={
            "user_id": str(STUDENT_ID), "topic_ids": [str(TOPIC_ID)],
        })
        assert resp.status_code == 401

    def test_schedule_next_401(self, unauthed_client):
        resp = unauthed_client.post("/v1/schedule/next", json={
            "user_id": str(STUDENT_ID), "topic_id": str(TOPIC_ID),
        })
        assert resp.status_code == 401

    def test_schedule_generate_401(self, unauthed_client):
        resp = unauthed_client.post("/v1/schedule/generate", json={
            "user_id": str(STUDENT_ID), "topic_ids": [str(TOPIC_ID)],
        })
        assert resp.status_code == 401

    def test_recalibrate_401(self, unauthed_client):
        resp = unauthed_client.post("/v1/recalibrate", json={
            "user_id": str(STUDENT_ID), "topic_id": str(TOPIC_ID),
            "event_type": "revision_completed",
        })
        assert resp.status_code == 401

    def test_recalibrate_batch_401(self, unauthed_client):
        resp = unauthed_client.post("/v1/recalibrate/batch", json={
            "events": [{"user_id": str(STUDENT_ID), "topic_id": str(TOPIC_ID),
                        "event_type": "revision_completed"}],
        })
        assert resp.status_code == 401

    def test_analytics_summary_401(self, unauthed_client):
        resp = unauthed_client.get(f"/v1/analytics/{STUDENT_ID}/summary")
        assert resp.status_code == 401

    def test_analytics_weak_topics_401(self, unauthed_client):
        resp = unauthed_client.get(f"/v1/analytics/{STUDENT_ID}/weak-topics")
        assert resp.status_code == 401

    def test_analytics_heatmap_401(self, unauthed_client):
        resp = unauthed_client.get(f"/v1/analytics/{STUDENT_ID}/heatmap")
        assert resp.status_code == 401

    def test_analytics_distribution_401(self, unauthed_client):
        resp = unauthed_client.get(f"/v1/analytics/{STUDENT_ID}/distribution")
        assert resp.status_code == 401

    def test_analytics_report_401(self, unauthed_client):
        resp = unauthed_client.get(f"/v1/analytics/{STUDENT_ID}/report")
        assert resp.status_code == 401

    def test_analytics_advanced_401(self, unauthed_client):
        resp = unauthed_client.get(f"/v1/analytics/{STUDENT_ID}/advanced")
        assert resp.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# 2. CROSS-USER ACCESS — STUDENTS MUST NOT ACCESS OTHER STUDENTS' DATA
# ══════════════════════════════════════════════════════════════════════════════

class TestCrossUserAccessDenied:
    """Students accessing another user's data must get 403."""

    def test_memory_cross_user_403(self, student_client):
        resp = student_client.get(f"/v1/memory/{OTHER_STUDENT_ID}/{TOPIC_ID}")
        assert resp.status_code == 403

    def test_retention_cross_user_403(self, student_client):
        resp = student_client.post("/v1/retention/predict", json={
            "user_id": str(OTHER_STUDENT_ID), "topic_id": str(TOPIC_ID),
        })
        assert resp.status_code == 403

    def test_priority_cross_user_403(self, student_client):
        resp = student_client.post("/v1/priority/rank", json={
            "user_id": str(OTHER_STUDENT_ID), "topic_id": str(TOPIC_ID),
        })
        assert resp.status_code == 403

    def test_schedule_cross_user_403(self, student_client):
        resp = student_client.post("/v1/schedule/next", json={
            "user_id": str(OTHER_STUDENT_ID), "topic_id": str(TOPIC_ID),
        })
        assert resp.status_code == 403

    def test_recalibrate_cross_user_403(self, student_client):
        resp = student_client.post("/v1/recalibrate", json={
            "user_id": str(OTHER_STUDENT_ID), "topic_id": str(TOPIC_ID),
            "event_type": "revision_completed",
        })
        assert resp.status_code == 403

    def test_analytics_cross_user_403(self, student_client):
        resp = student_client.get(f"/v1/analytics/{OTHER_STUDENT_ID}/summary")
        assert resp.status_code == 403

    def test_memory_init_cross_user_403(self, student_client):
        resp = student_client.post("/v1/memory/init", json={
            "user_id": str(OTHER_STUDENT_ID), "topic_id": str(TOPIC_ID),
        })
        assert resp.status_code == 403

    def test_memory_batch_cross_user_403(self, student_client):
        resp = student_client.post("/v1/memory/batch", json={
            "user_id": str(OTHER_STUDENT_ID), "topic_ids": [str(TOPIC_ID)],
        })
        assert resp.status_code == 403

    def test_recalibrate_batch_cross_user_403(self, student_client):
        """Batch recalibration with events for another user must fail."""
        resp = student_client.post("/v1/recalibrate/batch", json={
            "events": [{"user_id": str(OTHER_STUDENT_ID), "topic_id": str(TOPIC_ID),
                        "event_type": "revision_completed"}],
        })
        assert resp.status_code == 403


# ══════════════════════════════════════════════════════════════════════════════
# 3. SELF-ACCESS — STUDENTS ACCESSING THEIR OWN DATA MUST SUCCEED
# ══════════════════════════════════════════════════════════════════════════════

class TestSelfAccess:
    """Students accessing their own data must pass the ownership check."""

    @patch("app.services.memory_service.get_memory_state")
    def test_memory_self_access_passes_ownership(self, mock_service, student_client):
        mock_service.return_value = None  # returns 404, but auth passes
        resp = student_client.get(f"/v1/memory/{STUDENT_ID}/{TOPIC_ID}")
        assert resp.status_code == 404  # auth + ownership passed, no data

    @patch("app.services.analytics_service.get_retention_summary")
    def test_analytics_self_access_passes_ownership(self, mock_service, student_client):
        mock_service.return_value = MagicMock(
            mean_retention=0.75, zone="strong", total_topics=5,
            weak_count=1, critical_count=0,
            zone_distribution={"mastered": 2, "strong": 2, "moderate": 1, "weak": 0, "critical": 0},
        )
        resp = student_client.get(f"/v1/analytics/{STUDENT_ID}/summary")
        # Auth + ownership passes — service is called
        assert resp.status_code != 401
        assert resp.status_code != 403


# ══════════════════════════════════════════════════════════════════════════════
# 4. PRIVILEGED ACCESS — ADMIN / API_CLIENT CAN ACCESS ANY USER'S DATA
# ══════════════════════════════════════════════════════════════════════════════

class TestPrivilegedAccess:
    """Admin and API_CLIENT can access any learner's data."""

    @patch("app.services.memory_service.get_memory_state")
    def test_admin_can_access_any_user_memory(self, mock_service, admin_client):
        mock_service.return_value = None
        resp = admin_client.get(f"/v1/memory/{OTHER_STUDENT_ID}/{TOPIC_ID}")
        assert resp.status_code == 404  # auth passes, no data

    @patch("app.services.memory_service.get_memory_state")
    def test_api_client_can_access_any_user_memory(self, mock_service, api_client_client):
        mock_service.return_value = None
        resp = api_client_client.get(f"/v1/memory/{OTHER_STUDENT_ID}/{TOPIC_ID}")
        assert resp.status_code == 404  # auth passes, no data

    @patch("app.services.recalibration_service.process_event")
    def test_api_client_can_recalibrate_any_user(self, mock_recal, api_client_client):
        """API_CLIENT must be able to submit events for any user (platform use case)."""
        mock_result = MagicMock()
        mock_recal.return_value = mock_result
        resp = api_client_client.post("/v1/recalibrate", json={
            "user_id": str(OTHER_STUDENT_ID),
            "topic_id": str(TOPIC_ID),
            "event_type": "revision_completed",
        })
        assert resp.status_code != 401
        assert resp.status_code != 403

    @patch("app.services.analytics_service.get_retention_summary")
    def test_admin_can_access_any_user_analytics(self, mock_service, admin_client):
        """Admin must be able to view any learner's analytics."""
        mock_service.return_value = MagicMock(
            mean_retention=0.75, zone="strong", total_topics=5,
            weak_count=1, critical_count=0,
            zone_distribution={"mastered": 2, "strong": 2, "moderate": 1, "weak": 0, "critical": 0},
        )
        resp = admin_client.get(f"/v1/analytics/{OTHER_STUDENT_ID}/summary")
        assert resp.status_code != 401
        assert resp.status_code != 403


# ══════════════════════════════════════════════════════════════════════════════
# 5. TEACHER ACCESS — SAME OWNERSHIP RESTRICTIONS AS STUDENT
# ══════════════════════════════════════════════════════════════════════════════

class TestTeacherAccess:
    """Teachers have same ownership restrictions as students."""

    def test_teacher_cannot_access_other_user_data(self, mock_db):
        teacher = _make_user("teacher", uuid.uuid4())
        c = _authed_client(mock_db, teacher)
        resp = c.get(f"/v1/memory/{OTHER_STUDENT_ID}/{TOPIC_ID}")
        assert resp.status_code == 403
        app.dependency_overrides.clear()

    @patch("app.services.memory_service.get_memory_state")
    def test_teacher_can_access_own_data(self, mock_service, mock_db):
        teacher = _make_user("teacher", uuid.uuid4())
        c = _authed_client(mock_db, teacher)
        mock_service.return_value = None
        resp = c.get(f"/v1/memory/{teacher.id}/{TOPIC_ID}")
        assert resp.status_code == 404  # auth passes, just no data
        app.dependency_overrides.clear()


# ══════════════════════════════════════════════════════════════════════════════
# 6. ENFORCE_LEARNER_ACCESS UNIT TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestEnforceLearnerAccessUnit:
    """Direct unit tests for the enforce_learner_access function."""

    def test_student_own_data_passes(self):
        from app.deps_auth import enforce_learner_access
        enforce_learner_access(STUDENT_ID, STUDENT)

    def test_student_other_data_raises(self):
        from app.deps_auth import enforce_learner_access
        from app.core.exceptions import AuthorizationError
        with pytest.raises(AuthorizationError):
            enforce_learner_access(OTHER_STUDENT_ID, STUDENT)

    def test_admin_any_data_passes(self):
        from app.deps_auth import enforce_learner_access
        enforce_learner_access(OTHER_STUDENT_ID, ADMIN)

    def test_api_client_any_data_passes(self):
        from app.deps_auth import enforce_learner_access
        enforce_learner_access(OTHER_STUDENT_ID, API_CLIENT)

    def test_institution_admin_any_data_passes(self):
        from app.deps_auth import enforce_learner_access
        inst_admin = _make_user("institution_admin", uuid.uuid4())
        enforce_learner_access(OTHER_STUDENT_ID, inst_admin)

    def test_teacher_other_data_raises(self):
        from app.deps_auth import enforce_learner_access
        from app.core.exceptions import AuthorizationError
        teacher = _make_user("teacher", uuid.uuid4())
        with pytest.raises(AuthorizationError):
            enforce_learner_access(OTHER_STUDENT_ID, teacher)
