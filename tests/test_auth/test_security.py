"""
tests/test_auth/test_security.py
─────────────────────────────────
Unit tests for app/core/security.py — password hashing, JWT, token hashing.
No database required.
"""

import os

# Set up environment BEFORE importing app modules
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-unit-tests-minimum-length-required-64-chars-long")
os.environ.setdefault("APP_ENV", "testing")

from app.config import get_settings  # noqa: E402
get_settings.cache_clear()

import pytest  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402
from jose import jwt, JWTError  # noqa: E402

from app.core.constants import TOKEN_TYPE_ACCESS, TOKEN_TYPE_REFRESH  # noqa: E402
from app.core.security import (  # noqa: E402
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_token_hash,
)

settings = get_settings()


# ── Password hashing tests ───────────────────────────────────────────────────

class TestPasswordHashing:
    def test_hash_produces_non_empty_string(self):
        hashed = hash_password("mypassword")
        assert isinstance(hashed, str)
        assert len(hashed) > 0
        assert hashed != "mypassword"

    def test_verification_succeeds_with_correct_password(self):
        hashed = hash_password("mypassword")
        assert verify_password("mypassword", hashed) is True

    def test_verification_fails_with_wrong_password(self):
        hashed = hash_password("mypassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_hash_is_different_each_time_due_to_salt(self):
        hash1 = hash_password("mypassword")
        hash2 = hash_password("mypassword")
        assert hash1 != hash2

    def test_empty_password_hashes_and_verifies(self):
        hashed = hash_password("")
        assert verify_password("", hashed) is True

    def test_long_password_hashes_and_verifies(self):
        plain = "a" * 72  # bcrypt max input length
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_verify_fails_with_empty_against_real_hash(self):
        hashed = hash_password("realpassword")
        assert verify_password("", hashed) is False

    def test_verify_returns_false_on_invalid_hash(self):
        assert verify_password("password", "not-a-valid-hash") is False


# ── JWT access token tests ───────────────────────────────────────────────────

class TestAccessToken:
    def test_contains_correct_claims(self):
        token = create_access_token(subject="user-123", role="student")
        payload = decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["role"] == "student"
        assert payload["type"] == TOKEN_TYPE_ACCESS
        assert "exp" in payload
        assert "iat" in payload

    def test_type_is_access(self):
        token = create_access_token(subject="user-123", role="student")
        payload = decode_token(token)
        assert payload["type"] == TOKEN_TYPE_ACCESS

    def test_extra_claims_included(self):
        token = create_access_token(
            subject="user-123", role="admin",
            extra_claims={"tenant_id": "t-1", "custom": 42},
        )
        payload = decode_token(token)
        assert payload["tenant_id"] == "t-1"
        assert payload["custom"] == 42

    def test_expiry_matches_configured_minutes(self):
        token = create_access_token(subject="user", role="student")
        payload = decode_token(token)
        iat = datetime.fromtimestamp(payload["iat"], timezone.utc)
        exp = datetime.fromtimestamp(payload["exp"], timezone.utc)
        expected = settings.access_token_expire_minutes * 60
        assert abs((exp - iat).total_seconds() - expected) < 5

    def test_no_extra_claims_produces_clean_payload(self):
        token = create_access_token(subject="s", role="r")
        payload = decode_token(token)
        assert payload["sub"] == "s"
        assert payload["role"] == "r"


# ── JWT refresh token tests ──────────────────────────────────────────────────

class TestRefreshToken:
    def test_contains_correct_claims(self):
        token = create_refresh_token(subject="user-123")
        payload = decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["type"] == TOKEN_TYPE_REFRESH
        assert "exp" in payload
        assert "iat" in payload

    def test_type_is_refresh(self):
        token = create_refresh_token(subject="user-123")
        payload = decode_token(token)
        assert payload["type"] == TOKEN_TYPE_REFRESH

    def test_expiry_matches_configured_days(self):
        token = create_refresh_token(subject="user")
        payload = decode_token(token)
        iat = datetime.fromtimestamp(payload["iat"], timezone.utc)
        exp = datetime.fromtimestamp(payload["exp"], timezone.utc)
        expected = settings.refresh_token_expire_days * 86400
        assert abs((exp - iat).total_seconds() - expected) < 5

    def test_does_not_contain_role_claim(self):
        token = create_refresh_token(subject="user-123")
        payload = decode_token(token)
        assert "role" not in payload


# ── Token decoding edge cases ────────────────────────────────────────────────

class TestTokenDecoding:
    def test_decodes_correct_payload(self):
        token = create_access_token(
            subject="user-123", role="admin",
            extra_claims={"int_val": 123, "bool_val": True},
        )
        payload = decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["int_val"] == 123
        assert payload["bool_val"] is True

    def test_expired_token_raises_jwt_error(self):
        expired = datetime.now(timezone.utc) - timedelta(minutes=1)
        token = jwt.encode(
            {"sub": "user", "exp": expired},
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(JWTError):
            decode_token(token)

    def test_wrong_secret_raises_jwt_error(self):
        token = jwt.encode(
            {"sub": "user", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
            "wrong-secret-key",
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(JWTError):
            decode_token(token)

    def test_malformed_token_raises_jwt_error(self):
        with pytest.raises(JWTError):
            decode_token("not.a.valid.jwt")

    def test_completely_invalid_string_raises_jwt_error(self):
        with pytest.raises(JWTError):
            decode_token("garbage")


# ── Token hashing tests ─────────────────────────────────────────────────────

class TestTokenHash:
    def test_returns_64_char_hex_string(self):
        h = get_token_hash("some-token")
        assert len(h) == 64
        int(h, 16)  # validates it's valid hex

    def test_is_deterministic(self):
        assert get_token_hash("token-A") == get_token_hash("token-A")

    def test_different_inputs_produce_different_hashes(self):
        assert get_token_hash("token-A") != get_token_hash("token-B")

    def test_empty_string_produces_valid_hash(self):
        h = get_token_hash("")
        assert len(h) == 64
        int(h, 16)
