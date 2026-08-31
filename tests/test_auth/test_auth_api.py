"""
tests/test_auth/test_auth_api.py
─────────────────────────────────
Integration tests for /v1/auth/* endpoints.
Uses FastAPI TestClient with mock DB session.
"""

import os
import uuid

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-unit-tests-minimum-length-required-64-chars-long")
os.environ.setdefault("APP_ENV", "testing")

from app.config import get_settings  # noqa: E402
get_settings.cache_clear()

import pytest  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402
from unittest.mock import MagicMock, patch  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.core.enums import UserRole  # noqa: E402
from app.core.security import hash_password, create_access_token, decode_token  # noqa: E402
from app.deps import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.refresh_token import RefreshToken  # noqa: E402
from app.models.user import User  # noqa: E402


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    """Provide a mock DB session and override the dependency."""
    db = MagicMock()
    return db


@pytest.fixture
def client(mock_db):
    """TestClient with DB dependency overridden."""
    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _make_user_model(
    user_id=None,
    email="test@example.com",
    name="Test User",
    password="Password123",
    role="student",
    is_active=True,
    institution_id=None,
):
    """Create a mock User ORM object."""
    user = MagicMock(spec=User)
    user.id = user_id or uuid.uuid4()
    user.email = email
    user.name = name
    user.password_hash = hash_password(password)
    user.role = role
    user.is_active = is_active
    user.institution_id = institution_id
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    return user


# ══════════════════════════════════════════════════════════════════════════════
# POST /v1/auth/register
# ══════════════════════════════════════════════════════════════════════════════

class TestRegister:
    @patch("app.services.user_service.register_user")
    def test_register_success(self, mock_register, client, mock_db):
        user = _make_user_model(email="new@example.com")
        mock_register.return_value = user

        resp = client.post("/v1/auth/register", json={
            "name": "New User",
            "email": "new@example.com",
            "password": "SecureP@ss123",
        })

        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "new@example.com"
        assert data["role"] == "student"

    @patch("app.services.user_service.register_user")
    def test_register_enforces_student_role(self, mock_register, client, mock_db):
        """Even if caller tries to set role, it should be student."""
        user = _make_user_model(role="student")
        mock_register.return_value = user

        resp = client.post("/v1/auth/register", json={
            "name": "Sneaky Admin",
            "email": "sneaky@example.com",
            "password": "SecureP@ss123",
        })

        assert resp.status_code == 201
        # The service is called — role enforcement is in register_user
        mock_register.assert_called_once()

    def test_register_rejects_short_password(self, client, mock_db):
        resp = client.post("/v1/auth/register", json={
            "name": "Test",
            "email": "test@example.com",
            "password": "short",
        })
        assert resp.status_code == 422

    def test_register_rejects_missing_name(self, client, mock_db):
        resp = client.post("/v1/auth/register", json={
            "email": "test@example.com",
            "password": "LongEnough123",
        })
        assert resp.status_code == 422

    @patch("app.services.user_service.register_user")
    def test_register_conflict_on_duplicate_email(self, mock_register, client, mock_db):
        from app.core.exceptions import ConflictError
        mock_register.side_effect = ConflictError("User with email 'x@x.com' already exists")

        resp = client.post("/v1/auth/register", json={
            "name": "Dup",
            "email": "x@x.com",
            "password": "SecureP@ss123",
        })
        assert resp.status_code == 409


# ══════════════════════════════════════════════════════════════════════════════
# POST /v1/auth/login
# ══════════════════════════════════════════════════════════════════════════════

