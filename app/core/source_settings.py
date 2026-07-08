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
    updates = {
        "RSS_FEED_URLS": _normalize_list_value(rss_feed_urls),
        "SEC_USER_AGENT": sec_user_agent.strip(),
        "SEC_CIK": sec_cik.strip() or "0000320193",
        "ARXIV_SEARCH_QUERY": arxiv_search_query.strip() or "cat:q-fin*",
        "GITHUB_QUERY": github_query.strip() or "quant finance language:Python",
        "GITHUB_TOKEN": next_github_token,
        "FRED_API_KEY": next_fred_api_key,
        "FRED_SERIES_ID": fred_series_id.strip() or "FEDFUNDS",
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
