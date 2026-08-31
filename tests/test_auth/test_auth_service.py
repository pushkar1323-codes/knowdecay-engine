"""
tests/test_auth/test_auth_service.py
─────────────────────────────────────
Unit tests for app/services/auth_service.py.
Uses mock DB sessions to test auth business logic without PostgreSQL.
"""

import os
import uuid

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-unit-tests-minimum-length-required-64-chars-long")
os.environ.setdefault("APP_ENV", "testing")

from app.config import get_settings  # noqa: E402
get_settings.cache_clear()

import pytest  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402
from unittest.mock import MagicMock, patch, PropertyMock  # noqa: E402

from app.core.exceptions import AuthenticationError, AccountDisabledError  # noqa: E402
from app.core.security import (  # noqa: E402
    hash_password,
    create_refresh_token,
    get_token_hash,
    decode_token,
)
from app.models.refresh_token import RefreshToken  # noqa: E402
from app.services import auth_service  # noqa: E402


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_user(
    user_id=None,
    email="test@example.com",
    password="Password123",
    role="student",
    is_active=True,
    has_password=True,
):
    """Build a mock User with real password hash."""
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.email = email
    user.name = "Test User"
    user.role = role
    user.is_active = is_active
    user.password_hash = hash_password(password) if has_password else None
    return user


def _mock_db_returning_user(user):
    """Create a mock session where query(User).filter(...).first() returns user."""
    db = MagicMock()
    filter_mock = MagicMock()
    filter_mock.first.return_value = user
    query_mock = MagicMock()
    query_mock.filter.return_value = filter_mock
    db.query.return_value = query_mock
    return db


# ── authenticate_user tests ──────────────────────────────────────────────────

class TestAuthenticateUser:
    def test_success_with_valid_credentials(self):
        user = _make_user(password="Correct123")
        db = _mock_db_returning_user(user)

        result = auth_service.authenticate_user(db, "test@example.com", "Correct123")
        assert result.id == user.id

    def test_fails_with_unknown_email(self):
        db = _mock_db_returning_user(None)

        with pytest.raises(AuthenticationError, match="Invalid email or password"):
            auth_service.authenticate_user(db, "nobody@example.com", "Password123")

    def test_fails_with_wrong_password(self):
        user = _make_user(password="Correct123")
        db = _mock_db_returning_user(user)

        with pytest.raises(AuthenticationError, match="Invalid email or password"):
            auth_service.authenticate_user(db, "test@example.com", "WrongPass123")

    def test_fails_when_user_has_no_password_hash(self):
        user = _make_user(has_password=False)
        db = _mock_db_returning_user(user)

        with pytest.raises(AuthenticationError, match="Invalid email or password"):
            auth_service.authenticate_user(db, "test@example.com", "Password123")

    def test_raises_account_disabled_when_inactive(self):
        user = _make_user(password="Correct123", is_active=False)
        db = _mock_db_returning_user(user)

        with pytest.raises(AccountDisabledError):
            auth_service.authenticate_user(db, "test@example.com", "Correct123")


# ── create_tokens tests ─────────────────────────────────────────────────────

class TestCreateTokens:
    def test_returns_all_required_fields(self):
        user = _make_user()
        db = MagicMock()

        result = auth_service.create_tokens(db, user)

        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "bearer"
        assert isinstance(result["expires_in"], int)
        assert result["expires_in"] > 0

    def test_access_token_contains_user_claims(self):
        user = _make_user(role="teacher")
        db = MagicMock()

        result = auth_service.create_tokens(db, user)
        payload = decode_token(result["access_token"])

        assert payload["sub"] == str(user.id)
        assert payload["role"] == "teacher"
        assert payload["type"] == "access"

    def test_stores_hashed_refresh_token_in_db(self):
        user = _make_user()
        db = MagicMock()

        auth_service.create_tokens(db, user)

        db.add.assert_called_once()
        db.commit.assert_called_once()

        # Verify the stored object is a RefreshToken with correct user_id
        stored = db.add.call_args[0][0]
        assert isinstance(stored, RefreshToken)
        assert stored.user_id == user.id
        assert len(stored.token_hash) == 64  # SHA-256 hex

    def test_expires_in_matches_config(self):
        user = _make_user()
        db = MagicMock()

        result = auth_service.create_tokens(db, user)
        expected = get_settings().access_token_expire_minutes * 60
        assert result["expires_in"] == expected


# ── refresh_access_token tests ───────────────────────────────────────────────