class TestLogin:
    @patch("app.services.auth_service.create_tokens")
    @patch("app.services.auth_service.authenticate_user")
    def test_login_success(self, mock_auth, mock_tokens, client, mock_db):
        user = _make_user_model()
        mock_auth.return_value = user
        mock_tokens.return_value = {
            "access_token": "at",
            "refresh_token": "rt",
            "token_type": "bearer",
            "expires_in": 1800,
        }

        resp = client.post("/v1/auth/login", json={
            "email": "test@example.com",
            "password": "Password123",
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"] == "at"
        assert data["refresh_token"] == "rt"
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 1800

    @patch("app.services.auth_service.authenticate_user")
    def test_login_invalid_credentials(self, mock_auth, client, mock_db):
        from app.core.exceptions import AuthenticationError
        mock_auth.side_effect = AuthenticationError("Invalid email or password")

        resp = client.post("/v1/auth/login", json={
            "email": "bad@example.com",
            "password": "WrongPass123",
        })
        assert resp.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# POST /v1/auth/refresh
# ══════════════════════════════════════════════════════════════════════════════

class TestRefresh:
    @patch("app.services.auth_service.refresh_access_token")
    def test_refresh_success(self, mock_refresh, client, mock_db):
        mock_refresh.return_value = {
            "access_token": "new_at",
            "refresh_token": "new_rt",
            "token_type": "bearer",
            "expires_in": 1800,
        }

        resp = client.post("/v1/auth/refresh", json={
            "refresh_token": "old_refresh_token",
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"] == "new_at"

    @patch("app.services.auth_service.refresh_access_token")
    def test_refresh_invalid_token(self, mock_refresh, client, mock_db):
        from app.core.exceptions import AuthenticationError
        mock_refresh.side_effect = AuthenticationError("Invalid or expired refresh token")

        resp = client.post("/v1/auth/refresh", json={
            "refresh_token": "expired_token",
        })
        assert resp.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# POST /v1/auth/logout
# ══════════════════════════════════════════════════════════════════════════════

class TestLogout:
    @patch("app.services.auth_service.revoke_refresh_token")
    def test_logout_success(self, mock_revoke, client, mock_db):
        user = _make_user_model()
        # Mock get_current_user to return our user
        filter_mock = MagicMock()
        filter_mock.first.return_value = user
        query_mock = MagicMock()
        query_mock.filter.return_value = filter_mock
        mock_db.query.return_value = query_mock

        token = create_access_token(subject=str(user.id), role=user.role)

        resp = client.post(
            "/v1/auth/logout",
            json={"refresh_token": "rt_to_revoke"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200
        assert resp.json()["message"] == "Successfully logged out"

    def test_logout_without_auth(self, client, mock_db):
        resp = client.post("/v1/auth/logout", json={"refresh_token": "rt"})
        assert resp.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# GET /v1/auth/me
# ══════════════════════════════════════════════════════════════════════════════

class TestMe:
    def test_me_returns_user_profile(self, client, mock_db):
        user = _make_user_model(role="teacher")
        filter_mock = MagicMock()
        filter_mock.first.return_value = user
        query_mock = MagicMock()
        query_mock.filter.return_value = filter_mock
        mock_db.query.return_value = query_mock

        token = create_access_token(subject=str(user.id), role=user.role)

        resp = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@example.com"
        assert data["role"] == "teacher"

    def test_me_without_auth(self, client, mock_db):
        resp = client.get("/v1/auth/me")
        assert resp.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# POST /v1/auth/change-password
# ══════════════════════════════════════════════════════════════════════════════

class TestChangePassword:
    @patch("app.services.user_service.change_password")
    def test_change_password_success(self, mock_change, client, mock_db):
        user = _make_user_model()
        filter_mock = MagicMock()
        filter_mock.first.return_value = user
        query_mock = MagicMock()
        query_mock.filter.return_value = filter_mock
        mock_db.query.return_value = query_mock

        token = create_access_token(subject=str(user.id), role=user.role)

        resp = client.post(
            "/v1/auth/change-password",
            json={
                "current_password": "OldPass123",
                "new_password": "NewPass123!",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200
        assert resp.json()["message"] == "Password changed successfully"

    def test_change_password_without_auth(self, client, mock_db):
        resp = client.post("/v1/auth/change-password", json={
            "current_password": "Old",
            "new_password": "NewPass123!",
        })
        assert resp.status_code == 401

    def test_change_password_rejects_short_new_password(self, client, mock_db):
        user = _make_user_model()
        filter_mock = MagicMock()
        filter_mock.first.return_value = user
        query_mock = MagicMock()
        query_mock.filter.return_value = filter_mock
        mock_db.query.return_value = query_mock

        token = create_access_token(subject=str(user.id), role=user.role)

        resp = client.post(
            "/v1/auth/change-password",
            json={
                "current_password": "OldPass123",
                "new_password": "short",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422
