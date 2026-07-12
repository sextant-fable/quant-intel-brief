"""Demo seed tests."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from app.core.timezones import UTC
from app.db.models import ContentItem, Report, ReportEventRecord, ReportSection, SourceStatus
from app.db.session import create_db_engine, init_db
from app.jobs.seed_demo import DEMO_REPORT_TITLE, seed_demo


def _session() -> Session:
    engine = create_db_engine("sqlite://")
    init_db(engine)
    return Session(engine)


def test_seed_demo_populates_dashboard_data() -> None:
    now = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)
    with _session() as session:
        result = seed_demo(session, now=now)
        items = session.exec(select(ContentItem).order_by(ContentItem.source_name)).all()
        statuses = session.exec(select(SourceStatus).order_by(SourceStatus.source_name)).all()
        report = session.get(Report, result.report_id)
        sections = session.exec(
            select(ReportSection).where(ReportSection.report_id == result.report_id)
        ).all()
        report_events = session.exec(
            select(ReportEventRecord).where(ReportEventRecord.report_id == result.report_id)
        ).all()

    assert result.content_items == 6
    assert result.source_statuses == 6
    assert len(items) == 6
    assert len(statuses) == 6
    assert report is not None
    assert report.title == DEMO_REPORT_TITLE
    assert len(sections) == 5
    assert len(report_events) == 6
    assert any(item.tickers == ["SPY"] for item in items)
    assert any(item.source_name == "sec_edgar" for item in items)
    assert any(section.source_refs for section in sections)


def test_seed_demo_is_idempotent_for_content_and_demo_report() -> None:
    now = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)
    with _session() as session:
        first = seed_demo(session, now=now)
        second = seed_demo(session, now=now)
        items = session.exec(select(ContentItem)).all()
        demo_reports = session.exec(select(Report).where(Report.title == DEMO_REPORT_TITLE)).all()

    assert first.content_items == 6
    assert second.content_items == 6
    assert len(items) == 6
    assert len(demo_reports) == 1
