"""
app/config.py
─────────────
Centralised settings management using pydantic-settings.
All configuration is loaded from environment variables / .env file.
New settings must be added here — never hardcoded elsewhere.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",          # ignore unknown env vars silently
    )

    # ── Application ───────────────────────────────────────────────────────────
    app_name: str = "KnowDecay Engine"
    app_version: str = "0.1.0"
    app_env: str = "development"       # development | production

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "postgresql://knowdecay:knowdecay@localhost:5432/knowdecay"

    # ── Server ───────────────────────────────────────────────────────────────
    host: str = "0.0.0.0"                  # Bind address
    port: int = 8000                       # Bind port
    workers: int = 1                       # Gunicorn worker count (recommended: 2×CPU+1)

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = "INFO"            # DEBUG | INFO | WARNING | ERROR

    # ── Engine: Retention ─────────────────────────────────────────────────────
    # target recall probability — scheduler aims to keep retention above this
    default_retention_threshold: float = 0.85
    # base decay rate (λ) for Ebbinghaus forgetting curve
    base_decay_rate: float = 0.1
    # minimum floor — prevents retention from decaying to zero
    min_retention_floor: float = 0.05

    # ── Engine: Priority ──────────────────────────────────────────────────────
    # multiplier cap applied when exam is imminent
    priority_exam_weight: float = 1.5
    # how much topic difficulty amplifies urgency
    priority_difficulty_weight: float = 1.2
    # base weight applied to raw urgency signal
    priority_urgency_weight: float = 1.0

    # ── Engine: ML Augmentation ──────────────────────────────────────────
    # ML augments the deterministic engine — never replaces it
    ml_enabled: bool = False                     # master kill switch
    ml_blend_weight: float = 0.0                 # 0.0 = pure deterministic
    ml_max_stability_correction: float = 0.3     # ±30% max correction
    ml_max_decay_modifier_range: float = 0.3     # decay modifier 0.7–1.3

    # ── Infrastructure ────────────────────────────────────────────────────
    log_format: str = "text"               # text (dev) | json (production)
    cors_origins: str = ""                 # comma-separated origins, empty = disabled
    trusted_hosts: str = "*"               # Future: trusted host validation middleware
    request_timeout: int = 30              # Future: request timeout enforcement middleware
    max_batch_size: int = 100              # max items in batch endpoints

    # ── Authentication ────────────────────────────────────────────────────
    jwt_secret_key: str = ""               # REQUIRED — set via JWT_SECRET_KEY env var
    jwt_algorithm: str = "HS256"           # JWT signing algorithm
    access_token_expire_minutes: int = 30  # Access token TTL
    refresh_token_expire_days: int = 7     # Refresh token TTL
    bcrypt_rounds: int = 12               # bcrypt cost factor
    registration_enabled: bool = True      # allow public user registration

    @property
    def is_production(self) -> bool:
        """True if running in production environment."""
        return self.app_env.lower() == "production"

    @property
    def is_development(self) -> bool:
        """True if running in development environment."""
        return self.app_env.lower() == "development"

    @property
    def is_testing(self) -> bool:
        """True if running in testing environment."""
        return self.app_env.lower() == "testing"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        if not self.cors_origins:
            return []
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache()
def get_settings() -> Settings:
    """
    Return a cached singleton Settings instance.
    Use as a FastAPI dependency: Depends(get_settings)
    or call directly in engine modules.
    """
    return Settings()
