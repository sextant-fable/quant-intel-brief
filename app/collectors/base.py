"""Shared collector contracts and persistence helpers."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
from dateutil import parser as date_parser  # type: ignore[import-untyped]
from sqlmodel import Session, select

from app.core.timezones import UTC, ensure_utc, utc_now
from app.db.models import ContentItem, RawItem, Source, SourceStatus


class CollectorStatus(StrEnum):
    """Normalized collector outcomes stored in source status records."""

    SUCCESS = "success"
    EMPTY = "empty"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"


@dataclass(frozen=True, slots=True)
class CollectorConfig:
    """Runtime limits common to source collectors."""

    timeout_seconds: float = 30
    retry_attempts: int = 2
    retry_backoff_seconds: float = 1
    max_items: int = 200


@dataclass(slots=True)
class CollectedItem:
    """Metadata-only item emitted by a collector."""

    source_name: str
    source_item_id: str
    url: str
    title: str
    canonical_url: str | None = None
    summary: str | None = None
    excerpt: str | None = None
    author: str | None = None
    publisher: str | None = None
    published_at: datetime | None = None
    fetched_at: datetime = field(default_factory=utc_now)
    language: str | None = None
    raw_payload_hash: str | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FetchResult:
    """Result of a collector HTTP fetch."""

    status: CollectorStatus
    text: str | None = None
    status_code: int | None = None
    message: str | None = None


@dataclass(frozen=True, slots=True)
class JsonFetchResult:
    """Result of a collector JSON fetch."""

    status: CollectorStatus
    data: Any | None = None
    status_code: int | None = None
    message: str | None = None


@dataclass(slots=True)
class CollectorRunResult:
    """Single collector run output."""

    source_name: str
    source_type: str
    display_name: str
    status: CollectorStatus
    items: list[CollectedItem] = field(default_factory=list)
    message: str | None = None
    source_url: str | None = None
    fetched_at: datetime = field(default_factory=utc_now)
    skipped_duplicates: int = 0


@dataclass(frozen=True, slots=True)
class CollectorPersistenceSummary:
    """Summary of metadata persisted from one collector result."""

    source_name: str
    status: CollectorStatus
    raw_items_seen: int
    content_items_seen: int
    skipped_duplicates: int


class SourceCollector:
    """Base class for metadata-only source collectors."""

    source_name: str
    source_type: str
    display_name: str
    config: CollectorConfig

    def __init__(
        self,
        source_name: str,
        source_type: str,
        display_name: str,
        config: CollectorConfig | None = None,
    ) -> None:
        self.source_name = source_name
        self.source_type = source_type
        self.display_name = display_name
        self.config = config or CollectorConfig()

    async def collect(self) -> CollectorRunResult:
        """Collect raw items once implementation begins."""
        raise NotImplementedError

    async def fetch_text(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> FetchResult:
        """Fetch a URL with shared timeout, retry, and rate-limit handling."""
        attempts = max(1, self.config.retry_attempts + 1)
        owns_client = client is None
        active_client = client or httpx.AsyncClient(timeout=self.config.timeout_seconds)

        try:
            for attempt in range(1, attempts + 1):
                try:
                    response = await active_client.get(url, params=params, headers=headers)
                    if response.status_code == 429:
                        return FetchResult(
                            status=CollectorStatus.RATE_LIMITED,
                            status_code=response.status_code,
                            message="Source returned HTTP 429 rate limit.",
                        )
                    if response.status_code >= 500 and attempt < attempts:
                        await self._sleep_before_retry()
                        continue
                    response.raise_for_status()
                    return FetchResult(
                        status=CollectorStatus.SUCCESS,
                        text=response.text,
                        status_code=response.status_code,
                    )
                except httpx.TimeoutException as exc:
                    if attempt < attempts:
                        await self._sleep_before_retry()
                        continue
                    return FetchResult(
                        status=CollectorStatus.TIMEOUT,
                        message=f"Request timed out: {exc}",
                    )
                except httpx.HTTPStatusError as exc:
                    return FetchResult(
                        status=CollectorStatus.FAILED,
                        status_code=exc.response.status_code,
                        message=f"HTTP error {exc.response.status_code}.",
                    )
                except httpx.HTTPError as exc:
                    if attempt < attempts:
                        await self._sleep_before_retry()
                        continue
                    return FetchResult(
                        status=CollectorStatus.FAILED,
                        message=f"HTTP request failed: {exc}",
                    )

            return FetchResult(status=CollectorStatus.FAILED, message="Request failed.")
        finally:
            if owns_client:
                await active_client.aclose()

    async def fetch_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> JsonFetchResult:
        """Fetch and decode JSON with shared HTTP behavior."""
        fetch_result = await self.fetch_text(url, params=params, headers=headers, client=client)
        if fetch_result.status != CollectorStatus.SUCCESS:
            return JsonFetchResult(
                status=fetch_result.status,
                status_code=fetch_result.status_code,
                message=fetch_result.message,
            )
        try:
            return JsonFetchResult(
                status=CollectorStatus.SUCCESS,
                data=json.loads(fetch_result.text or "{}"),
                status_code=fetch_result.status_code,
            )
        except json.JSONDecodeError as exc:
            return JsonFetchResult(
                status=CollectorStatus.FAILED,
                status_code=fetch_result.status_code,
                message=f"JSON decode failed: {exc}",
            )

    async def _sleep_before_retry(self) -> None:
        if self.config.retry_backoff_seconds > 0:
            await asyncio.sleep(self.config.retry_backoff_seconds)


def canonicalize_url_for_storage(url: str) -> str:
    """Apply light URL cleanup before full canonicalization exists."""
    parts = urlsplit(url.strip())
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip("/") or parts.path,
            "",
            parts.query,
        )
    )


def compact_text_for_storage(value: Any | None, max_chars: int = 500) -> str | None:
    """Normalize and bound plain-text source snippets."""
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(value)).strip()
    if not cleaned:
        return None
    if len(cleaned) <= max_chars:
        return cleaned
    return f"{cleaned[: max_chars - 1].rstrip()}..."


def hash_text(value: str) -> str:
    """Hash source identifiers or payload references without storing full payloads."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_datetime_utc(value: str | int | float | None) -> datetime | None:
    """Parse common source timestamps as UTC datetimes."""
    if value is None or value == "":
        return None
    try:
        if isinstance(value, int | float):
            return datetime.fromtimestamp(value, tz=UTC)
        return ensure_utc(date_parser.parse(str(value)))
    except (ValueError, TypeError, OverflowError):
        return None


