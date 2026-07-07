"""Alpha Vantage news sentiment metadata collector."""

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


class AlphaVantageCollector(SourceCollector):
    """Collect Alpha Vantage market news metadata."""

    endpoint = "https://www.alphavantage.co/query"

    def __init__(
        self,
        api_key: str | None = None,
        topics: str = "financial_markets,economy_macro",
        config: CollectorConfig | None = None,
        endpoint: str | None = None,
    ) -> None:
        super().__init__(
            source_name="alphavantage",
            source_type="market_api",
            display_name="Alpha Vantage",
            config=config,
        )
        self.api_key = api_key
        self.topics = topics
        self.endpoint = endpoint or self.endpoint

    async def collect(self, client: httpx.AsyncClient | None = None) -> CollectorRunResult:
        fetched_at = utc_now()
        if not self.api_key:
            return self._result(
                CollectorStatus.FAILED,
                "ALPHAVANTAGE_API_KEY is required.",
                fetched_at,
            )

        fetch = await self.fetch_json(
            self.endpoint,
            params={
                "function": "NEWS_SENTIMENT",
                "topics": self.topics,
                "limit": self.config.max_items,
                "apikey": self.api_key,
            },
            client=client,
        )
        if fetch.status != CollectorStatus.SUCCESS:
            return self._result(
                fetch.status,
                fetch.message or "Alpha Vantage request failed.",
                fetched_at,
            )

        data = fetch.data if isinstance(fetch.data, dict) else {}
        quota_message = str(data.get("Note") or data.get("Information") or "")
        if quota_message:
            status = (
                CollectorStatus.RATE_LIMITED
                if "rate" in quota_message.lower()
                else CollectorStatus.FAILED
            )
            return self._result(status, quota_message, fetched_at)

        feed_value = data.get("feed")
        feed = feed_value if isinstance(feed_value, list) else []
        items = [
            item for article in feed if (item := self._article_to_item(article, fetched_at))
        ]
        status = CollectorStatus.SUCCESS if items else CollectorStatus.EMPTY
        return self._result(
            status,
            f"Parsed {len(items)} Alpha Vantage item(s).",
            fetched_at,
            items,
        )

    def _article_to_item(self, article: Any, fetched_at: datetime) -> CollectedItem | None:
        if not isinstance(article, dict):
            return None
        url = compact_text_for_storage(article.get("url"), max_chars=2000)
        title = compact_text_for_storage(article.get("title"))
        if not url or not title:
            return None

        canonical_url = canonicalize_url_for_storage(url)
        summary = compact_text_for_storage(article.get("summary"))
        source_item_id = hash_text(canonical_url)
        authors = article.get("authors")
        author = ", ".join(str(item) for item in authors) if isinstance(authors, list) else authors
        ticker_sentiment = article.get("ticker_sentiment")
        topics = article.get("topics")
        return CollectedItem(
            source_name=self.source_name,
            source_item_id=source_item_id,
            url=url,
            canonical_url=canonical_url,
            title=title,
            summary=summary,
            excerpt=summary,
            author=compact_text_for_storage(author),
            publisher=compact_text_for_storage(article.get("source")),
            published_at=parse_datetime_utc(article.get("time_published")),
            fetched_at=fetched_at,
            raw_payload_hash=hash_text("|".join([source_item_id, title, summary or ""])),
            raw_metadata={
                "category_within_source": article.get("category_within_source"),
                "source_domain": article.get("source_domain"),
                "overall_sentiment_label": article.get("overall_sentiment_label"),
                "ticker_sentiment": ticker_sentiment if isinstance(ticker_sentiment, list) else [],
                "topics": topics if isinstance(topics, list) else [],
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


__all__ = ["AlphaVantageCollector"]
