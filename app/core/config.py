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

    llm_provider: str = "deepseek"
    llm_api_key: SecretStr | None = None
    llm_base_url: str | None = "https://api.deepseek.com"
    llm_model: str | None = "deepseek-chat"
    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    newsapi_key: SecretStr | None = None
    newsapi_query: str = "quant finance OR ETF OR options"
    gdelt_api_key: SecretStr | None = None
    gdelt_query: str = "quant finance"
    alphavantage_api_key: SecretStr | None = None
    alphavantage_topics: str = "financial_markets,economy_macro"
    finnhub_api_key: SecretStr | None = None
    finnhub_category: str = "general"
    rss_feed_urls: str | None = None
    fred_api_key: SecretStr | None = None
    fred_series_id: str = "FEDFUNDS"
    sec_user_agent: str | None = None
    sec_cik: str = "0000320193"
    arxiv_search_query: str = "cat:q-fin*"

    github_token: SecretStr | None = None
    github_query: str = "quant finance language:Python"
    reddit_client_id: SecretStr | None = None
    reddit_client_secret: SecretStr | None = None
    reddit_access_token: SecretStr | None = None
    reddit_user_agent: str | None = None
    reddit_query: str = "quant finance OR algotrading"
    reddit_subreddit: str | None = None
    youtube_api_key: SecretStr | None = None
    youtube_query: str = "quant finance"
    x_bearer_token: SecretStr | None = None
    x_query: str = "quant finance lang:en"
    stackexchange_key: SecretStr | None = None
    stackexchange_query: str = "quant finance"
    stackexchange_site: str = "quant"
    quantconnect_user_id: SecretStr | None = None
    quantconnect_token: SecretStr | None = None
    quantconnect_organization_id: str | None = None

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
    retention_days: int = 30
    enable_scheduler: bool = False
    daily_run_time: str = "07:00"
    store_full_text: bool = False
    enable_premium_browser: bool = False
    premium_rss_feed_urls: str | None = None

    def public_summary(self) -> dict[str, Any]:
        """Return non-secret settings safe for health and status responses."""
        return {
            "app_env": self.app_env,
            "app_name": self.app_name,
            "app_timezone": self.app_timezone,
            "database_url": self._redact_database_url(self.database_url),
            "dashboard_base_url": self.dashboard_base_url,
            "dashboard_title": self.dashboard_title,
            "llm_provider": self.llm_provider,
            "llm_base_url": self.llm_base_url or self.deepseek_base_url,
            "llm_model": self.llm_model or self.deepseek_model,
            "enable_scheduler": self.enable_scheduler,
            "daily_run_time": self.daily_run_time,
            "retention_days": self.retention_days,
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
