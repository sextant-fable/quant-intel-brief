"""Premium-source reading queue and user-note helpers."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from sqlmodel import Session, select

from app.collectors.base import (
    CollectorConfig,
    CollectorPersistenceSummary,
    persist_collector_result,
)
from app.collectors.rss import RssCollector
from app.core.config import Settings
from app.core.timezones import utc_now
from app.db.models import ContentItem, PremiumSourceNote
from app.dedup.canonicalize import canonicalize_url

PREMIUM_NOTE_CONTEXT_LIMIT = 1000
PREMIUM_SUMMARY_LIMIT = 700
ALLOWED_PREMIUM_NOTE_STATUSES = frozenset({"to_read", "read", "skipped"})


@dataclass(frozen=True, slots=True)
class PremiumRssCollectResult:
    """Summary of a public premium RSS metadata collection run."""

    summaries: tuple[CollectorPersistenceSummary, ...]
    queued_items: int


def upsert_premium_note(
    session: Session,
    *,
    url: str,
    title: str,
    publisher: str | None = None,
    public_summary: str | None = None,
    user_note: str | None = None,
    tickers: str | Iterable[str] | None = None,
    importance: int | str | None = None,
    status: str = "to_read",
    content_item_id: str | None = None,
) -> PremiumSourceNote:
    """Create or update a premium reading queue item without storing article text."""
    canonical_url = canonicalize_url(url)
    note = session.exec(
        select(PremiumSourceNote).where(PremiumSourceNote.canonical_url == canonical_url)
    ).one_or_none()
    if note is None:
        note = PremiumSourceNote(
            url=url.strip(),
            canonical_url=canonical_url,
            title=_required_text(title, fallback=canonical_url),
        )
        session.add(note)

    note.url = url.strip()
    note.canonical_url = canonical_url
    note.title = _required_text(title, fallback=canonical_url)
    note.publisher = _clean_text(publisher)
    note.public_summary = _bounded_text(public_summary, PREMIUM_SUMMARY_LIMIT)
    note.user_note = _bounded_text(user_note, PREMIUM_NOTE_CONTEXT_LIMIT)
    note.tickers = _parse_tickers(tickers)
    note.importance = _importance_value(importance)
    note.status = status if status in ALLOWED_PREMIUM_NOTE_STATUSES else "to_read"
    note.content_item_id = content_item_id
    note.storage_policy = "user_notes_only"
    note.updated_at = utc_now()
    session.flush()
    return note


def update_premium_note(
    session: Session,
    note_id: str,
    *,
    user_note: str | None,
    tickers: str | Iterable[str] | None,
    importance: int | str | None,
    status: str,
) -> PremiumSourceNote | None:
    """Update user-owned note fields for an existing premium queue item."""
    note = session.get(PremiumSourceNote, note_id)
    if note is None:
        return None
    note.user_note = _bounded_text(user_note, PREMIUM_NOTE_CONTEXT_LIMIT)
    note.tickers = _parse_tickers(tickers)
    note.importance = _importance_value(importance)
    note.status = status if status in ALLOWED_PREMIUM_NOTE_STATUSES else note.status
    note.updated_at = utc_now()
    session.flush()
    return note


async def collect_premium_rss_feeds(
    session: Session,
    *,
    feed_urls: str,
    settings: Settings,
) -> PremiumRssCollectResult:
    """Collect public RSS metadata into the reading queue."""
    urls = _split_urls(feed_urls)
    config = CollectorConfig(
        timeout_seconds=settings.collector_timeout_seconds,
        retry_attempts=settings.http_retry_attempts,
        retry_backoff_seconds=settings.http_retry_backoff_seconds,
        max_items=settings.max_items_per_source,
    )
    summaries: list[CollectorPersistenceSummary] = []
    queued_items = 0

    for index, feed_url in enumerate(urls, start=1):
        collector = RssCollector(
            feed_url=feed_url,
            source_name=f"premium_rss_{index}",
            display_name=f"Premium Public RSS {index}",
            config=config,
        )
        result = await collector.collect()
        summaries.append(persist_collector_result(session, result))
        for item in result.items:
            content_item = _content_item_for_source_item(
                session,
                item.source_name,
                item.source_item_id,
            )
            upsert_premium_note(
                session,
                url=item.url,
                title=item.title,
                publisher=item.publisher,
                public_summary=item.summary or item.excerpt,
                content_item_id=content_item.id if content_item else None,
            )
            queued_items += 1

    session.commit()
    return PremiumRssCollectResult(summaries=tuple(summaries), queued_items=queued_items)


def premium_notes_for_llm(notes: Iterable[PremiumSourceNote]) -> list[dict[str, object]]:
    """Build source-grounded context from user notes and public metadata only."""
    contexts: list[dict[str, object]] = []
    for note in notes:
        contexts.append(
            {
                "note_id": note.id,
                "url": note.url,
                "title": note.title,
                "publisher": note.publisher,
                "public_summary": note.public_summary,
                "user_note": note.user_note,
                "tickers": note.tickers,
                "importance": note.importance,
                "status": note.status,
            }
        )
    return contexts


def _content_item_for_source_item(
    session: Session,
    source_name: str,
    source_item_id: str,
) -> ContentItem | None:
    return session.exec(
        select(ContentItem).where(
            ContentItem.source_name == source_name,
            ContentItem.source_item_id == source_item_id,
        )
    ).one_or_none()


def _required_text(value: str | None, *, fallback: str) -> str:
    cleaned = _clean_text(value)
    return cleaned or fallback


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned or None


def _bounded_text(value: str | None, max_chars: int) -> str | None:
    cleaned = _clean_text(value)
    if cleaned is None or len(cleaned) <= max_chars:
        return cleaned
    return f"{cleaned[: max_chars - 3].rstrip()}..."


def _parse_tickers(value: str | Iterable[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = re.split(r"[,\s]+", value)
    else:
        parts = [str(part) for part in value]
    return sorted({part.strip().upper().lstrip("$") for part in parts if part.strip()})


def _importance_value(value: int | str | None) -> int:
    try:
        parsed = int(value) if value is not None else 3
    except (TypeError, ValueError):
        parsed = 3
    return min(max(parsed, 1), 5)


def _split_urls(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(part.strip() for part in re.split(r"[\n,]+", value) if part.strip())


__all__ = [
    "ALLOWED_PREMIUM_NOTE_STATUSES",
    "PremiumRssCollectResult",
    "collect_premium_rss_feeds",
    "premium_notes_for_llm",
    "update_premium_note",
    "upsert_premium_note",
]
