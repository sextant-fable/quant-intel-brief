"""NewsAPI metadata collector."""

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


class NewsApiCollector(SourceCollector):
    """Collect market-news metadata from NewsAPI."""

    endpoint = "https://newsapi.org/v2/everything"

    def __init__(
        self,
        api_key: str | None = None,
        query: str = "quant finance OR ETF OR options",
        config: CollectorConfig | None = None,
        endpoint: str | None = None,
    ) -> None:
        super().__init__(
            source_name="newsapi",
            source_type="news_api",
            display_name="NewsAPI",
            config=config,
        )
        self.api_key = api_key
        self.query = query
        self.endpoint = endpoint or self.endpoint

    async def collect(self, client: httpx.AsyncClient | None = None) -> CollectorRunResult:
        fetched_at = utc_now()
        if not self.api_key:
            return self._result(
                status=CollectorStatus.FAILED,
                message="NEWSAPI_KEY is required.",
                fetched_at=fetched_at,
            )

        fetch = await self.fetch_json(
            self.endpoint,
            params={
                "q": self.query,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": self.config.max_items,
                "apiKey": self.api_key,
            },
            client=client,
        )
        if fetch.status != CollectorStatus.SUCCESS:
            return self._result(
                fetch.status,
                fetch.message or "NewsAPI request failed.",
                fetched_at,
            )

        data = fetch.data if isinstance(fetch.data, dict) else {}
        if data.get("status") == "error":
            code = str(data.get("code") or "")
            status = (
                CollectorStatus.RATE_LIMITED
                if "rate" in code.lower()
                else CollectorStatus.FAILED
            )
            return self._result(status, str(data.get("message") or code), fetched_at)

        articles_value = data.get("articles")
        articles = articles_value if isinstance(articles_value, list) else []
        items = [
            item
            for article in articles
            if (item := self._article_to_item(article, fetched_at))
        ]
        status = CollectorStatus.SUCCESS if items else CollectorStatus.EMPTY
        return self._result(status, f"Parsed {len(items)} NewsAPI article(s).", fetched_at, items)

    def _article_to_item(self, article: Any, fetched_at: datetime) -> CollectedItem | None:
        if not isinstance(article, dict):
            return None
        url = compact_text_for_storage(article.get("url"), max_chars=2000)
        title = compact_text_for_storage(article.get("title"))
        if not url or not title:
            return None

        source_value = article.get("source")
        source: dict[str, Any] = source_value if isinstance(source_value, dict) else {}
        canonical_url = canonicalize_url_for_storage(url)
        description = compact_text_for_storage(article.get("description"))
        source_item_id = hash_text(canonical_url)
        return CollectedItem(
            source_name=self.source_name,
            source_item_id=source_item_id,
            url=url,
            canonical_url=canonical_url,
            title=title,
            summary=description,
            excerpt=description,
            author=compact_text_for_storage(article.get("author")),
            publisher=compact_text_for_storage(source.get("name")),
            published_at=parse_datetime_utc(article.get("publishedAt")),
            fetched_at=fetched_at,
            raw_payload_hash=hash_text("|".join([source_item_id, title, description or ""])),
            raw_metadata={
                "source_id": source.get("id"),
                "source_name": source.get("name"),
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


__all__ = ["NewsApiCollector"]
