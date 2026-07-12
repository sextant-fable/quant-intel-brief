"""Daily report assembly from ranked, source-grounded summaries."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.core.timezones import utc_now
from app.llm.schemas import SummaryResult
from app.reports.sections import (
    SECTION_DEFINITIONS,
    SECTION_KEYS,
    section_key_from_signals,
)


class ReportEvent(BaseModel):
    """One cited event rendered inside a daily report section."""

    event_id: str
    ranked_item_id: str | None = None
    score: float = 0.0
    headline: str
    headline_zh: str
    factual_summary: str
    factual_summary_zh: str
    market_relevance: str
    market_relevance_zh: str
    uncertainty: str
    what_to_watch: list[str]
    what_to_watch_zh: list[str]
    source_credibility: str
    source_credibility_reason: str
    source_ids: list[str] = Field(min_length=1)
    source_urls: list[str] = Field(min_length=1)
    tickers: list[str] = Field(default_factory=list)
    assets: list[str] = Field(default_factory=list)
    quant_topics: list[str] = Field(default_factory=list)


class ReportSectionData(BaseModel):
    """A deterministic report section."""

    key: str
    title: str
    title_zh: str
    position: int
    events: list[ReportEvent] = Field(default_factory=list)


class DailyReport(BaseModel):
    """Full local daily report payload before persistence or delivery."""

    report_date: date
    title: str
    source_coverage_note: str
    generated_at: datetime = Field(default_factory=utc_now)
    top_events: list[ReportEvent] = Field(default_factory=list)
    sections: list[ReportSectionData]


def generate_daily_report(
    summary_results: Iterable[SummaryResult],
    *,
    report_date: date | None = None,
    title: str = "Quant Intel Brief",
    source_coverage_note: str | None = None,
) -> DailyReport:
    """Generate a deterministic daily report payload from summarized ranked events."""
    results = list(summary_results)
    section_events: dict[str, list[ReportEvent]] = {
        key: [] for key, _, _ in SECTION_DEFINITIONS
    }
    skipped = 0

    for result in results:
        event = _event_from_result(result)
        if event is None:
            skipped += 1
            continue
        section_key = result.section_key if result.section_key in SECTION_KEYS else None
        section_events[section_key or _section_key_for_event(event)].append(event)

    for events in section_events.values():
        events.sort(key=lambda event: (-event.score, event.headline.lower()))

    top_events = sorted(
        [event for events in section_events.values() for event in events],
        key=lambda event: (-event.score, event.headline.lower()),
    )[:10]
    sections = [
        ReportSectionData(
            key=key,
            title=section_title,
            title_zh=section_title_zh,
            position=index,
            events=section_events[key],
        )
        for index, (key, section_title, section_title_zh) in enumerate(SECTION_DEFINITIONS)
    ]
    included = sum(len(section.events) for section in sections)

    return DailyReport(
        report_date=report_date or utc_now().date(),
        title=title,
        source_coverage_note=source_coverage_note
        or _coverage_note(included, skipped, len(results)),
        top_events=top_events,
        sections=sections,
    )


def _event_from_result(result: SummaryResult) -> ReportEvent | None:
    summary = result.summary
    if not result.success or summary is None:
        return None
    if summary.insufficient_evidence or not summary.source_ids or not summary.source_urls:
        return None

    return ReportEvent(
        event_id=summary.event_id,
        ranked_item_id=result.ranked_item_id,
        score=result.ranked_score or 0.0,
        headline=summary.headline,
        headline_zh=summary.headline_zh,
        factual_summary=summary.factual_summary,
        factual_summary_zh=summary.factual_summary_zh,
        market_relevance=summary.market_relevance,
        market_relevance_zh=summary.market_relevance_zh,
        uncertainty=summary.uncertainty,
        what_to_watch=summary.what_to_watch,
        what_to_watch_zh=summary.what_to_watch_zh,
        source_credibility=summary.source_credibility,
        source_credibility_reason=summary.source_credibility_reason,
        source_ids=summary.source_ids,
        source_urls=summary.source_urls,
        tickers=summary.tickers,
        assets=summary.assets,
        quant_topics=summary.quant_topics,
    )


def _section_key_for_event(event: ReportEvent) -> str:
    return section_key_from_signals(
        title=event.headline,
        assets=event.assets,
        quant_topics=event.quant_topics,
        extra_text=" ".join([event.factual_summary, event.market_relevance]),
    )


def _coverage_note(included: int, skipped: int, total: int) -> str:
    if total == 0:
        return "No ranked summaries were available for this report."
    return (
        f"{included} summarized events included; {skipped} result(s) skipped because "
        "they failed validation or lacked source citations."
    )


__all__ = [
    "DailyReport",
    "ReportEvent",
    "ReportSectionData",
    "SECTION_DEFINITIONS",
    "generate_daily_report",
]
