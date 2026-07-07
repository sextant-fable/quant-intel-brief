"""YouTube Data API metadata collector."""

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


class YouTubeCollector(SourceCollector):
    """Collect YouTube video metadata from the official search API."""

    endpoint = "https://www.googleapis.com/youtube/v3/search"

    def __init__(
        self,
        api_key: str | None = None,
        query: str = "quant finance",
        config: CollectorConfig | None = None,
        endpoint: str | None = None,
    ) -> None:
        super().__init__(
            source_name="youtube",
            source_type="video_api",
            display_name="YouTube",
            config=config,
        )
        self.api_key = api_key
        self.query = query
        self.endpoint = endpoint or self.endpoint

    async def collect(self, client: httpx.AsyncClient | None = None) -> CollectorRunResult:
        fetched_at = utc_now()
        if not self.api_key:
            return self._result(CollectorStatus.FAILED, "YOUTUBE_API_KEY is required.", fetched_at)

        fetch = await self.fetch_json(
            self.endpoint,
            params={
                "part": "snippet",
                "q": self.query,
                "type": "video",
                "order": "date",
                "maxResults": min(self.config.max_items, 50),
                "key": self.api_key,
            },
            client=client,
        )
        if fetch.status != CollectorStatus.SUCCESS:
            return self._result(
                fetch.status,
                fetch.message or "YouTube request failed.",
                fetched_at,
            )

        data = fetch.data if isinstance(fetch.data, dict) else {}
        items_value = data.get("items")
        entries = items_value if isinstance(items_value, list) else []
        items = [item for entry in entries if (item := self._video_to_item(entry, fetched_at))]
        status = CollectorStatus.SUCCESS if items else CollectorStatus.EMPTY
        return self._result(status, f"Parsed {len(items)} YouTube video(s).", fetched_at, items)

    def _video_to_item(self, entry: Any, fetched_at: datetime) -> CollectedItem | None:
        if not isinstance(entry, dict):
            return None
        snippet_value = entry.get("snippet")
        snippet: dict[str, Any] = snippet_value if isinstance(snippet_value, dict) else {}
        id_value = entry.get("id")
        id_data: dict[str, Any] = id_value if isinstance(id_value, dict) else {}
        video_id = compact_text_for_storage(id_data.get("videoId"))
        title = compact_text_for_storage(snippet.get("title"))
        if not video_id or not title:
            return None

        url = f"https://www.youtube.com/watch?v={video_id}"
        summary = compact_text_for_storage(snippet.get("description"))
        return CollectedItem(
            source_name=self.source_name,
            source_item_id=video_id,
            url=url,
            canonical_url=canonicalize_url_for_storage(url),
            title=title,
            summary=summary,
            excerpt=summary,
            author=compact_text_for_storage(snippet.get("channelTitle")),
            publisher="YouTube",
            published_at=parse_datetime_utc(snippet.get("publishedAt")),
            fetched_at=fetched_at,
            raw_payload_hash=hash_text("|".join([video_id, title, summary or ""])),
            raw_metadata={
                "channel_id": snippet.get("channelId"),
                "live_broadcast_content": snippet.get("liveBroadcastContent"),
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


__all__ = ["YouTubeCollector"]
