"""Local source collection settings helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SOURCE_ENV_KEYS = (
    "RSS_FEED_URLS",
    "SEC_USER_AGENT",
    "SEC_CIK",
    "ARXIV_SEARCH_QUERY",
    "GITHUB_QUERY",
    "GITHUB_TOKEN",
    "FRED_API_KEY",
    "FRED_SERIES_ID",
    "NEWSAPI_KEY",
    "NEWSAPI_QUERY",
    "GDELT_QUERY",
    "ALPHAVANTAGE_API_KEY",
    "ALPHAVANTAGE_TOPICS",
    "FINNHUB_API_KEY",
    "FINNHUB_CATEGORY",
    "REDDIT_ACCESS_TOKEN",
    "REDDIT_USER_AGENT",
    "REDDIT_QUERY",
    "REDDIT_SUBREDDIT",
    "YOUTUBE_API_KEY",
    "YOUTUBE_QUERY",
    "X_BEARER_TOKEN",
    "X_QUERY",
    "STACKEXCHANGE_KEY",
    "STACKEXCHANGE_QUERY",
    "STACKEXCHANGE_SITE",
    "QUANTCONNECT_USER_ID",
    "QUANTCONNECT_TOKEN",
    "QUANTCONNECT_ORGANIZATION_ID",
)


@dataclass(frozen=True, slots=True)
class SavedSourceSettings:
    """Saved local source settings without exposing secrets."""

    rss_feed_urls: str
    sec_user_agent: str
    sec_cik: str
    arxiv_search_query: str
    github_query: str
    has_github_token: bool
    has_fred_api_key: bool
    fred_series_id: str
    has_newsapi_key: bool
    newsapi_query: str
    gdelt_query: str
    has_alphavantage_api_key: bool
    alphavantage_topics: str
    has_finnhub_api_key: bool
    finnhub_category: str
    has_reddit_access_token: bool
    reddit_user_agent: str
    reddit_query: str
    reddit_subreddit: str
    has_youtube_api_key: bool
    youtube_query: str
    has_x_bearer_token: bool
    x_query: str
    has_stackexchange_key: bool
    stackexchange_query: str
    stackexchange_site: str
    has_quantconnect_user_id: bool
    has_quantconnect_token: bool
    quantconnect_organization_id: str


def load_source_settings(env_path: Path) -> SavedSourceSettings:
    """Load saved source settings from a local env file."""
    values = read_env_values(env_path)
    return SavedSourceSettings(
        rss_feed_urls=values.get("RSS_FEED_URLS", ""),
        sec_user_agent=values.get("SEC_USER_AGENT", ""),
        sec_cik=values.get("SEC_CIK", "0000320193"),
        arxiv_search_query=values.get("ARXIV_SEARCH_QUERY", "cat:q-fin*"),
        github_query=values.get("GITHUB_QUERY", "quant finance language:Python"),
        has_github_token=bool(values.get("GITHUB_TOKEN")),
        has_fred_api_key=bool(values.get("FRED_API_KEY")),
        fred_series_id=values.get("FRED_SERIES_ID", "FEDFUNDS"),
        has_newsapi_key=bool(values.get("NEWSAPI_KEY")),
        newsapi_query=values.get("NEWSAPI_QUERY", "quant finance OR ETF OR options"),
        gdelt_query=values.get("GDELT_QUERY", "quant finance"),
        has_alphavantage_api_key=bool(values.get("ALPHAVANTAGE_API_KEY")),
        alphavantage_topics=values.get(
            "ALPHAVANTAGE_TOPICS",
            "financial_markets,economy_macro",
        ),
        has_finnhub_api_key=bool(values.get("FINNHUB_API_KEY")),
        finnhub_category=values.get("FINNHUB_CATEGORY", "general"),
        has_reddit_access_token=bool(values.get("REDDIT_ACCESS_TOKEN")),
        reddit_user_agent=values.get("REDDIT_USER_AGENT", ""),
        reddit_query=values.get("REDDIT_QUERY", "quant finance OR algotrading"),
        reddit_subreddit=values.get("REDDIT_SUBREDDIT", ""),
        has_youtube_api_key=bool(values.get("YOUTUBE_API_KEY")),
        youtube_query=values.get("YOUTUBE_QUERY", "quant finance"),
        has_x_bearer_token=bool(values.get("X_BEARER_TOKEN")),
        x_query=values.get("X_QUERY", "quant finance lang:en"),
        has_stackexchange_key=bool(values.get("STACKEXCHANGE_KEY")),
        stackexchange_query=values.get("STACKEXCHANGE_QUERY", "quant finance"),
        stackexchange_site=values.get("STACKEXCHANGE_SITE", "quant"),
        has_quantconnect_user_id=bool(values.get("QUANTCONNECT_USER_ID")),
        has_quantconnect_token=bool(values.get("QUANTCONNECT_TOKEN")),
        quantconnect_organization_id=values.get("QUANTCONNECT_ORGANIZATION_ID", ""),
    )


def save_source_settings(
    env_path: Path,
    *,
    rss_feed_urls: str,
    sec_user_agent: str,
    sec_cik: str,
    arxiv_search_query: str,
    github_query: str,
    github_token: str | None,
    clear_github_token: bool = False,
    fred_api_key: str | None,
    clear_fred_api_key: bool = False,
    fred_series_id: str,
    newsapi_key: str | None,
    clear_newsapi_key: bool = False,
    newsapi_query: str,
    gdelt_query: str,
    alphavantage_api_key: str | None,
    clear_alphavantage_api_key: bool = False,
    alphavantage_topics: str,
    finnhub_api_key: str | None,
    clear_finnhub_api_key: bool = False,
    finnhub_category: str,
    reddit_access_token: str | None,
    clear_reddit_access_token: bool = False,
    reddit_user_agent: str,
    reddit_query: str,
    reddit_subreddit: str,
    youtube_api_key: str | None,
    clear_youtube_api_key: bool = False,
    youtube_query: str,
    x_bearer_token: str | None,
    clear_x_bearer_token: bool = False,
    x_query: str,
    stackexchange_key: str | None,
    clear_stackexchange_key: bool = False,
    stackexchange_query: str,
    stackexchange_site: str,
    quantconnect_user_id: str | None,
    clear_quantconnect_user_id: bool = False,
    quantconnect_token: str | None,
    clear_quantconnect_token: bool = False,
    quantconnect_organization_id: str,
) -> SavedSourceSettings:
    """Persist source settings to `.env`, preserving blank secrets unless cleared."""
    existing = read_env_values(env_path)
    next_github_token = _next_secret_value(
        existing.get("GITHUB_TOKEN", ""),
        github_token,
        clear=clear_github_token,
    )
    next_fred_api_key = _next_secret_value(
        existing.get("FRED_API_KEY", ""),
        fred_api_key,
        clear=clear_fred_api_key,
    )
    next_newsapi_key = _next_secret_value(
        existing.get("NEWSAPI_KEY", ""),
        newsapi_key,
        clear=clear_newsapi_key,
    )
    next_alphavantage_api_key = _next_secret_value(
        existing.get("ALPHAVANTAGE_API_KEY", ""),
        alphavantage_api_key,
        clear=clear_alphavantage_api_key,
    )
    next_finnhub_api_key = _next_secret_value(
        existing.get("FINNHUB_API_KEY", ""),
        finnhub_api_key,
        clear=clear_finnhub_api_key,
    )
    next_reddit_access_token = _next_secret_value(
        existing.get("REDDIT_ACCESS_TOKEN", ""),
        reddit_access_token,
        clear=clear_reddit_access_token,
    )
    next_youtube_api_key = _next_secret_value(
        existing.get("YOUTUBE_API_KEY", ""),
        youtube_api_key,
        clear=clear_youtube_api_key,
    )
    next_x_bearer_token = _next_secret_value(
        existing.get("X_BEARER_TOKEN", ""),
        x_bearer_token,
        clear=clear_x_bearer_token,
    )
    next_stackexchange_key = _next_secret_value(
        existing.get("STACKEXCHANGE_KEY", ""),
        stackexchange_key,
        clear=clear_stackexchange_key,
    )
    next_quantconnect_user_id = _next_secret_value(
        existing.get("QUANTCONNECT_USER_ID", ""),
        quantconnect_user_id,
        clear=clear_quantconnect_user_id,
    )
    next_quantconnect_token = _next_secret_value(
        existing.get("QUANTCONNECT_TOKEN", ""),
        quantconnect_token,
        clear=clear_quantconnect_token,
    )
    updates = {
        "RSS_FEED_URLS": _normalize_list_value(rss_feed_urls),
        "SEC_USER_AGENT": sec_user_agent.strip(),
        "SEC_CIK": sec_cik.strip() or "0000320193",
        "ARXIV_SEARCH_QUERY": arxiv_search_query.strip() or "cat:q-fin*",
        "GITHUB_QUERY": github_query.strip() or "quant finance language:Python",
        "GITHUB_TOKEN": next_github_token,
        "FRED_API_KEY": next_fred_api_key,
        "FRED_SERIES_ID": fred_series_id.strip() or "FEDFUNDS",
        "NEWSAPI_KEY": next_newsapi_key,
        "NEWSAPI_QUERY": newsapi_query.strip() or "quant finance OR ETF OR options",
        "GDELT_QUERY": gdelt_query.strip() or "quant finance",
        "ALPHAVANTAGE_API_KEY": next_alphavantage_api_key,
        "ALPHAVANTAGE_TOPICS": alphavantage_topics.strip()
        or "financial_markets,economy_macro",
        "FINNHUB_API_KEY": next_finnhub_api_key,
        "FINNHUB_CATEGORY": finnhub_category.strip() or "general",
        "REDDIT_ACCESS_TOKEN": next_reddit_access_token,
        "REDDIT_USER_AGENT": reddit_user_agent.strip(),
        "REDDIT_QUERY": reddit_query.strip() or "quant finance OR algotrading",
        "REDDIT_SUBREDDIT": reddit_subreddit.strip(),
        "YOUTUBE_API_KEY": next_youtube_api_key,
        "YOUTUBE_QUERY": youtube_query.strip() or "quant finance",
        "X_BEARER_TOKEN": next_x_bearer_token,
        "X_QUERY": x_query.strip() or "quant finance lang:en",
        "STACKEXCHANGE_KEY": next_stackexchange_key,
        "STACKEXCHANGE_QUERY": stackexchange_query.strip() or "quant finance",
        "STACKEXCHANGE_SITE": stackexchange_site.strip() or "quant",
        "QUANTCONNECT_USER_ID": next_quantconnect_user_id,
        "QUANTCONNECT_TOKEN": next_quantconnect_token,
        "QUANTCONNECT_ORGANIZATION_ID": quantconnect_organization_id.strip(),
    }
    write_env_updates(env_path, updates, SOURCE_ENV_KEYS, header="Source collection")
    return SavedSourceSettings(
        rss_feed_urls=updates["RSS_FEED_URLS"],
        sec_user_agent=updates["SEC_USER_AGENT"],
        sec_cik=updates["SEC_CIK"],
        arxiv_search_query=updates["ARXIV_SEARCH_QUERY"],
        github_query=updates["GITHUB_QUERY"],
        has_github_token=bool(next_github_token),
        has_fred_api_key=bool(next_fred_api_key),
        fred_series_id=updates["FRED_SERIES_ID"],
        has_newsapi_key=bool(next_newsapi_key),
        newsapi_query=updates["NEWSAPI_QUERY"],
        gdelt_query=updates["GDELT_QUERY"],
        has_alphavantage_api_key=bool(next_alphavantage_api_key),
        alphavantage_topics=updates["ALPHAVANTAGE_TOPICS"],
        has_finnhub_api_key=bool(next_finnhub_api_key),
        finnhub_category=updates["FINNHUB_CATEGORY"],
        has_reddit_access_token=bool(next_reddit_access_token),
        reddit_user_agent=updates["REDDIT_USER_AGENT"],
        reddit_query=updates["REDDIT_QUERY"],
        reddit_subreddit=updates["REDDIT_SUBREDDIT"],
        has_youtube_api_key=bool(next_youtube_api_key),
        youtube_query=updates["YOUTUBE_QUERY"],
        has_x_bearer_token=bool(next_x_bearer_token),
        x_query=updates["X_QUERY"],
        has_stackexchange_key=bool(next_stackexchange_key),
        stackexchange_query=updates["STACKEXCHANGE_QUERY"],
        stackexchange_site=updates["STACKEXCHANGE_SITE"],
        has_quantconnect_user_id=bool(next_quantconnect_user_id),
        has_quantconnect_token=bool(next_quantconnect_token),
        quantconnect_organization_id=updates["QUANTCONNECT_ORGANIZATION_ID"],
    )


def read_env_values(env_path: Path) -> dict[str, str]:
    """Read simple KEY=value pairs from a local env file."""
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def write_env_updates(
    env_path: Path,
    updates: dict[str, str],
    ordered_keys: tuple[str, ...],
    *,
    header: str,
) -> None:
    """Write selected KEY=value updates while preserving unrelated env lines."""
    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    seen: set[str] = set()
    next_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                next_lines.append(f"{key}={updates[key]}")
                seen.add(key)
                continue
        next_lines.append(line)

    if not next_lines:
        next_lines.append("# Local settings")

    missing = [key for key in ordered_keys if key not in seen]
    if missing:
        if next_lines[-1].strip():
            next_lines.append("")
        next_lines.append(f"# {header}")
        next_lines.extend(f"{key}={updates[key]}" for key in missing)

    env_path.write_text("\n".join(next_lines).rstrip() + "\n", encoding="utf-8")


def _next_secret_value(existing_value: str, submitted_value: str | None, *, clear: bool) -> str:
    submitted = (submitted_value or "").strip()
    if clear:
        return ""
    return submitted or existing_value


def _normalize_list_value(value: str) -> str:
    return ",".join(part.strip() for part in re.split(r"[\n,]+", value) if part.strip())


__all__ = [
    "SOURCE_ENV_KEYS",
    "SavedSourceSettings",
    "load_source_settings",
    "read_env_values",
    "save_source_settings",
    "write_env_updates",
]
