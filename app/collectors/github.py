"""GitHub repository search metadata collector."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.collectors.base import (
    CollectedItem,
    CollectorConfig,
    CollectorRunResult,
    CollectorStatus,
    SourceCollector,
    canonicalize_url_for_storage,
    compact_text_for_storage,
    hash_text,
    parse_datetime_utc,
)
from app.core.timezones import utc_now


class GitHubCollector(SourceCollector):
    """Collect GitHub repository metadata through the REST search API."""

    endpoint = "https://api.github.com/search/repositories"

    def __init__(
        self,
        token: str | None = None,
        query: str = "quant finance language:Python",
        config: CollectorConfig | None = None,
        endpoint: str | None = None,
    ) -> None:
        super().__init__(
            source_name="github",
            source_type="developer_api",
            display_name="GitHub",
            config=config,
        )
        self.token = token
        self.query = query
        self.endpoint = endpoint or self.endpoint

    async def collect(self, client: httpx.AsyncClient | None = None) -> CollectorRunResult:
        fetched_at = utc_now()
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        fetch = await self.fetch_json(
            self.endpoint,
            params={
                "q": self.query,
                "sort": "updated",
                "order": "desc",
                "per_page": self.config.max_items,
            },
            headers=headers,
            client=client,
        )
        if fetch.status != CollectorStatus.SUCCESS:
            return self._result(fetch.status, fetch.message or "GitHub request failed.", fetched_at)

        data = fetch.data if isinstance(fetch.data, dict) else {}
        message = str(data.get("message") or "")
        if "rate limit" in message.lower():
            return self._result(CollectorStatus.RATE_LIMITED, message, fetched_at)

        repos_value = data.get("items")
        repos = repos_value if isinstance(repos_value, list) else []
        items = [
            item for repo in repos if (item := self._repo_to_item(repo, fetched_at))
        ]
        status = CollectorStatus.SUCCESS if items else CollectorStatus.EMPTY
        return self._result(
            status,
            f"Parsed {len(items)} GitHub repository item(s).",
            fetched_at,
            items,
        )

    def _repo_to_item(self, repo: Any, fetched_at: datetime) -> CollectedItem | None:
        if not isinstance(repo, dict):
            return None
        url = compact_text_for_storage(repo.get("html_url"), max_chars=2000)
        full_name = compact_text_for_storage(repo.get("full_name"))
        if not url or not full_name:
            return None

        owner_value = repo.get("owner")
        owner: dict[str, Any] = owner_value if isinstance(owner_value, dict) else {}
        summary = compact_text_for_storage(repo.get("description"))
        source_item_id = str(repo.get("id") or full_name)
        license_value = repo.get("license")
        license_data: dict[str, Any] = license_value if isinstance(license_value, dict) else {}
        return CollectedItem(
            source_name=self.source_name,
            source_item_id=source_item_id,
            url=url,
            canonical_url=canonicalize_url_for_storage(url),
            title=full_name,
            summary=summary,
            excerpt=summary,
            author=compact_text_for_storage(owner.get("login")),
            publisher="GitHub",
            published_at=parse_datetime_utc(repo.get("updated_at")),
            fetched_at=fetched_at,
            language=compact_text_for_storage(repo.get("language")),
            raw_payload_hash=hash_text("|".join([source_item_id, full_name, summary or ""])),
            raw_metadata={
                "stars": repo.get("stargazers_count"),
                "forks": repo.get("forks_count"),
                "open_issues": repo.get("open_issues_count"),
                "license": license_data.get("spdx_id"),
            },
        )

    def _result(
        self,
        status: CollectorStatus,
        message: str,
        fetched_at: datetime,
        items: list[CollectedItem] | None = None,
    ) -> CollectorRunResult:
        return CollectorRunResult(
            source_name=self.source_name,
            source_type=self.source_type,
            display_name=self.display_name,
            status=status,
            message=message,
            source_url=self.endpoint,
            fetched_at=fetched_at,
            items=items or [],
        )


__all__ = ["GitHubCollector"]
