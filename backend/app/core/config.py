"""Application settings, read from environment variables (and .env in development)."""

from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


def _origin(url: str) -> str:
    parts = urlsplit(url.strip())
    return f"{parts.scheme}://{parts.netloc}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "production", "test"] = "development"

    # Required: the app refuses to start without it.
    mongodb_uri: str
    mongodb_db: str = "healthai"

    frontend_url: str = "http://localhost:3000"
    admin_url: str = "http://localhost:3001"
    trust_proxy: bool = True

    session_ttl_seconds: int = 60 * 60 * 24 * 7  # 7 days
    reset_token_ttl_seconds: int = 60 * 30  # 30 minutes
    max_body_bytes: int = 16 * 1024

    # --- AI ---
    # Empty = AI disabled: chat returns a clear 503 instead of pretending to work.
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-5-5"
    chat_effort: Literal["low", "medium", "high"] = "low"  # chat turns: keep latency low
    report_effort: Literal["low", "medium", "high"] = "medium"  # reports: more careful
    ai_timeout_seconds: float = 90.0

    # --- Chat limits ---
    max_message_chars: int = 2000
    max_user_messages_per_conversation: int = 20
    min_user_messages_for_report: int = 2

    @property
    def ai_configured(self) -> bool:
        return bool(self.anthropic_api_key.strip())

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def allowed_origins(self) -> set[str]:
        return {_origin(self.frontend_url), _origin(self.admin_url)}

    @property
    def session_cookie_name(self) -> str:
        # "__Host-" makes browsers require Secure + Path=/ + no Domain (HTTPS only).
        return "__Host-healthai_session" if self.is_production else "healthai_session"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
