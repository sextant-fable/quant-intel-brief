"""Phase 8 daily HTML report generation tests."""

from __future__ import annotations

from datetime import date

from app.llm.schemas import EventSummary, SummaryResult
from app.reports.generator import SECTION_DEFINITIONS, DailyReport, generate_daily_report
from app.reports.templates import render_email_report


def _summary_result(
    event_id: str,
    headline: str,
    *,
    score: float = 80.0,
    tickers: list[str] | None = None,
    assets: list[str] | None = None,
    quant_topics: list[str] | None = None,
    source_urls: list[str] | None = None,
) -> SummaryResult:
    urls = source_urls if source_urls is not None else [f"https://example.test/{event_id}"]
    return SummaryResult(
        success=True,
        ranked_item_id=f"ranked-{event_id}",
        event_id=event_id,
        ranked_score=score,
        summary=EventSummary(
            event_id=event_id,
            headline=headline,
            factual_summary=f"{headline} was reported by cited sources.",
            market_relevance="Relevant as an informational market or quant workflow signal.",
            uncertainty="Follow-up source coverage may change the interpretation.",
            source_ids=[f"source-{index}" for index, _ in enumerate(urls, start=1)],
            source_urls=urls,
            tickers=tickers or [],
            assets=assets or [],
            quant_topics=quant_topics or [],
        ),
    )


def test_report_sections_are_ordered_and_classified() -> None:
    report = generate_daily_report(
        [
            _summary_result("market", "Broad market breadth update"),
            _summary_result("macro", "FOMC inflation path update", assets=["macro"]),
            _summary_result("etf", "SPY options skew rises", assets=["options"]),
            _summary_result("sec", "Issuer files 10-Q update"),
            _summary_result("research", "New factor model paper", quant_topics=["factor"]),
            _summary_result(
                "community",
                "GitHub community library release",
                quant_topics=["github"],
            ),
            _summary_result("watch", "NVDA supply chain item", tickers=["NVDA"]),
        ],
        report_date=date(2026, 7, 8),
    )

    assert [section.key for section in report.sections] == [key for key, _ in SECTION_DEFINITIONS]

    by_key = {section.key: section for section in report.sections}
    assert by_key["market_overview"].events[0].event_id == "market"
    assert by_key["macro_fed"].events[0].event_id == "macro"
    assert by_key["etf_options"].events[0].event_id == "etf"
    assert by_key["sec_filings"].events[0].event_id == "sec"
    assert by_key["research"].events[0].event_id == "research"
    assert by_key["github_community"].events[0].event_id == "community"
    assert by_key["watchlist"].events[0].event_id == "watch"


def test_empty_report_renders_without_events() -> None:
    report = generate_daily_report([], report_date=date(2026, 7, 8))

    html = render_email_report(report)

    assert "No ranked summaries were available" in report.source_coverage_note
    assert html.count("No qualifying summarized events for this section.") == len(
        SECTION_DEFINITIONS
    )
    assert "daily-report" in html


def test_report_excludes_failed_or_uncited_summaries() -> None:
    failed = SummaryResult(success=False, event_id="failed", error_message="LLM failed")
    uncited = _summary_result("uncited", "Uncited item", source_urls=[])

    report = generate_daily_report([failed, uncited], report_date=date(2026, 7, 8))

    assert sum(len(section.events) for section in report.sections) == 0
    assert "0 summarized events included; 2 result(s) skipped" in report.source_coverage_note


def test_rendered_report_contains_source_links_and_escapes_headlines() -> None:
    report = generate_daily_report(
        [
            _summary_result(
                "escape",
                "Volatility <script>alert('x')</script> update",
                assets=["options"],
                source_urls=["https://example.test/source"],
            )
        ],
        report_date=date(2026, 7, 8),
        title="Morning Brief",
    )

    html = render_email_report(report)

    assert "Morning Brief" in html
    assert "https://example.test/source" in html
    assert "&lt;script&gt;" in html
    assert "<script>alert" not in html


def test_report_model_requires_source_references() -> None:
    report = generate_daily_report(
        [_summary_result("cited", "Cited market update", source_urls=["https://example.test/a"])],
        report_date=date(2026, 7, 8),
    )

    event = next(event for section in report.sections for event in section.events)

    assert isinstance(report, DailyReport)
    assert event.source_ids
    assert event.source_urls
