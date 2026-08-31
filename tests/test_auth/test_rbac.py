"""
tests/test_auth/test_rbac.py
─────────────────────────────
Unit tests for app/deps_auth.py — RBAC and authentication dependencies.
Uses mock DB sessions. No PostgreSQL required.
"""

import os
import uuid

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-unit-tests-minimum-length-required-64-chars-long")
os.environ.setdefault("APP_ENV", "testing")

from app.config import get_settings  # noqa: E402
get_settings.cache_clear()

import pytest  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402
from jose import jwt  # noqa: E402

from app.core.enums import UserRole  # noqa: E402
from app.core.exceptions import (  # noqa: E402
    AccountDisabledError,
    AuthenticationError,
    AuthorizationError,
)
from app.core.security import create_access_token  # noqa: E402
from app.deps_auth import (  # noqa: E402
    get_current_user,
    require_admin,
    require_any_authenticated,
    require_institution_admin,
    require_roles,
    require_teacher,
)

settings = get_settings()


# ── Helpers ───────────────────────────────────────────────────────────────────

class MockUser:
    """Minimal mock user with required attributes."""

    def __init__(self, user_id=None, role="student", is_active=True):
        self.id = user_id or uuid.uuid4()
        self.role = role if isinstance(role, str) else role.value
        self.is_active = is_active
        self.email = f"{self.role}@test.com"
        self.name = f"Test {self.role}"


def _mock_db(user=None):
    """Create a mock DB where query(User).filter(...).first() returns user."""
    db = MagicMock()
    filter_mock = MagicMock()
    filter_mock.first.return_value = user
    query_mock = MagicMock()
    query_mock.filter.return_value = filter_mock
    db.query.return_value = query_mock
    return db


# ══════════════════════════════════════════════════════════════════════════════
# get_current_user tests
# ══════════════════════════════════════════════════════════════════════════════