def persist_collector_result(
    session: Session,
    result: CollectorRunResult,
) -> CollectorPersistenceSummary:
    """Persist a collector result as source, raw item, content item, and status rows."""
    source = _upsert_source(session, result)
    raw_seen = 0
    content_seen = 0
    skipped_duplicates = result.skipped_duplicates
    seen_source_ids: set[str] = set()
    seen_canonical_urls: set[str] = set()

    for item in result.items:
        canonical_url = item.canonical_url or canonicalize_url_for_storage(item.url)
        if item.source_item_id in seen_source_ids or canonical_url in seen_canonical_urls:
            skipped_duplicates += 1
            continue
        seen_source_ids.add(item.source_item_id)
        seen_canonical_urls.add(canonical_url)

        raw_item, raw_created = _upsert_raw_item(session, source, item, canonical_url)
        content_created = _upsert_content_item(session, source, raw_item, item, canonical_url)
        raw_seen += int(raw_created)
        content_seen += int(content_created)

    _upsert_source_status(session, source, result)
    session.commit()

    return CollectorPersistenceSummary(
        source_name=result.source_name,
        status=result.status,
        raw_items_seen=raw_seen,
        content_items_seen=content_seen,
        skipped_duplicates=skipped_duplicates,
    )


def _upsert_source(session: Session, result: CollectorRunResult) -> Source:
    source = session.exec(select(Source).where(Source.name == result.source_name)).one_or_none()
    if source is None:
        source = Source(
            name=result.source_name,
            source_type=result.source_type,
            display_name=result.display_name,
            access_mode="public",
        )
        session.add(source)

    source.source_type = result.source_type
    source.display_name = result.display_name
    source.enabled = True
    session.flush()
    return source


