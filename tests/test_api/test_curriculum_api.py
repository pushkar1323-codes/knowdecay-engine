"""
tests/test_api/test_curriculum_api.py
──────────────────────────────────────
Integration tests for /v1/curriculum/* endpoints.

Validates:
  • Authenticated provisioner can create full hierarchy
  • Invalid parent IDs return 404
  • Unauthenticated requests return 401
  • Unauthorized roles (student) return 403
  • API_CLIENT role succeeds (server-to-server integration)
  • Topic creation preserves engine-critical fields
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

from app.core.enums import UserRole  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.deps import get_db  # noqa: E402
from app.deps_auth import get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User  # noqa: E402


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_user(role="api_client", user_id=None):
    """Create a mock User ORM object."""
    user = MagicMock(spec=User)
    user.id = user_id or uuid.uuid4()
    user.email = f"{role}@test.com"
    user.name = f"Test {role}"
    user.role = role
    user.is_active = True
    user.institution_id = None
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    return user


@pytest.fixture
def mock_db():
    db = MagicMock()
    return db


@pytest.fixture
def client(mock_db):
    """TestClient with DB override only — no auth override (for 401 tests)."""
    def override_get_db():
        yield mock_db
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def api_client_user():
    return _make_user(role="api_client")


@pytest.fixture
def authed_client(mock_db, api_client_user):
    """TestClient with both DB and auth overridden to api_client role."""
    def override_get_db():
        yield mock_db
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: api_client_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _make_authed_client(mock_db, user):
    """Create a TestClient authenticated as the given user."""
    def override_get_db():
        yield mock_db
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


# ══════════════════════════════════════════════════════════════════════════════
# 1. AUTHENTICATION & AUTHORIZATION
# ══════════════════════════════════════════════════════════════════════════════

class TestCurriculumAuth:
    """Authentication and authorization for curriculum provisioning."""

    def test_unauthenticated_subject_returns_401(self, client):
        """Requests without a JWT must be rejected."""
        resp = client.post("/v1/curriculum/subjects", json={"name": "Physics"})
        assert resp.status_code == 401

    def test_unauthenticated_module_returns_401(self, client):
        resp = client.post("/v1/curriculum/modules", json={
            "name": "Mechanics", "subject_id": str(uuid.uuid4()),
        })
        assert resp.status_code == 401

    def test_unauthenticated_chapter_returns_401(self, client):
        resp = client.post("/v1/curriculum/chapters", json={
            "name": "Newton's Laws", "module_id": str(uuid.uuid4()),
        })
        assert resp.status_code == 401

    def test_unauthenticated_topic_returns_401(self, client):
        resp = client.post("/v1/curriculum/topics", json={
            "name": "F=ma", "chapter_id": str(uuid.uuid4()),
        })
        assert resp.status_code == 401

    def test_student_cannot_create_subject(self, mock_db):
        """Student role must not be able to provision curriculum."""
        student = _make_user(role="student")
        c = _make_authed_client(mock_db, student)
        resp = c.post("/v1/curriculum/subjects", json={"name": "Physics"})
        assert resp.status_code == 403
        app.dependency_overrides.clear()

    def test_teacher_cannot_create_subject(self, mock_db):
        """Teacher role must not be able to provision curriculum."""
        teacher = _make_user(role="teacher")
        c = _make_authed_client(mock_db, teacher)
        resp = c.post("/v1/curriculum/subjects", json={"name": "Physics"})
        assert resp.status_code == 403
        app.dependency_overrides.clear()


# ══════════════════════════════════════════════════════════════════════════════
# 2. SUBJECT CREATION
# ══════════════════════════════════════════════════════════════════════════════

class TestSubjectCreation:
    """Subject creation by authorized roles."""

    @patch("app.services.curriculum_service.create_subject")
    def test_api_client_can_create_subject(self, mock_create, authed_client, mock_db):
        """API_CLIENT role must succeed — this is the platform integration path."""
        subject_id = uuid.uuid4()
        mock_subject = MagicMock()
        mock_subject.id = subject_id
        mock_subject.name = "Physics"
        mock_subject.institution_id = None
        mock_subject.course_id = None
        mock_subject.created_at = datetime.now(timezone.utc)
        mock_create.return_value = mock_subject

        resp = authed_client.post("/v1/curriculum/subjects", json={"name": "Physics"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Physics"
        assert data["id"] == str(subject_id)

    @patch("app.services.curriculum_service.create_subject")
    def test_super_admin_can_create_subject(self, mock_create, mock_db):
        """Super admin must succeed."""
        admin = _make_user(role="super_admin")
        c = _make_authed_client(mock_db, admin)

        subject_id = uuid.uuid4()
        mock_subject = MagicMock()
        mock_subject.id = subject_id
        mock_subject.name = "Chemistry"
        mock_subject.institution_id = None
        mock_subject.course_id = None
        mock_subject.created_at = datetime.now(timezone.utc)
        mock_create.return_value = mock_subject

        resp = c.post("/v1/curriculum/subjects", json={"name": "Chemistry"})
        assert resp.status_code == 201
        app.dependency_overrides.clear()

    @patch("app.services.curriculum_service.create_subject")
    def test_institution_admin_can_create_subject(self, mock_create, mock_db):
        """Institution admin must succeed."""
        inst_admin = _make_user(role="institution_admin")
        c = _make_authed_client(mock_db, inst_admin)

        subject_id = uuid.uuid4()
        mock_subject = MagicMock()
        mock_subject.id = subject_id
        mock_subject.name = "Biology"
        mock_subject.institution_id = None
        mock_subject.course_id = None
        mock_subject.created_at = datetime.now(timezone.utc)
        mock_create.return_value = mock_subject

        resp = c.post("/v1/curriculum/subjects", json={"name": "Biology"})
        assert resp.status_code == 201
        app.dependency_overrides.clear()


# ══════════════════════════════════════════════════════════════════════════════
# 3. PARENT VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

class TestParentValidation:
    """Invalid parent IDs must return 404."""

    def test_module_with_invalid_subject_returns_404(self, authed_client, mock_db):
        """Creating a module with a non-existent subject_id must fail."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        resp = authed_client.post("/v1/curriculum/modules", json={
            "name": "Mechanics",
            "subject_id": str(uuid.uuid4()),
        })
        assert resp.status_code == 404

    def test_chapter_with_invalid_module_returns_404(self, authed_client, mock_db):
        """Creating a chapter with a non-existent module_id must fail."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        resp = authed_client.post("/v1/curriculum/chapters", json={
            "name": "Newton's Laws",
            "module_id": str(uuid.uuid4()),
        })
        assert resp.status_code == 404

    def test_topic_with_invalid_chapter_returns_404(self, authed_client, mock_db):
        """Creating a topic with a non-existent chapter_id must fail."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        resp = authed_client.post("/v1/curriculum/topics", json={
            "name": "F=ma",
            "chapter_id": str(uuid.uuid4()),
        })
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# 4. TOPIC ENGINE FIELDS
# ══════════════════════════════════════════════════════════════════════════════

