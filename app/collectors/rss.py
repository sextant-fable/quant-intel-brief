"""RSS feed collector."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any

import feedparser  # type: ignore[import-untyped]
import httpx
from bs4 import BeautifulSoup  # type: ignore[import-untyped]
from dateutil import parser as date_parser  # type: ignore[import-untyped]

from app.collectors.base import (
    CollectedItem,
    CollectorConfig,
    CollectorRunResult,
    CollectorStatus,
    SourceCollector,
    canonicalize_url_for_storage,
)
from app.core.timezones import ensure_utc, utc_now

MAX_EXCERPT_CHARS = 500


class RssCollector(SourceCollector):
    """Collect metadata from a public RSS or Atom feed."""

    def __init__(
        self,
        feed_url: str,
        source_name: str = "rss",
        display_name: str = "RSS Feed",
        config: CollectorConfig | None = None,
    ) -> None:
        super().__init__(
            source_name=source_name,
            source_type="rss",
            display_name=display_name,
            config=config,
        )
        self.feed_url = feed_url

    async def collect(self, client: httpx.AsyncClient | None = None) -> CollectorRunResult:
        """Fetch and parse the configured RSS feed."""
        fetched_at = utc_now()
        fetch_result = await self.fetch_text(self.feed_url, client=client)
        if fetch_result.status != CollectorStatus.SUCCESS:
            return CollectorRunResult(
                source_name=self.source_name,
                source_type=self.source_type,
                display_name=self.display_name,
                status=fetch_result.status,
                message=fetch_result.message,
                source_url=self.feed_url,
                fetched_at=fetched_at,
            )

        return self.parse_feed(fetch_result.text or "", fetched_at=fetched_at)

    def parse_feed(self, feed_text: str, fetched_at: datetime | None = None) -> CollectorRunResult:
        """Parse RSS/Atom text into normalized metadata items."""
        checked_at = fetched_at or utc_now()
        parsed = feedparser.parse(feed_text)
        entries = list(parsed.entries)[: self.config.max_items]

        if getattr(parsed, "bozo", False) and not entries:
            return self._result(
                status=CollectorStatus.FAILED,
                message="Feed could not be parsed.",
                fetched_at=checked_at,
            )

        if not entries:
            return self._result(
                status=CollectorStatus.EMPTY,
                message="Feed contained no entries.",
                fetched_at=checked_at,
            )

        feed_metadata = parsed.feed if hasattr(parsed, "feed") else {}
        feed_title = _clean_text(_get_value(feed_metadata, "title")) or self.display_name
        feed_language = _clean_text(_get_value(feed_metadata, "language"))
        items: list[CollectedItem] = []
        seen_source_ids: set[str] = set()
        seen_canonical_urls: set[str] = set()
        skipped_duplicates = 0

        for entry in entries:
            item = self._entry_to_item(
                entry=entry,
                feed_title=feed_title,
                feed_language=feed_language,
                fetched_at=checked_at,
            )
            if item is None:
                continue
            canonical_url = item.canonical_url or canonicalize_url_for_storage(item.url)
            if item.source_item_id in seen_source_ids or canonical_url in seen_canonical_urls:
                skipped_duplicates += 1
                continue
            seen_source_ids.add(item.source_item_id)
            seen_canonical_urls.add(canonical_url)
            items.append(item)

        if not items:
            return self._result(
                status=CollectorStatus.EMPTY,
                message="Feed entries did not include usable links.",
                fetched_at=checked_at,
                skipped_duplicates=skipped_duplicates,
            )

        return self._result(
            status=CollectorStatus.SUCCESS,
            message=f"Parsed {len(items)} feed item(s).",
            fetched_at=checked_at,
            items=items,
            skipped_duplicates=skipped_duplicates,
        )

    def _entry_to_item(
        self,
        entry: Any,
        feed_title: str,
        feed_language: str | None,
        fetched_at: datetime,
    ) -> CollectedItem | None:
        link = _clean_text(_get_value(entry, "link"))
        if not link:
            return None

        canonical_url = canonicalize_url_for_storage(link)
        source_item_id = _clean_text(_get_value(entry, "id")) or _clean_text(
            _get_value(entry, "guid")
        )
        if not source_item_id:
            source_item_id = _hash_text(canonical_url)

        title = _clean_text(_get_value(entry, "title")) or canonical_url
        summary = _compact_html(_get_value(entry, "summary") or _get_value(entry, "description"))
        published_at = _parse_datetime(
            _get_value(entry, "published") or _get_value(entry, "updated")
        )
        tags = _extract_tags(entry)
        raw_payload_hash = _hash_text(
            "|".join([source_item_id, canonical_url, title, summary or ""])
        )

        return CollectedItem(
            source_name=self.source_name,
            source_item_id=source_item_id,
            url=link,
            canonical_url=canonical_url,
            title=title,
            summary=summary,
            excerpt=summary,
            author=_clean_text(_get_value(entry, "author")),
            publisher=feed_title,
            published_at=published_at,
            fetched_at=fetched_at,
            language=feed_language,
            raw_payload_hash=raw_payload_hash,
            raw_metadata={
                "feed_url": self.feed_url,
                "feed_title": feed_title,
                "entry_tags": tags,
                "published": _clean_text(_get_value(entry, "published")),
                "updated": _clean_text(_get_value(entry, "updated")),
            },
        )

    def _result(
        self,
        status: CollectorStatus,
        message: str,
        fetched_at: datetime,
        items: list[CollectedItem] | None = None,
        skipped_duplicates: int = 0,
    ) -> CollectorRunResult:
        return CollectorRunResult(
            source_name=self.source_name,
            source_type=self.source_type,
            display_name=self.display_name,
            status=status,
            items=items or [],
            message=message,
            source_url=self.feed_url,
            fetched_at=fetched_at,
            skipped_duplicates=skipped_duplicates,
        )


def _get_value(source: Any, key: str) -> str | None:
    if not hasattr(source, "get"):
        return None
    if hasattr(source, "__contains__") and key not in source:
        return None
    value = source.get(key)
    if value is None:
        return None
    return str(value)


def _clean_text(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned or None


def _compact_html(value: str | None, max_chars: int = MAX_EXCERPT_CHARS) -> str | None:
    if not value:
        return None
    text = BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
    cleaned = _clean_text(text)
    if not cleaned:
        return None
    if len(cleaned) <= max_chars:
        return cleaned
    return f"{cleaned[: max_chars - 1].rstrip()}..."


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return ensure_utc(date_parser.parse(value))
    except (ValueError, TypeError, OverflowError):
        return None


def _extract_tags(entry: Any) -> list[str]:
    tags = entry.get("tags", []) if hasattr(entry, "get") else []
    values: list[str] = []
    for tag in tags:
        term = tag.get("term") if hasattr(tag, "get") else None
        if term:
            values.append(str(term))
    return values


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


__all__ = ["RssCollector"]
