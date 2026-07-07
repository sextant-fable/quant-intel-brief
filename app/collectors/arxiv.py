"""arXiv API metadata collector."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import feedparser  # type: ignore[import-untyped]
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


class ArxivCollector(SourceCollector):
    """Collect paper metadata from the arXiv API."""

    endpoint = "https://export.arxiv.org/api/query"

    def __init__(
        self,
        search_query: str = "cat:q-fin*",
        config: CollectorConfig | None = None,
        endpoint: str | None = None,
    ) -> None:
        super().__init__(
            source_name="arxiv",
            source_type="research_api",
            display_name="arXiv",
            config=config,
        )
        self.search_query = search_query
        self.endpoint = endpoint or self.endpoint

    async def collect(self, client: httpx.AsyncClient | None = None) -> CollectorRunResult:
        fetched_at = utc_now()
        fetch = await self.fetch_text(
            self.endpoint,
            params={
                "search_query": self.search_query,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
                "max_results": self.config.max_items,
            },
            client=client,
        )
        if fetch.status != CollectorStatus.SUCCESS:
            return self._result(fetch.status, fetch.message or "arXiv request failed.", fetched_at)

        return self.parse_feed(fetch.text or "", fetched_at=fetched_at)

    def parse_feed(self, feed_text: str, fetched_at: datetime | None = None) -> CollectorRunResult:
        checked_at = fetched_at or utc_now()
        parsed = feedparser.parse(feed_text)
        entries = list(parsed.entries)[: self.config.max_items]
        if getattr(parsed, "bozo", False) and not entries:
            return self._result(
                CollectorStatus.FAILED,
                "arXiv feed could not be parsed.",
                checked_at,
            )
        if not entries:
            return self._result(
                CollectorStatus.EMPTY,
                "arXiv feed contained no entries.",
                checked_at,
            )

        items = [item for entry in entries if (item := self._entry_to_item(entry, checked_at))]
        status = CollectorStatus.SUCCESS if items else CollectorStatus.EMPTY
        return self._result(status, f"Parsed {len(items)} arXiv paper(s).", checked_at, items)

    def _entry_to_item(self, entry: Any, fetched_at: datetime) -> CollectedItem | None:
        arxiv_id = compact_text_for_storage(entry.get("id")) if hasattr(entry, "get") else None
        title = compact_text_for_storage(entry.get("title")) if hasattr(entry, "get") else None
        if not arxiv_id or not title:
            return None

        url = arxiv_id
        canonical_url = canonicalize_url_for_storage(url)
        summary = compact_text_for_storage(entry.get("summary")) if hasattr(entry, "get") else None
        authors = _authors(entry)
        categories = _tags(entry)
        published = entry.get("published") if hasattr(entry, "get") else None
        updated = (
            entry.get("updated")
            if hasattr(entry, "get") and "updated" in entry
            else None
        )
        return CollectedItem(
            source_name=self.source_name,
            source_item_id=arxiv_id.rsplit("/", maxsplit=1)[-1],
            url=url,
            canonical_url=canonical_url,
            title=title,
            summary=summary,
            excerpt=summary,
            author=", ".join(authors) if authors else None,
            publisher="arXiv",
            published_at=parse_datetime_utc(published),
            fetched_at=fetched_at,
            raw_payload_hash=hash_text("|".join([arxiv_id, title, summary or ""])),
            raw_metadata={
                "authors": authors,
                "categories": categories,
                "updated": updated,
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


def _authors(entry: Any) -> list[str]:
    values = entry.get("authors", []) if hasattr(entry, "get") else []
    authors: list[str] = []
    for author in values:
        name = author.get("name") if hasattr(author, "get") else None
        if name:
            authors.append(str(name))
    return authors


def _tags(entry: Any) -> list[str]:
    values = entry.get("tags", []) if hasattr(entry, "get") else []
    tags: list[str] = []
    for tag in values:
        term = tag.get("term") if hasattr(tag, "get") else None
        if term:
            tags.append(str(term))
    return tags


__all__ = ["ArxivCollector"]