class TestRefreshAccessToken:
    def _setup_refresh(self, user, db, revoked=False, expired=False):
        """Create a real refresh token and set up mock DB to find it."""
        refresh_token = create_refresh_token(subject=str(user.id))
        token_hash = get_token_hash(refresh_token)

        db_token = MagicMock(spec=RefreshToken)
        db_token.token_hash = token_hash
        db_token.user_id = user.id
        db_token.revoked = revoked
        db_token.expires_at = (
            datetime.now(timezone.utc) - timedelta(days=1) if expired
            else datetime.now(timezone.utc) + timedelta(days=7)
        )

        # query(RefreshToken).filter(...).first() -> db_token
        rt_filter = MagicMock()
        rt_filter.first.return_value = None if revoked else db_token

        # query(User).filter(...).first() -> user
        user_filter = MagicMock()
        user_filter.first.return_value = user

        def query_side_effect(model):
            mock = MagicMock()
            if model is RefreshToken or (hasattr(model, '__tablename__') and model.__tablename__ == 'refresh_tokens'):
                mock.filter.return_value = rt_filter
            else:
                mock.filter.return_value = user_filter
            return mock

        db.query.side_effect = query_side_effect
        return refresh_token

    def test_success_returns_new_token_pair(self):
        user = _make_user()
        db = MagicMock()
        refresh_token = self._setup_refresh(user, db)

        result = auth_service.refresh_access_token(db, refresh_token)

        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "bearer"

    def test_fails_with_invalid_jwt(self):
        db = MagicMock()

        with pytest.raises(AuthenticationError, match="Invalid or expired refresh token"):
            auth_service.refresh_access_token(db, "invalid.jwt.token")

    def test_fails_with_access_token_type(self):
        """Using an access token as refresh token should fail."""
        from app.core.security import create_access_token
        token = create_access_token(subject=str(uuid.uuid4()), role="student")
        db = MagicMock()

        with pytest.raises(AuthenticationError, match="Invalid token type"):
            auth_service.refresh_access_token(db, token)

    def test_fails_when_token_not_in_db(self):
        user = _make_user()
        db = MagicMock()
        refresh_token = create_refresh_token(subject=str(user.id))

        # DB returns None for the token lookup
        filter_mock = MagicMock()
        filter_mock.first.return_value = None
        query_mock = MagicMock()
        query_mock.filter.return_value = filter_mock
        db.query.return_value = query_mock

        with pytest.raises(AuthenticationError, match="invalid or has been revoked"):
            auth_service.refresh_access_token(db, refresh_token)


# ── revoke_refresh_token tests ───────────────────────────────────────────────

class TestRevokeRefreshToken:
    def test_marks_token_as_revoked(self):
        db = MagicMock()
        db_token = MagicMock()
        db_token.revoked = False

        filter_mock = MagicMock()
        filter_mock.first.return_value = db_token
        query_mock = MagicMock()
        query_mock.filter.return_value = filter_mock
        db.query.return_value = query_mock

        auth_service.revoke_refresh_token(db, "some-token")

        assert db_token.revoked is True
        db.commit.assert_called_once()

    def test_no_error_if_token_not_found(self):
        db = MagicMock()
        filter_mock = MagicMock()
        filter_mock.first.return_value = None
        query_mock = MagicMock()
        query_mock.filter.return_value = filter_mock
        db.query.return_value = query_mock

        # Should not raise
        auth_service.revoke_refresh_token(db, "nonexistent-token")


# ── revoke_all_user_tokens tests ─────────────────────────────────────────────

class TestRevokeAllUserTokens:
    def test_revokes_all_and_returns_count(self):
        db = MagicMock()
        user_id = uuid.uuid4()

        # Mock: query().filter().update() -> count
        update_mock = MagicMock(return_value=3)
        filter_mock = MagicMock()
        filter_mock.update = update_mock
        query_mock = MagicMock()
        query_mock.filter.return_value = filter_mock
        db.query.return_value = query_mock

        count = auth_service.revoke_all_user_tokens(db, user_id)

        assert count == 3
        db.commit.assert_called_once()

    def test_returns_zero_when_no_tokens(self):
        db = MagicMock()
        user_id = uuid.uuid4()

        update_mock = MagicMock(return_value=0)
        filter_mock = MagicMock()
        filter_mock.update = update_mock
        query_mock = MagicMock()
        query_mock.filter.return_value = filter_mock
        db.query.return_value = query_mock

        count = auth_service.revoke_all_user_tokens(db, user_id)
        assert count == 0
