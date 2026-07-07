"""Daily report assembly from ranked, source-grounded summaries."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.core.timezones import utc_now
from app.llm.schemas import SummaryResult

SECTION_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("market_overview", "Market Overview"),
    ("macro_fed", "Macro/Fed"),
    ("etf_options", "ETFs/Options"),
    ("sec_filings", "SEC Filings"),
    ("research", "Research"),
    ("github_community", "GitHub/Community"),
    ("watchlist", "Watchlist"),
)

RESEARCH_TOPICS = frozenset(
    {"arxiv", "backtesting", "factor", "microstructure", "risk_model", "volatility"}
)


class ReportEvent(BaseModel):
    """One cited event rendered inside a daily report section."""

    event_id: str
    ranked_item_id: str | None = None
    score: float = 0.0
    headline: str
    factual_summary: str
    market_relevance: str
    uncertainty: str
    source_ids: list[str] = Field(min_length=1)
    source_urls: list[str] = Field(min_length=1)
    tickers: list[str] = Field(default_factory=list)
    assets: list[str] = Field(default_factory=list)
    quant_topics: list[str] = Field(default_factory=list)


class ReportSectionData(BaseModel):
    """A deterministic report section."""

    key: str
    title: str
    position: int
    events: list[ReportEvent] = Field(default_factory=list)


class DailyReport(BaseModel):
    """Full local daily report payload before persistence or delivery."""

    report_date: date
    title: str
    source_coverage_note: str
    generated_at: datetime = Field(default_factory=utc_now)
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
    section_events: dict[str, list[ReportEvent]] = {key: [] for key, _ in SECTION_DEFINITIONS}
    skipped = 0

    for result in results:
        event = _event_from_result(result)
        if event is None:
            skipped += 1
            continue
        section_events[_section_key_for_event(event)].append(event)

    for events in section_events.values():
        events.sort(key=lambda event: (-event.score, event.headline.lower()))

    sections = [
        ReportSectionData(key=key, title=section_title, position=index, events=section_events[key])
        for index, (key, section_title) in enumerate(SECTION_DEFINITIONS)
    ]
    included = sum(len(section.events) for section in sections)

    return DailyReport(
        report_date=report_date or utc_now().date(),
        title=title,
        source_coverage_note=source_coverage_note
        or _coverage_note(included, skipped, len(results)),
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
        factual_summary=summary.factual_summary,
        market_relevance=summary.market_relevance,
        uncertainty=summary.uncertainty,
        source_ids=summary.source_ids,
        source_urls=summary.source_urls,
        tickers=summary.tickers,
        assets=summary.assets,
        quant_topics=summary.quant_topics,
    )


def _section_key_for_event(event: ReportEvent) -> str:
    text = _event_text(event)
    assets = {asset.lower() for asset in event.assets}
    topics = {topic.lower() for topic in event.quant_topics}

    if "macro" in assets or any(term in text for term in ("fed", "fomc", "fred", "cpi")):
        return "macro_fed"
    if assets & {"etf", "options"} or any(term in text for term in ("etf", "option")):
        return "etf_options"
    if any(term in text for term in ("sec", "filing", "10-k", "10-q", "8-k")):
        return "sec_filings"
    if topics & RESEARCH_TOPICS or any(term in text for term in ("research", "paper", "arxiv")):
        return "research"
    if any(term in text for term in ("github", "community", "reddit", "youtube", "open source")):
        return "github_community"
    if event.tickers:
        return "watchlist"
    return "market_overview"


def _event_text(event: ReportEvent) -> str:
    return " ".join(
        [
            event.headline,
            event.factual_summary,
            event.market_relevance,
            " ".join(event.assets),
            " ".join(event.quant_topics),
        ]
    ).lower()


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