class TestTopicEngineFields:
    """Topic creation preserves engine-critical fields."""

    @patch("app.services.curriculum_service.create_topic")
    def test_topic_preserves_difficulty_and_weight(self, mock_create, authed_client, mock_db):
        """Custom difficulty and importance_weight must be preserved."""
        topic_id = uuid.uuid4()
        mock_topic = MagicMock()
        mock_topic.id = topic_id
        mock_topic.name = "Quantum Mechanics"
        mock_topic.chapter_id = uuid.uuid4()
        mock_topic.difficulty = 0.85
        mock_topic.importance_weight = 2.5
        mock_topic.created_at = datetime.now(timezone.utc)
        mock_create.return_value = mock_topic

        resp = authed_client.post("/v1/curriculum/topics", json={
            "name": "Quantum Mechanics",
            "chapter_id": str(mock_topic.chapter_id),
            "difficulty": 0.85,
            "importance_weight": 2.5,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["difficulty"] == 0.85
        assert data["importance_weight"] == 2.5

    @patch("app.services.curriculum_service.create_topic")
    def test_topic_uses_defaults_when_not_specified(self, mock_create, authed_client, mock_db):
        """Default difficulty=0.5 and importance_weight=1.0."""
        topic_id = uuid.uuid4()
        mock_topic = MagicMock()
        mock_topic.id = topic_id
        mock_topic.name = "Basics"
        mock_topic.chapter_id = uuid.uuid4()
        mock_topic.difficulty = 0.5
        mock_topic.importance_weight = 1.0
        mock_topic.created_at = datetime.now(timezone.utc)
        mock_create.return_value = mock_topic

        resp = authed_client.post("/v1/curriculum/topics", json={
            "name": "Basics",
            "chapter_id": str(mock_topic.chapter_id),
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["difficulty"] == 0.5
        assert data["importance_weight"] == 1.0


# ══════════════════════════════════════════════════════════════════════════════
# 5. INPUT VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

class TestCurriculumInputValidation:
    """Pydantic validation for malformed requests."""

    def test_subject_empty_name_returns_422(self, authed_client):
        resp = authed_client.post("/v1/curriculum/subjects", json={"name": ""})
        assert resp.status_code == 422

    def test_module_missing_subject_id_returns_422(self, authed_client):
        resp = authed_client.post("/v1/curriculum/modules", json={"name": "Test"})
        assert resp.status_code == 422

    def test_topic_difficulty_out_of_range_returns_422(self, authed_client):
        resp = authed_client.post("/v1/curriculum/topics", json={
            "name": "Test",
            "chapter_id": str(uuid.uuid4()),
            "difficulty": 1.5,
        })
        assert resp.status_code == 422
