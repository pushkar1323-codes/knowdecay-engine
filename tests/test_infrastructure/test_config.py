"""
tests/test_infrastructure/test_config.py
──────────────────────────────────────────
Tests for Phase 12 configuration management:
  - Default settings load correctly
  - Environment-specific properties
  - New Phase 12 settings
  - CORS origins parsing
"""

import pytest

from app.config import Settings


# ── Default Settings ──────────────────────────────────────────────────────────

class TestDefaultSettings:
    """Verify default settings values."""

    def setup_method(self):
        """Create a fresh Settings instance for each test."""
        self.settings = Settings(
            _env_file=None,  # Don't load .env during testing
            database_url="postgresql://test:test@localhost:5432/test",
            app_env="development",  # Explicit default — avoids inheriting APP_ENV from env
        )

    def test_app_name_default(self):
        assert self.settings.app_name == "KnowDecay Engine"

    def test_app_version_default(self):
        assert self.settings.app_version == "0.1.0"

    def test_app_env_default(self):
        assert self.settings.app_env == "development"

    def test_log_level_default(self):
        assert self.settings.log_level == "INFO"

    def test_retention_threshold_default(self):
        assert self.settings.default_retention_threshold == 0.85

    def test_base_decay_rate_default(self):
        assert self.settings.base_decay_rate == 0.1

    def test_min_retention_floor_default(self):
        assert self.settings.min_retention_floor == 0.05

    def test_ml_enabled_default(self):
        assert self.settings.ml_enabled is False

    def test_ml_blend_weight_default(self):
        assert self.settings.ml_blend_weight == 0.0


# ── Phase 12 Settings ────────────────────────────────────────────────────────

class TestPhase12Settings:
    """Verify Phase 12 infrastructure settings."""

    def setup_method(self):
        self.settings = Settings(
            _env_file=None,
            database_url="postgresql://test:test@localhost:5432/test",
        )

    def test_log_format_default(self):
        assert self.settings.log_format == "text"

    def test_cors_origins_default_empty(self):
        assert self.settings.cors_origins == ""

    def test_trusted_hosts_default(self):
        assert self.settings.trusted_hosts == "*"

    def test_request_timeout_default(self):
        assert self.settings.request_timeout == 30

    def test_max_batch_size_default(self):
        assert self.settings.max_batch_size == 100


# ── Environment Properties ───────────────────────────────────────────────────

class TestEnvironmentProperties:
    """Verify environment detection properties."""

    def test_is_development(self):
        s = Settings(
            _env_file=None,
            database_url="postgresql://test:test@localhost:5432/test",
            app_env="development",
        )
        assert s.is_development is True
        assert s.is_production is False
        assert s.is_testing is False

    def test_is_production(self):
        s = Settings(
            _env_file=None,
            database_url="postgresql://test:test@localhost:5432/test",
            app_env="production",
        )
        assert s.is_production is True
        assert s.is_development is False
        assert s.is_testing is False

    def test_is_testing(self):
        s = Settings(
            _env_file=None,
            database_url="postgresql://test:test@localhost:5432/test",
            app_env="testing",
        )
        assert s.is_testing is True
        assert s.is_development is False
        assert s.is_production is False

    def test_case_insensitive_env(self):
        s = Settings(
            _env_file=None,
            database_url="postgresql://test:test@localhost:5432/test",
            app_env="Production",
        )
        assert s.is_production is True


# ── CORS Origins Parsing ─────────────────────────────────────────────────────

class TestCORSOrigins:
    """Verify CORS origins parsing from comma-separated string."""

    def test_empty_origins(self):
        s = Settings(
            _env_file=None,
            database_url="postgresql://test:test@localhost:5432/test",
            cors_origins="",
        )
        assert s.cors_origins_list == []

    def test_single_origin(self):
        s = Settings(
            _env_file=None,
            database_url="postgresql://test:test@localhost:5432/test",
            cors_origins="http://localhost:3000",
        )
        assert s.cors_origins_list == ["http://localhost:3000"]

    def test_multiple_origins(self):
        s = Settings(
            _env_file=None,
            database_url="postgresql://test:test@localhost:5432/test",
            cors_origins="http://localhost:3000,https://app.example.com,https://admin.example.com",
        )
        assert s.cors_origins_list == [
            "http://localhost:3000",
            "https://app.example.com",
            "https://admin.example.com",
        ]

    def test_origins_with_whitespace(self):
        s = Settings(
            _env_file=None,
            database_url="postgresql://test:test@localhost:5432/test",
            cors_origins="  http://a.com , http://b.com  ",
        )
        assert s.cors_origins_list == ["http://a.com", "http://b.com"]

    def test_origins_trailing_comma_ignored(self):
        s = Settings(
            _env_file=None,
            database_url="postgresql://test:test@localhost:5432/test",
            cors_origins="http://a.com,",
        )
        assert s.cors_origins_list == ["http://a.com"]
