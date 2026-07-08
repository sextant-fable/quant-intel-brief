"""Dashboard view-model formatting helpers."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from app.core.logging import redact_text
from app.core.timezones import utc_now
from app.db.models import ContentItem, Report, ReportSection, SourceStatus
from app.web.filters import DashboardFilters


def build_dashboard_view(
    *,
    items: Iterable[ContentItem],
    reports: Iterable[Report],
    statuses: Iterable[SourceStatus],
) -> dict[str, Any]:
    """Build the local dashboard overview payload."""
    item_views = [_content_item_view(item) for item in _sort_items(items)]
    report_views = [_report_view(report) for report in _sort_reports(reports)]
    status_views = [_source_status_view(status) for status in statuses]
    return {
        "generated_at": utc_now().isoformat(),
        "counts": {
            "item_count": len(item_views),
            "report_count": len(report_views),
            "source_count": len(status_views),
            "source_failures": sum(1 for status in status_views if status["is_failure"]),
        },
        "recent_items": item_views[:8],
        "latest_reports": report_views[:5],
        "source_statuses": status_views,
    }


def build_feed_view(
    *,
    items: Iterable[ContentItem],
    filters: DashboardFilters,
) -> dict[str, Any]:
    """Build feed page payload."""
    item_views = [_content_item_view(item) for item in _sort_items(items)]
    return {
        "filters": filters.model_dump(),
        "has_active_filters": filters.has_active_filters,
        "feed_items": item_views,
        "item_count": len(item_views),
    }


def build_reports_view(reports: Iterable[Report]) -> dict[str, Any]:
    """Build report archive payload."""
    report_views = [_report_view(report) for report in _sort_reports(reports)]
    return {"reports": report_views, "report_count": len(report_views)}


def build_report_detail_view(
    *,
    report: Report,
    sections: Iterable[ReportSection],
) -> dict[str, Any]:
    """Build report detail payload."""
    return {
        "report": _report_view(report),
        "sections": [_report_section_view(section) for section in _sort_sections(sections)],
    }


def build_source_status_view(statuses: Iterable[SourceStatus]) -> dict[str, Any]:
    """Build source status page payload with redacted messages."""
    status_views = [_source_status_view(status) for status in statuses]
    return {
        "statuses": status_views,
        "source_count": len(status_views),
        "failure_count": sum(1 for status in status_views if status["is_failure"]),
    }


def source_status_json(statuses: Iterable[SourceStatus]) -> list[dict[str, Any]]:
    """Return redacted source status dictionaries for JSON system routes."""
    return [_source_status_view(status) for status in statuses]


def _content_item_view(item: ContentItem) -> dict[str, Any]:
    item_time = item.published_at or item.fetched_at
    return {
        "id": item.id,
        "title": item.title,
        "url": item.url,
        "source_name": item.source_name,
        "publisher": item.publisher,
        "published_at": _format_datetime(item_time),
        "tickers": item.tickers,
        "assets": item.assets,
        "quant_topics": item.quant_topics,
        "summary": item.summary or item.excerpt,
    }


def _report_view(report: Report) -> dict[str, Any]:
    return {
        "id": report.id,
        "title": report.title,
        "status": report.status,
        "report_date": _format_datetime(report.report_date),
        "html_path": report.html_path,
        "source_coverage_note": report.source_coverage_note,
        "created_at": _format_datetime(report.created_at),
    }


def _report_section_view(section: ReportSection) -> dict[str, Any]:
    return {
        "id": section.id,
        "key": section.section_key,
        "title": section.title,
        "position": section.position,
        "content": section.content,
        "source_refs": section.source_refs,
    }


def _source_status_view(status: SourceStatus) -> dict[str, Any]:
    normalized_status = status.status.lower()
    return {
        "source_name": status.source_name,
        "status": status.status,
        "message": redact_text(status.message or ""),
        "last_checked_at": _format_datetime(status.last_checked_at),
        "is_failure": normalized_status not in {"ok", "success", "healthy"},
    }


def _sort_items(items: Iterable[ContentItem]) -> list[ContentItem]:
    return sorted(items, key=lambda item: item.published_at or item.fetched_at, reverse=True)


def _sort_reports(reports: Iterable[Report]) -> list[Report]:
    return sorted(reports, key=lambda report: report.report_date, reverse=True)


def _sort_sections(sections: Iterable[ReportSection]) -> list[ReportSection]:
    return sorted(sections, key=lambda section: (section.position, section.title))


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.isoformat()


__all__ = [
    "build_dashboard_view",
    "build_feed_view",
    "build_report_detail_view",
    "build_reports_view",
    "build_source_status_view",
    "source_status_json",
]
