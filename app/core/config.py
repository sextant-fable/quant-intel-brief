"""Environment-backed application configuration."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "quant-intel-brief"
    app_timezone: str = "America/New_York"
    database_url: str = "sqlite:///data/app.db"
    log_level: str = "INFO"

    web_host: str = "127.0.0.1"
    web_port: int = 8000
    dashboard_base_url: str = "http://127.0.0.1:8000"
    dashboard_title: str = "Quant Intel Brief"

    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    newsapi_key: SecretStr | None = None
    gdelt_api_key: SecretStr | None = None
    alphavantage_api_key: SecretStr | None = None
    finnhub_api_key: SecretStr | None = None
    fred_api_key: SecretStr | None = None
    sec_user_agent: str | None = None

    github_token: SecretStr | None = None
    reddit_client_id: SecretStr | None = None
    reddit_client_secret: SecretStr | None = None
    youtube_api_key: SecretStr | None = None
    x_bearer_token: SecretStr | None = None
    stackexchange_key: SecretStr | None = None
    quantconnect_token: SecretStr | None = None

    email_provider: str = "smtp"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: SecretStr | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str | None = None
    resend_api_key: SecretStr | None = None
    resend_from: str | None = None
    report_recipients: str | None = None

    collector_timeout_seconds: int = 30
    max_items_per_source: int = 200
    http_retry_attempts: int = 2
    http_retry_backoff_seconds: int = 1
    store_full_text: bool = False
    enable_premium_browser: bool = False

    def public_summary(self) -> dict[str, Any]:
        """Return non-secret settings safe for health and status responses."""
        return {
            "app_env": self.app_env,
            "app_name": self.app_name,
            "app_timezone": self.app_timezone,
            "database_url": self._redact_database_url(self.database_url),
            "dashboard_base_url": self.dashboard_base_url,
            "dashboard_title": self.dashboard_title,
            "store_full_text": self.store_full_text,
            "enable_premium_browser": self.enable_premium_browser,
        }

    @staticmethod
    def _redact_database_url(database_url: str) -> str:
        if "@" not in database_url:
            return database_url
        scheme, rest = database_url.split("://", 1)
        return f"{scheme}://***@{rest.split('@', 1)[1]}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings for application wiring."""
    return Settings()


def reset_settings_cache() -> None:
    """Clear cached settings, mainly for tests."""
    get_settings.cache_clear()
