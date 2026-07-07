"""X API recent-search metadata collector."""

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


class XApiCollector(SourceCollector):
    """Collect X post metadata from recent search."""

    endpoint = "https://api.x.com/2/tweets/search/recent"

    def __init__(
        self,
        bearer_token: str | None = None,
        query: str = "quant finance lang:en",
        config: CollectorConfig | None = None,
        endpoint: str | None = None,
    ) -> None:
        super().__init__(
            source_name="x_api",
            source_type="social_api",
            display_name="X API",
            config=config,
        )
        self.bearer_token = bearer_token
        self.query = query
        self.endpoint = endpoint or self.endpoint

    async def collect(self, client: httpx.AsyncClient | None = None) -> CollectorRunResult:
        fetched_at = utc_now()
        if not self.bearer_token:
            return self._result(CollectorStatus.FAILED, "X_BEARER_TOKEN is required.", fetched_at)

        fetch = await self.fetch_json(
            self.endpoint,
            params={
                "query": self.query,
                "max_results": min(max(self.config.max_items, 10), 100),
                "tweet.fields": "created_at,author_id,public_metrics,lang",
            },
            headers={"Authorization": f"Bearer {self.bearer_token}"},
            client=client,
        )
        if fetch.status != CollectorStatus.SUCCESS:
            return self._result(fetch.status, fetch.message or "X API request failed.", fetched_at)

        data = fetch.data if isinstance(fetch.data, dict) else {}
        tweets_value = data.get("data")
        tweets = tweets_value if isinstance(tweets_value, list) else []
        items = [item for tweet in tweets if (item := self._tweet_to_item(tweet, fetched_at))]
        status = CollectorStatus.SUCCESS if items else CollectorStatus.EMPTY
        return self._result(status, f"Parsed {len(items)} X post(s).", fetched_at, items)

    def _tweet_to_item(self, tweet: Any, fetched_at: datetime) -> CollectedItem | None:
        if not isinstance(tweet, dict):
            return None
        tweet_id = compact_text_for_storage(tweet.get("id"))
        text = compact_text_for_storage(tweet.get("text"), max_chars=240)
        if not tweet_id or not text:
            return None

        url = f"https://x.com/i/web/status/{tweet_id}"
        return CollectedItem(
            source_name=self.source_name,
            source_item_id=tweet_id,
            url=url,
            canonical_url=canonicalize_url_for_storage(url),
            title=text,
            summary=text,
            excerpt=text,
            author=compact_text_for_storage(tweet.get("author_id")),
            publisher="X",
            published_at=parse_datetime_utc(tweet.get("created_at")),
            fetched_at=fetched_at,
            language=compact_text_for_storage(tweet.get("lang")),
            raw_payload_hash=hash_text("|".join([tweet_id, text])),
            raw_metadata={
                "author_id": tweet.get("author_id"),
                "public_metrics": tweet.get("public_metrics")
                if isinstance(tweet.get("public_metrics"), dict)
                else {},
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


__all__ = ["XApiCollector"]
