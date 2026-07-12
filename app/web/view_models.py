"""Dashboard view-model formatting helpers."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from app.core.logging import redact_text
from app.core.timezones import next_regular_market_open, utc_now
from app.db.models import ContentItem, Report, ReportEventRecord, ReportSection, SourceStatus
from app.web.filters import DashboardFilters


def build_dashboard_view(
    *,
    items: Iterable[ContentItem],
    reports: Iterable[Report],
    statuses: Iterable[SourceStatus],
    report_events: Iterable[ReportEventRecord] = (),
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build the local dashboard overview payload."""
    item_rows = _sort_items(items)
    report_rows = _sort_reports(reports)
    status_rows = list(statuses)
    event_views = [_report_event_view(event) for event in _sort_report_events(report_events)]
    item_views = [_content_item_view(item) for item in item_rows]
    report_views = [_report_view(report) for report in report_rows]
    status_views = [_source_status_view(status) for status in status_rows]
    failure_views = [status for status in status_views if status["is_failure"]]
    active_now = now or utc_now()
    return {
        "generated_at": active_now.isoformat(),
        "data_updated_at": _latest_data_timestamp(item_rows, report_rows, status_rows),
        "next_market_open": next_regular_market_open(active_now).isoformat(),
        "counts": {
            "item_count": len(item_views),
            "report_count": len(report_views),
            "source_count": len(status_views),
            "source_failures": sum(1 for status in status_views if status["is_failure"]),
        },
        "recent_items": item_views[:8],
        "latest_reports": report_views[:5],
        "source_statuses": status_views,
        "source_failures": failure_views,
        "brief": {
            "has_events": bool(event_views),
            "report_id": event_views[0]["report_id"] if event_views else None,
            "top_events": event_views[:10],
            "daily_focus": _daily_focus(event_views),
            "market_sections": _market_section_views(event_views),
        },
    }


def build_feed_view(
    *,
    items: Iterable[ContentItem],
    filters: DashboardFilters,
    report_events: Iterable[ReportEventRecord] = (),
) -> dict[str, Any]:
    """Build feed page payload."""
    insights = _insights_by_source_id(report_events)
    item_views = [
        _content_item_view(item, insight=insights.get(item.id)) for item in _sort_items(items)
    ]
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
    report_events: Iterable[ReportEventRecord] = (),
) -> dict[str, Any]:
    """Build report detail payload."""
    event_views = [_report_event_view(event) for event in _sort_report_events(report_events)]
    return {
        "report": _report_view(report),
        "sections": [_report_section_view(section) for section in _sort_sections(sections)],
        "top_events": event_views[:10],
        "market_sections": _market_section_views(event_views),
        "has_structured_events": bool(event_views),
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


def _content_item_view(
    item: ContentItem,
    *,
    insight: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
        "insight": insight,
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


def _report_event_view(event: ReportEventRecord) -> dict[str, Any]:
    credibility_zh = {"high": "高", "medium": "中", "low": "低"}
    return {
        "id": event.id,
        "report_id": event.report_id,
        "position": event.position,
        "section_key": event.section_key,
        "score": event.score,
        "headline": event.headline,
        "headline_zh": event.headline_zh,
        "factual_summary": event.factual_summary,
        "factual_summary_zh": event.factual_summary_zh,
        "market_relevance": event.market_relevance,
        "market_relevance_zh": event.market_relevance_zh,
        "uncertainty": event.uncertainty,
        "what_to_watch": event.what_to_watch,
        "what_to_watch_zh": event.what_to_watch_zh,
        "source_credibility": event.source_credibility,
        "source_credibility_zh": credibility_zh.get(event.source_credibility, "中"),
        "source_credibility_reason": event.source_credibility_reason,
        "source_ids": event.source_ids,
        "source_urls": event.source_urls,
        "source_links": [
            {
                "id": source_id,
                "url": event.source_urls[index],
            }
            for index, source_id in enumerate(event.source_ids)
            if index < len(event.source_urls)
        ],
        "tickers": event.tickers,
        "assets": event.assets,
        "quant_topics": event.quant_topics,
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


def _sort_report_events(events: Iterable[ReportEventRecord]) -> list[ReportEventRecord]:
    return sorted(events, key=lambda event: (event.position, -event.score, event.headline))


def _insights_by_source_id(
    events: Iterable[ReportEventRecord],
) -> dict[str, dict[str, Any]]:
    insights: dict[str, dict[str, Any]] = {}
    for event in _sort_report_events(events):
        view = _report_event_view(event)
        for source_id in event.source_ids:
            insights.setdefault(source_id, view)
    return insights


def _daily_focus(events: list[dict[str, Any]]) -> dict[str, str]:
    if not events:
        return {
            "en": "Generate a fresh brief to see today's market focus.",
            "zh": "生成最新简报后，这里会显示今日市场主线。",
        }
    leaders = events[:3]
    return {
        "en": "Today's brief is led by " + "; ".join(event["headline"] for event in leaders) + ".",
        "zh": "今日重点集中在：" + "、".join(event["headline_zh"] for event in leaders) + "。",
    }


def _market_section_views(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    definitions = (
        ("macro_fed", "Macro & Fed", "宏观与美联储"),
        ("etf_options", "ETFs & Options", "ETF 与期权"),
        ("sec_companies", "SEC & Companies", "SEC 与公司"),
        ("quant_research", "Quant Research", "量化研究"),
        ("community_heat", "Community Heat", "社区热度"),
    )
    return [
        {
            "key": key,
            "title": title,
            "title_zh": title_zh,
            "events": [event for event in events if event["section_key"] == key],
            "count": sum(1 for event in events if event["section_key"] == key),
        }
        for key, title, title_zh in definitions
    ]


def _latest_data_timestamp(
    items: list[ContentItem],
    reports: list[Report],
    statuses: list[SourceStatus],
) -> str:
    values = [item.fetched_at for item in items]
    values.extend(report.created_at for report in reports)
    values.extend(status.last_checked_at for status in statuses)
    return _format_datetime(max(values)) if values else ""


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
