"""
tests/test_auth/test_users_api.py
──────────────────────────────────
Integration tests for /v1/users/* admin endpoints.
Uses FastAPI TestClient with mock DB session.
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
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.deps import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User  # noqa: E402


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def client(mock_db):
    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _make_user(
    user_id=None,
    email="admin@example.com",
    role="super_admin",
    is_active=True,
    name="Admin User",
):
    user = MagicMock(spec=User)
    user.id = user_id or uuid.uuid4()
    user.email = email
    user.name = name
    user.role = role
    user.is_active = is_active
    user.institution_id = None
    user.password_hash = hash_password("Password123")
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    return user


def _auth_header(user):
    """Build Authorization header for a mock user."""
    token = create_access_token(subject=str(user.id), role=user.role)
    return {"Authorization": f"Bearer {token}"}


def _setup_auth_db(mock_db, auth_user):
    """Configure mock_db so get_current_user finds auth_user."""
    filter_mock = MagicMock()
    filter_mock.first.return_value = auth_user
    query_mock = MagicMock()
    query_mock.filter.return_value = filter_mock
    mock_db.query.return_value = query_mock


# ══════════════════════════════════════════════════════════════════════════════
# GET /v1/users — List users
# ══════════════════════════════════════════════════════════════════════════════

class TestListUsers:
    @patch("app.services.user_service.list_users")
    def test_admin_can_list_users(self, mock_list, client, mock_db):
        admin = _make_user(role="super_admin")
        _setup_auth_db(mock_db, admin)

        target_user = _make_user(email="student@example.com", role="student")
        mock_list.return_value = ([target_user], 1)

        resp = client.get("/v1/users", headers=_auth_header(admin))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["users"]) == 1

    @patch("app.services.user_service.list_users")
    def test_institution_admin_can_list(self, mock_list, client, mock_db):
        admin = _make_user(role="institution_admin")
        _setup_auth_db(mock_db, admin)
        mock_list.return_value = ([], 0)

        resp = client.get("/v1/users", headers=_auth_header(admin))
        assert resp.status_code == 200

    def test_student_cannot_list_users(self, client, mock_db):
        student = _make_user(role="student")
        _setup_auth_db(mock_db, student)

        resp = client.get("/v1/users", headers=_auth_header(student))
        assert resp.status_code == 403

    def test_no_auth_returns_401(self, client, mock_db):
        resp = client.get("/v1/users")
        assert resp.status_code == 401

    @patch("app.services.user_service.list_users")
    def test_pagination_params(self, mock_list, client, mock_db):
        admin = _make_user(role="super_admin")
        _setup_auth_db(mock_db, admin)
        mock_list.return_value = ([], 0)

        resp = client.get("/v1/users?page=2&page_size=10", headers=_auth_header(admin))
        assert resp.status_code == 200
        mock_list.assert_called_once()
        # Verify skip = (2-1) * 10 = 10
        call_kwargs = mock_list.call_args
        assert call_kwargs[1]["skip"] == 10
        assert call_kwargs[1]["limit"] == 10


# ══════════════════════════════════════════════════════════════════════════════
# GET /v1/users/{user_id} — Get user
# ══════════════════════════════════════════════════════════════════════════════

class TestGetUser:
    @patch("app.services.user_service.get_user_by_id")
    def test_admin_can_get_user(self, mock_get, client, mock_db):
        admin = _make_user(role="super_admin")
        _setup_auth_db(mock_db, admin)

        target = _make_user(email="student@test.com", role="student")
        mock_get.return_value = target

        resp = client.get(f"/v1/users/{target.id}", headers=_auth_header(admin))
        assert resp.status_code == 200
        assert resp.json()["email"] == "student@test.com"

    def test_student_cannot_get_user(self, client, mock_db):
        student = _make_user(role="student")
        _setup_auth_db(mock_db, student)

        resp = client.get(
            f"/v1/users/{uuid.uuid4()}", headers=_auth_header(student)
        )
        assert resp.status_code == 403

    @patch("app.services.user_service.get_user_by_id")
    def test_user_not_found_returns_404(self, mock_get, client, mock_db):
        from app.core.exceptions import NotFoundError

        admin = _make_user(role="super_admin")
        _setup_auth_db(mock_db, admin)
        target_id = uuid.uuid4()
        mock_get.side_effect = NotFoundError("User", str(target_id))

        resp = client.get(f"/v1/users/{target_id}", headers=_auth_header(admin))
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# PATCH /v1/users/{user_id} — Update user
# ══════════════════════════════════════════════════════════════════════════════

class TestUpdateUser:
    @patch("app.services.user_service.admin_update_user")
    def test_admin_can_update_user(self, mock_update, client, mock_db):
        admin = _make_user(role="super_admin")
        _setup_auth_db(mock_db, admin)

        target = _make_user(email="student@test.com", role="teacher", name="Updated")
        mock_update.return_value = target

        resp = client.patch(
            f"/v1/users/{target.id}",
            json={"name": "Updated", "role": "teacher"},
            headers=_auth_header(admin),
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "teacher"

    def test_student_cannot_update(self, client, mock_db):
        student = _make_user(role="student")
        _setup_auth_db(mock_db, student)

        resp = client.patch(
            f"/v1/users/{uuid.uuid4()}",
            json={"name": "Hacked"},
            headers=_auth_header(student),
        )
        assert resp.status_code == 403


# ══════════════════════════════════════════════════════════════════════════════
# POST /v1/users/{user_id}/activate
# ══════════════════════════════════════════════════════════════════════════════

class TestActivateUser:
    @patch("app.services.user_service.activate_user")
    def test_super_admin_can_activate(self, mock_activate, client, mock_db):
        admin = _make_user(role="super_admin")
        _setup_auth_db(mock_db, admin)

        target = _make_user(role="student", is_active=True)
        mock_activate.return_value = target

        resp = client.post(
            f"/v1/users/{target.id}/activate", headers=_auth_header(admin)
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is True

    def test_institution_admin_cannot_activate(self, client, mock_db):
        admin = _make_user(role="institution_admin")
        _setup_auth_db(mock_db, admin)

        resp = client.post(
            f"/v1/users/{uuid.uuid4()}/activate",
            headers=_auth_header(admin),
        )
        assert resp.status_code == 403

    def test_student_cannot_activate(self, client, mock_db):
        student = _make_user(role="student")
        _setup_auth_db(mock_db, student)

        resp = client.post(
            f"/v1/users/{uuid.uuid4()}/activate",
            headers=_auth_header(student),
        )
        assert resp.status_code == 403


# ══════════════════════════════════════════════════════════════════════════════
# POST /v1/users/{user_id}/deactivate
# ══════════════════════════════════════════════════════════════════════════════

class TestDeactivateUser:
    @patch("app.services.user_service.deactivate_user")
    def test_super_admin_can_deactivate(self, mock_deactivate, client, mock_db):
        admin = _make_user(role="super_admin")
        _setup_auth_db(mock_db, admin)

        target = _make_user(role="student", is_active=False)
        mock_deactivate.return_value = target

        resp = client.post(
            f"/v1/users/{target.id}/deactivate", headers=_auth_header(admin)
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_teacher_cannot_deactivate(self, client, mock_db):
        teacher = _make_user(role="teacher")
        _setup_auth_db(mock_db, teacher)

        resp = client.post(
            f"/v1/users/{uuid.uuid4()}/deactivate",
            headers=_auth_header(teacher),
        )
        assert resp.status_code == 403
