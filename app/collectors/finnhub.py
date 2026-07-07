"""Finnhub market news metadata collector."""

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


class FinnhubCollector(SourceCollector):
    """Collect Finnhub market-news metadata."""

    endpoint = "https://finnhub.io/api/v1/news"

    def __init__(
        self,
        api_key: str | None = None,
        category: str = "general",
        config: CollectorConfig | None = None,
        endpoint: str | None = None,
    ) -> None:
        super().__init__(
            source_name="finnhub",
            source_type="market_api",
            display_name="Finnhub",
            config=config,
        )
        self.api_key = api_key
        self.category = category
        self.endpoint = endpoint or self.endpoint

    async def collect(self, client: httpx.AsyncClient | None = None) -> CollectorRunResult:
        fetched_at = utc_now()
        if not self.api_key:
            return self._result(CollectorStatus.FAILED, "FINNHUB_API_KEY is required.", fetched_at)

        fetch = await self.fetch_json(
            self.endpoint,
            params={"category": self.category, "token": self.api_key},
            client=client,
        )
        if fetch.status != CollectorStatus.SUCCESS:
            return self._result(
                fetch.status,
                fetch.message or "Finnhub request failed.",
                fetched_at,
            )

        articles = fetch.data if isinstance(fetch.data, list) else []
        items = [
            item
            for article in articles
            if (item := self._article_to_item(article, fetched_at))
        ]
        status = CollectorStatus.SUCCESS if items else CollectorStatus.EMPTY
        return self._result(status, f"Parsed {len(items)} Finnhub article(s).", fetched_at, items)

    def _article_to_item(self, article: Any, fetched_at: datetime) -> CollectedItem | None:
        if not isinstance(article, dict):
            return None
        url = compact_text_for_storage(article.get("url"), max_chars=2000)
        title = compact_text_for_storage(article.get("headline"))
        if not url or not title:
            return None

        canonical_url = canonicalize_url_for_storage(url)
        summary = compact_text_for_storage(article.get("summary"))
        source_item_id = str(article.get("id") or hash_text(canonical_url))
        return CollectedItem(
            source_name=self.source_name,
            source_item_id=source_item_id,
            url=url,
            canonical_url=canonical_url,
            title=title,
            summary=summary,
            excerpt=summary,
            publisher=compact_text_for_storage(article.get("source")),
            published_at=parse_datetime_utc(article.get("datetime")),
            fetched_at=fetched_at,
            raw_payload_hash=hash_text("|".join([source_item_id, title, summary or ""])),
            raw_metadata={
                "category": article.get("category"),
                "related": article.get("related"),
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


__all__ = ["FinnhubCollector"]
