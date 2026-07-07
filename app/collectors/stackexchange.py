"""Stack Exchange API metadata collector."""

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


class StackExchangeCollector(SourceCollector):
    """Collect Stack Exchange question metadata."""

    endpoint = "https://api.stackexchange.com/2.3/search/advanced"

    def __init__(
        self,
        enabled: bool = False,
        api_key: str | None = None,
        query: str = "quant finance",
        site: str = "quant",
        config: CollectorConfig | None = None,
        endpoint: str | None = None,
    ) -> None:
        super().__init__(
            source_name="stackexchange",
            source_type="community_api",
            display_name="Stack Exchange",
            config=config,
        )
        self.enabled = enabled
        self.api_key = api_key
        self.query = query
        self.site = site
        self.endpoint = endpoint or self.endpoint

    async def collect(self, client: httpx.AsyncClient | None = None) -> CollectorRunResult:
        fetched_at = utc_now()
        if not self.enabled:
            return self._result(
                CollectorStatus.FAILED,
                "Stack Exchange collection is disabled.",
                fetched_at,
            )

        params: dict[str, Any] = {
            "order": "desc",
            "sort": "activity",
            "q": self.query,
            "site": self.site,
            "pagesize": min(self.config.max_items, 100),
        }
        if self.api_key:
            params["key"] = self.api_key

        fetch = await self.fetch_json(self.endpoint, params=params, client=client)
        if fetch.status != CollectorStatus.SUCCESS:
            return self._result(
                fetch.status,
                fetch.message or "Stack Exchange request failed.",
                fetched_at,
            )

        data = fetch.data if isinstance(fetch.data, dict) else {}
        if "error_id" in data:
            return self._result(CollectorStatus.FAILED, str(data.get("error_message")), fetched_at)

        items_value = data.get("items")
        questions = items_value if isinstance(items_value, list) else []
        items = [
            item
            for question in questions
            if (item := self._question_to_item(question, fetched_at))
        ]
        status = CollectorStatus.SUCCESS if items else CollectorStatus.EMPTY
        return self._result(
            status,
            f"Parsed {len(items)} Stack Exchange question(s).",
            fetched_at,
            items,
        )

    def _question_to_item(self, question: Any, fetched_at: datetime) -> CollectedItem | None:
        if not isinstance(question, dict):
            return None
        url = compact_text_for_storage(question.get("link"), max_chars=2000)
        title = compact_text_for_storage(question.get("title"))
        question_id = compact_text_for_storage(question.get("question_id"))
        if not url or not title or not question_id:
            return None

        owner_value = question.get("owner")
        owner: dict[str, Any] = owner_value if isinstance(owner_value, dict) else {}
        tags_value = question.get("tags")
        tags = [str(tag) for tag in tags_value] if isinstance(tags_value, list) else []
        summary = compact_text_for_storage(", ".join(tags))
        return CollectedItem(
            source_name=self.source_name,
            source_item_id=question_id,
            url=url,
            canonical_url=canonicalize_url_for_storage(url),
            title=title,
            summary=summary,
            excerpt=summary,
            author=compact_text_for_storage(owner.get("display_name")),
            publisher=f"Stack Exchange:{self.site}",
            published_at=parse_datetime_utc(question.get("creation_date")),
            fetched_at=fetched_at,
            raw_payload_hash=hash_text("|".join([question_id, title, summary or ""])),
            raw_metadata={
                "tags": tags,
                "score": question.get("score"),
                "answer_count": question.get("answer_count"),
                "is_answered": question.get("is_answered"),
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


__all__ = ["StackExchangeCollector"]
