"""Retention cleanup for local runtime data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlmodel import Session, select

from app.core.timezones import ensure_utc, utc_now
from app.db.models import (
    Cluster,
    ContentItem,
    DeliveryLog,
    EntityTag,
    EventItem,
    RankedItem,
    RawItem,
    Report,
    ReportSection,
)


@dataclass(frozen=True, slots=True)
class CleanupResult:
    """Summary of rows deleted by retention cleanup."""

    cutoff: datetime
    deleted_counts: dict[str, int]


def cleanup_retention(
    session: Session,
    *,
    retain_days: int = 30,
    now: datetime | None = None,
) -> CleanupResult:
    """Delete local rows older than the configured retention window."""
    cutoff = ensure_utc(now or utc_now()) - timedelta(days=retain_days)
    deleted_counts: dict[str, int] = {}

    old_reports = list(session.exec(select(Report).where(Report.report_date < cutoff)).all())
    old_report_ids = [report.id for report in old_reports]
    deleted_counts["report_sections"] = _delete_report_sections(session, old_report_ids)
    deleted_counts["reports"] = _delete_rows(session, old_reports)

    deleted_counts["delivery_logs"] = _delete_selected(
        session, select(DeliveryLog).where(DeliveryLog.created_at < cutoff)
    )
    deleted_counts["ranked_items"] = _delete_selected(
        session, select(RankedItem).where(RankedItem.ranked_at < cutoff)
    )
    deleted_counts["event_items"] = _delete_selected(
        session, select(EventItem).where(EventItem.created_at < cutoff)
    )
    deleted_counts["clusters"] = _delete_selected(
        session, select(Cluster).where(Cluster.created_at < cutoff)
    )
    deleted_counts["entity_tags"] = _delete_selected(
        session, select(EntityTag).where(EntityTag.created_at < cutoff)
    )
    content_items = list(session.exec(select(ContentItem)).all())
    raw_items = list(session.exec(select(RawItem)).all())
    deleted_counts["content_items"] = _delete_rows(
        session,
        [
            item
            for item in content_items
            if _is_expired(item.retention_until, item.fetched_at, cutoff)
        ],
    )
    deleted_counts["raw_items"] = _delete_rows(
        session,
        [item for item in raw_items if _is_expired(item.retention_until, item.fetched_at, cutoff)],
    )

    session.commit()
    return CleanupResult(cutoff=cutoff, deleted_counts=deleted_counts)


def cleanup(
    session: Session,
    *,
    retain_days: int = 30,
    now: datetime | None = None,
) -> CleanupResult:
    """Compatibility wrapper for running cleanup as a job."""
    return cleanup_retention(session, retain_days=retain_days, now=now)


def _delete_selected(session: Session, statement: Any) -> int:
    rows = list(session.exec(statement).all())
    return _delete_rows(session, rows)


def _delete_report_sections(session: Session, report_ids: list[str]) -> int:
    if not report_ids:
        return 0
    rows = [
        section
        for section in session.exec(select(ReportSection)).all()
        if section.report_id in report_ids
    ]
    return _delete_rows(session, rows)


def _delete_rows(session: Session, rows: list[Any]) -> int:
    for row in rows:
        session.delete(row)
    return len(rows)


def _is_expired(
    retention_until: datetime | None,
    fallback_timestamp: datetime,
    cutoff: datetime,
) -> bool:
    if retention_until is not None:
        return ensure_utc(retention_until) < cutoff
    return ensure_utc(fallback_timestamp) < cutoff


__all__ = ["CleanupResult", "cleanup", "cleanup_retention"]
