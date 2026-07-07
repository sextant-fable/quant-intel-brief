"""Phase 10 job orchestration, scheduler, and retention tests."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.collectors.base import CollectedItem, CollectorRunResult, CollectorStatus
from app.core.config import Settings
from app.core.timezones import UTC
from app.db.models import (
    Cluster,
    ContentItem,
    DeliveryLog,
    EventItem,
    RawItem,
    Report,
    ReportSection,
    Source,
    SourceStatus,
)
from app.db.session import create_db_engine, init_db
from app.email.sender import DryRunEmailSender
from app.jobs.cleanup import cleanup_retention
from app.jobs.run_daily import run_daily
from app.jobs.scheduler import DAILY_JOB_ID, build_scheduler, parse_daily_run_time
from app.llm.schemas import EventSummary, SummaryResult


def _session() -> Session:
    engine = create_db_engine("sqlite://")
    init_db(engine)
    return Session(engine)


def _collector_result(
    source_name: str = "newsapi",
    status: CollectorStatus = CollectorStatus.SUCCESS,
) -> CollectorRunResult:
    item_count = 1 if status == CollectorStatus.SUCCESS else 0
    return CollectorRunResult(
        source_name=source_name,
        source_type="news",
        display_name=source_name.title(),
        status=status,
        items=[
            CollectedItem(
                source_name=source_name,
                source_item_id=f"{source_name}-1",
                url=f"https://example.test/{source_name}/1",
                title="SPY options volatility update",
                summary="Metadata summary only.",
                published_at=datetime(2026, 7, 8, 11, 0, tzinfo=UTC),
            )
            for _ in range(item_count)
        ],
        message=None if status == CollectorStatus.SUCCESS else "Fixture source failed.",
        fetched_at=datetime(2026, 7, 8, 11, 5, tzinfo=UTC),
    )


def _summary_result() -> SummaryResult:
    return SummaryResult(
        success=True,
        ranked_item_id="ranked-1",
        event_id="event-1",
        ranked_score=91.0,
        summary=EventSummary(
            event_id="event-1",
            headline="SPY options volatility update",
            factual_summary="Cited sources reported an options volatility update.",
            market_relevance="Relevant as an informational volatility input.",
            uncertainty="Further source coverage may change the interpretation.",
            source_ids=["source-1"],
            source_urls=["https://example.test/newsapi/1"],
            tickers=["SPY"],
            assets=["options"],
            quant_topics=["volatility"],
        ),
    )


def test_run_daily_orchestrates_fixture_collectors_and_report(tmp_path: Path) -> None:
    with _session() as session:
        result = run_daily(
            session,
            collector_results=[
                _collector_result("newsapi"),
                _collector_result("finnhub", CollectorStatus.FAILED),
            ],
            summary_results=[_summary_result()],
            report_date=datetime(2026, 7, 8, tzinfo=UTC).date(),
            reports_dir=tmp_path,
            email_sender=DryRunEmailSender(),
            report_recipients="alpha@example.test",
        )

        report = session.get(Report, result.report_id)
        statuses = session.exec(select(SourceStatus).order_by(SourceStatus.source_name)).all()
        sections = session.exec(
            select(ReportSection).where(ReportSection.report_id == result.report_id)
        ).all()
        delivery_logs = session.exec(select(DeliveryLog)).all()

    assert result.collector_count == 2
    assert result.source_failure_count == 1
    assert result.delivery_status == "dry_run"
    assert result.html_path is not None
    assert Path(result.html_path).is_file()
    assert report is not None
    assert "noncritical failure" in (report.source_coverage_note or "")
    assert [status.source_name for status in statuses] == ["finnhub", "newsapi"]
    assert len(sections) == 7
    assert any("https://example.test/newsapi/1" in section.source_refs for section in sections)
    assert len(delivery_logs) == 1
    assert delivery_logs[0].recipient_hash is not None


def test_run_daily_creates_report_despite_noncritical_source_failure() -> None:
    with _session() as session:
        result = run_daily(
            session,
            collector_results=[_collector_result("newsapi", CollectorStatus.FAILED)],
            summary_results=[],
            report_date=datetime(2026, 7, 8, tzinfo=UTC).date(),
        )
        report = session.get(Report, result.report_id)

    assert result.source_failure_count == 1
    assert report is not None
    assert "No ranked summaries were available" in (report.source_coverage_note or "")
    assert "noncritical failure" in (report.source_coverage_note or "")


def test_cleanup_retention_deletes_old_rows_and_preserves_recent() -> None:
    now = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)
    old = now - timedelta(days=45)
    recent = now - timedelta(days=5)

    with _session() as session:
        source = Source(name="fixture", source_type="fixture", display_name="Fixture")
        session.add(source)
        session.flush()
        session.add(
            RawItem(
                source_id=source.id,
                source_item_id="old-raw",
                url="https://example.test/old-raw",
                fetched_at=old,
                retention_until=old,
            )
        )
        recent_item = ContentItem(
            source_name="fixture",
            source_item_id="recent",
            url="https://example.test/recent",
            title="Recent item",
            fetched_at=recent,
            retention_until=now + timedelta(days=20),
        )
        old_item = ContentItem(
            source_name="fixture",
            source_item_id="old",
            url="https://example.test/old",
            title="Old item",
            fetched_at=old,
            retention_until=old,
        )
        session.add(recent_item)
        session.add(old_item)
        old_cluster = Cluster(id="old-cluster", canonical_title="Old cluster", created_at=old)
        session.add(old_cluster)
        session.add(
            EventItem(
                cluster_id="old-cluster",
                item_id="old",
                source_name="fixture",
                created_at=old,
            )
        )
        old_report = Report(
            id="old-report",
            report_date=old,
            title="Old Report",
            status="draft",
        )
        recent_report = Report(
            id="recent-report",
            report_date=recent,
            title="Recent Report",
            status="draft",
        )
        session.add(old_report)
        session.add(recent_report)
        session.add(ReportSection(report_id="old-report", section_key="macro", title="Macro"))
        session.add(
            DeliveryLog(
                report_id="old-report",
                provider="dry_run",
                status="dry_run",
                created_at=old,
            )
        )
        session.commit()

        result = cleanup_retention(session, now=now, retain_days=30)
        remaining_items = session.exec(select(ContentItem)).all()
        remaining_reports = session.exec(select(Report)).all()
        remaining_sections = session.exec(select(ReportSection)).all()

    assert result.deleted_counts["content_items"] == 1
    assert result.deleted_counts["raw_items"] == 1
    assert result.deleted_counts["clusters"] == 1
    assert result.deleted_counts["event_items"] == 1
    assert result.deleted_counts["reports"] == 1
    assert result.deleted_counts["report_sections"] == 1
    assert result.deleted_counts["delivery_logs"] == 1
    assert [item.source_item_id for item in remaining_items] == ["recent"]
    assert [report.id for report in remaining_reports] == ["recent-report"]
    assert remaining_sections == []


def test_scheduler_is_disabled_by_default() -> None:
    scheduler = build_scheduler(Settings(), job_func=lambda: None)

    assert scheduler is None


def test_scheduler_builds_optional_local_job_without_starting() -> None:
    scheduler = build_scheduler(
        Settings(enable_scheduler=True, daily_run_time="06:30"),
        job_func=lambda: None,
    )

    assert scheduler is not None
    assert scheduler.get_job(DAILY_JOB_ID) is not None
    assert scheduler.running is False


def test_scheduler_rejects_invalid_time() -> None:
    assert parse_daily_run_time("06:30") == (6, 30)
    with pytest.raises(ValueError):
        parse_daily_run_time("25:00")