def _upsert_raw_item(
    session: Session,
    source: Source,
    item: CollectedItem,
    canonical_url: str,
) -> tuple[RawItem, bool]:
    raw_item = session.exec(
        select(RawItem).where(
            RawItem.source_id == source.id,
            RawItem.source_item_id == item.source_item_id,
        )
    ).one_or_none()
    created = raw_item is None
    if raw_item is None:
        raw_item = RawItem(
            source_id=source.id,
            source_item_id=item.source_item_id,
            url=item.url,
        )
        session.add(raw_item)

    raw_item.url = item.url
    raw_item.canonical_url = canonical_url
    raw_item.title = item.title
    raw_item.publisher = item.publisher
    raw_item.author = item.author
    raw_item.published_at = item.published_at
    raw_item.fetched_at = item.fetched_at
    raw_item.raw_payload_hash = item.raw_payload_hash
    raw_item.raw_metadata = item.raw_metadata
    session.flush()
    return raw_item, created


def _upsert_content_item(
    session: Session,
    source: Source,
    raw_item: RawItem,
    item: CollectedItem,
    canonical_url: str,
) -> bool:
    content_item = session.exec(
        select(ContentItem).where(
            ContentItem.source_name == source.name,
            ContentItem.source_item_id == item.source_item_id,
        )
    ).one_or_none()

    if content_item is None:
        content_item = session.exec(
            select(ContentItem).where(
                ContentItem.source_name == source.name,
                ContentItem.canonical_url == canonical_url,
            )
        ).first()

    created = content_item is None
    if content_item is None:
        content_item = ContentItem(
            source_id=source.id,
            raw_item_id=raw_item.id,
            source_name=source.name,
            source_item_id=item.source_item_id,
            url=item.url,
            title=item.title,
        )
        session.add(content_item)

    content_item.source_id = source.id
    content_item.raw_item_id = raw_item.id
    content_item.url = item.url
    content_item.canonical_url = canonical_url
    content_item.title = item.title
    content_item.summary = item.summary
    content_item.excerpt = item.excerpt
    content_item.author = item.author
    content_item.publisher = item.publisher
    content_item.published_at = item.published_at
    content_item.fetched_at = item.fetched_at
    content_item.language = item.language
    content_item.raw_payload_hash = item.raw_payload_hash
    session.flush()
    return created


def _upsert_source_status(
    session: Session,
    source: Source,
    result: CollectorRunResult,
) -> SourceStatus:
    status_row = session.exec(
        select(SourceStatus).where(SourceStatus.source_name == result.source_name)
    ).one_or_none()
    if status_row is None:
        status_row = SourceStatus(
            source_id=source.id,
            source_name=result.source_name,
            status=result.status.value,
        )
        session.add(status_row)

    status_row.source_id = source.id
    status_row.status = result.status.value
    status_row.message = result.message
    status_row.last_checked_at = result.fetched_at
    session.flush()
    return status_row


__all__ = [
    "CollectedItem",
    "CollectorConfig",
    "CollectorPersistenceSummary",
    "CollectorRunResult",
    "CollectorStatus",
    "FetchResult",
    "JsonFetchResult",
    "SourceCollector",
    "canonicalize_url_for_storage",
    "compact_text_for_storage",
    "hash_text",
    "parse_datetime_utc",
    "persist_collector_result",
]