class TestGetCurrentUser:
    def test_returns_user_with_valid_token(self):
        user = MockUser(role=UserRole.STUDENT)
        db = _mock_db(user)
        token = create_access_token(subject=str(user.id), role=user.role)

        result = get_current_user(token=token, db=db)
        assert result.id == user.id

    def test_raises_auth_error_with_no_token(self):
        db = _mock_db()
        with pytest.raises(AuthenticationError, match="Authentication required"):
            get_current_user(token=None, db=db)

    def test_raises_auth_error_with_malformed_token(self):
        db = _mock_db()
        with pytest.raises(AuthenticationError):
            get_current_user(token="invalid.token.string", db=db)

    def test_raises_auth_error_with_expired_token(self):
        expired = datetime.now(timezone.utc) - timedelta(minutes=1)
        token = jwt.encode(
            {"sub": str(uuid.uuid4()), "type": "access", "exp": expired},
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        db = _mock_db()
        with pytest.raises(AuthenticationError):
            get_current_user(token=token, db=db)

    def test_raises_auth_error_with_refresh_token_type(self):
        """Using a refresh token where access token is expected."""
        token = jwt.encode(
            {
                "sub": str(uuid.uuid4()),
                "type": "refresh",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                "iat": datetime.now(timezone.utc),
            },
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        db = _mock_db()
        with pytest.raises(AuthenticationError, match="Invalid token type"):
            get_current_user(token=token, db=db)

    def test_raises_auth_error_when_user_not_found(self):
        db = _mock_db(user=None)
        token = create_access_token(subject=str(uuid.uuid4()), role="student")
        with pytest.raises(AuthenticationError, match="User not found"):
            get_current_user(token=token, db=db)

    def test_raises_account_disabled_when_inactive(self):
        user = MockUser(is_active=False)
        db = _mock_db(user)
        token = create_access_token(subject=str(user.id), role=user.role)
        with pytest.raises(AccountDisabledError):
            get_current_user(token=token, db=db)

    def test_raises_auth_error_with_missing_sub_claim(self):
        token = jwt.encode(
            {
                "type": "access",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        db = _mock_db()
        with pytest.raises(AuthenticationError):
            get_current_user(token=token, db=db)

    def test_raises_auth_error_with_invalid_uuid_sub(self):
        token = jwt.encode(
            {
                "sub": "not-a-uuid",
                "type": "access",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        db = _mock_db()
        with pytest.raises(AuthenticationError):
            get_current_user(token=token, db=db)


# ══════════════════════════════════════════════════════════════════════════════
# require_roles tests
# ══════════════════════════════════════════════════════════════════════════════

class TestRequireAdmin:
    """require_admin allows only SUPER_ADMIN."""

    def test_super_admin_passes(self):
        user = MockUser(role=UserRole.SUPER_ADMIN)
        checker = require_admin
        result = checker(user)
        assert result.id == user.id

    @pytest.mark.parametrize("role", [
        UserRole.INSTITUTION_ADMIN,
        UserRole.TEACHER,
        UserRole.STUDENT,
        UserRole.API_CLIENT,
    ])
    def test_non_admin_roles_fail(self, role):
        user = MockUser(role=role)
        with pytest.raises(AuthorizationError):
            require_admin(user)


class TestRequireInstitutionAdmin:
    """require_institution_admin allows SUPER_ADMIN and INSTITUTION_ADMIN."""

    @pytest.mark.parametrize("role", [
        UserRole.SUPER_ADMIN,
        UserRole.INSTITUTION_ADMIN,
    ])
    def test_allowed_roles_pass(self, role):
        user = MockUser(role=role)
        result = require_institution_admin(user)
        assert result.id == user.id

    @pytest.mark.parametrize("role", [
        UserRole.TEACHER,
        UserRole.STUDENT,
        UserRole.API_CLIENT,
    ])
    def test_denied_roles_fail(self, role):
        user = MockUser(role=role)
        with pytest.raises(AuthorizationError):
            require_institution_admin(user)


class TestRequireTeacher:
    """require_teacher allows SUPER_ADMIN, INSTITUTION_ADMIN, TEACHER."""

    @pytest.mark.parametrize("role", [
        UserRole.SUPER_ADMIN,
        UserRole.INSTITUTION_ADMIN,
        UserRole.TEACHER,
    ])
    def test_allowed_roles_pass(self, role):
        user = MockUser(role=role)
        result = require_teacher(user)
        assert result.id == user.id

    @pytest.mark.parametrize("role", [
        UserRole.STUDENT,
        UserRole.API_CLIENT,
    ])
    def test_denied_roles_fail(self, role):
        user = MockUser(role=role)
        with pytest.raises(AuthorizationError):
            require_teacher(user)


class TestRequireAnyAuthenticated:
    """require_any_authenticated allows all 5 roles."""

    @pytest.mark.parametrize("role", list(UserRole))
    def test_all_roles_pass(self, role):
        user = MockUser(role=role)
        result = require_any_authenticated(user)
        assert result.id == user.id


class TestCustomRequireRoles:
    def test_custom_combination_passes(self):
        checker = require_roles(UserRole.STUDENT, UserRole.TEACHER)
        student = MockUser(role=UserRole.STUDENT)
        teacher = MockUser(role=UserRole.TEACHER)
        assert checker(student).id == student.id
        assert checker(teacher).id == teacher.id

    def test_custom_combination_fails(self):
        checker = require_roles(UserRole.STUDENT, UserRole.TEACHER)
        admin = MockUser(role=UserRole.SUPER_ADMIN)
        with pytest.raises(AuthorizationError):
            checker(admin)

    def test_single_role_checker(self):
        checker = require_roles(UserRole.API_CLIENT)
        api = MockUser(role=UserRole.API_CLIENT)
        assert checker(api).id == api.id

        student = MockUser(role=UserRole.STUDENT)
        with pytest.raises(AuthorizationError):
            checker(student)


# ══════════════════════════════════════════════════════════════════════════════
# Role enum validation
# ══════════════════════════════════════════════════════════════════════════════

class TestRoleEnumValidation:
    def test_all_five_roles_exist(self):
        values = {r.value for r in UserRole}
        assert values == {
            "super_admin", "institution_admin", "teacher", "student", "api_client"
        }

    def test_authorization_error_has_403_status(self):
        user = MockUser(role=UserRole.STUDENT)
        with pytest.raises(AuthorizationError) as exc_info:
            require_admin(user)
        assert exc_info.value.status_code == 403

    def test_authorization_error_contains_role_info(self):
        user = MockUser(role=UserRole.STUDENT)
        with pytest.raises(AuthorizationError) as exc_info:
            require_admin(user)
        assert "student" in str(exc_info.value.message).lower()
