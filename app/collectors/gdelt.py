"""GDELT DOC API metadata collector."""

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


class GdeltCollector(SourceCollector):
    """Collect public article metadata from GDELT."""

    endpoint = "https://api.gdeltproject.org/api/v2/doc/doc"

    def __init__(
        self,
        query: str = "quant finance",
        config: CollectorConfig | None = None,
        endpoint: str | None = None,
    ) -> None:
        super().__init__(
            source_name="gdelt",
            source_type="public_api",
            display_name="GDELT",
            config=config,
        )
        self.query = query
        self.endpoint = endpoint or self.endpoint

    async def collect(self, client: httpx.AsyncClient | None = None) -> CollectorRunResult:
        fetched_at = utc_now()
        fetch = await self.fetch_json(
            self.endpoint,
            params={
                "query": self.query,
                "mode": "artlist",
                "format": "json",
                "maxrecords": self.config.max_items,
            },
            client=client,
        )
        if fetch.status != CollectorStatus.SUCCESS:
            return self._result(fetch.status, fetch.message or "GDELT request failed.", fetched_at)

        data = fetch.data if isinstance(fetch.data, dict) else {}
        articles_value = data.get("articles")
        articles = articles_value if isinstance(articles_value, list) else []
        items = [
            item
            for article in articles
            if (item := self._article_to_item(article, fetched_at))
        ]
        status = CollectorStatus.SUCCESS if items else CollectorStatus.EMPTY
        return self._result(status, f"Parsed {len(items)} GDELT article(s).", fetched_at, items)

    def _article_to_item(self, article: Any, fetched_at: datetime) -> CollectedItem | None:
        if not isinstance(article, dict):
            return None
        url = compact_text_for_storage(article.get("url"), max_chars=2000)
        title = compact_text_for_storage(article.get("title"))
        if not url or not title:
            return None

        canonical_url = canonicalize_url_for_storage(url)
        source_item_id = hash_text(canonical_url)
        summary = compact_text_for_storage(article.get("seendate"))
        return CollectedItem(
            source_name=self.source_name,
            source_item_id=source_item_id,
            url=url,
            canonical_url=canonical_url,
            title=title,
            summary=summary,
            excerpt=summary,
            publisher=compact_text_for_storage(article.get("sourceCommonName")),
            published_at=parse_datetime_utc(article.get("seendate")),
            fetched_at=fetched_at,
            language=compact_text_for_storage(article.get("language")),
            raw_payload_hash=hash_text("|".join([source_item_id, title, summary or ""])),
            raw_metadata={
                "domain": article.get("domain"),
                "source_country": article.get("sourceCountry"),
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


__all__ = ["GdeltCollector"]
