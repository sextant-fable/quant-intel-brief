"""Manual daily job orchestration."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path

from sqlmodel import Session

from app.collectors.base import (
    CollectorPersistenceSummary,
    CollectorRunResult,
    CollectorStatus,
    hash_text,
    persist_collector_result,
)
from app.core.config import get_settings
from app.core.timezones import UTC, utc_now
from app.db.models import DeliveryLog, Report, ReportSection
from app.db.session import create_db_engine, init_db
from app.email.sender import EmailDeliveryResult, EmailSender, build_report_email
from app.llm.schemas import SummaryResult
from app.reports.generator import DailyReport, ReportSectionData, generate_daily_report
from app.reports.templates import render_email_report


@dataclass(frozen=True, slots=True)
class DailyRunResult:
    """Summary of one local daily run."""

    report_id: str
    status: str
    collector_count: int
    source_failure_count: int
    html_path: str | None
    delivery_status: str | None
    source_coverage_note: str


def run_daily(
    session: Session,
    *,
    collector_results: Iterable[CollectorRunResult] = (),
    summary_results: Iterable[SummaryResult] = (),
    report_date: date | None = None,
    report_title: str = "Quant Intel Brief",
    reports_dir: Path | None = None,
    email_sender: EmailSender | None = None,
    report_recipients: Iterable[str] | str | None = None,
    dry_run_email: bool = True,
) -> DailyRunResult:
    """Run the local daily pipeline with injected fixture/configured results."""
    persistence_summaries = [
        persist_collector_result(session, result) for result in collector_results
    ]
    daily_report = generate_daily_report(
        summary_results,
        report_date=report_date or utc_now().date(),
        title=report_title,
    )
    source_failure_count = _source_failure_count(persistence_summaries)
    daily_report.source_coverage_note = _coverage_note(
        daily_report.source_coverage_note,
        persistence_summaries,
        source_failure_count,
    )
    html = render_email_report(daily_report)
    html_path = _write_report_html(daily_report, html, reports_dir)
    report = _persist_report(session, daily_report, html_path)
    delivery_result = _maybe_send_preview(
        session,
        report,
        daily_report,
        email_sender=email_sender,
        report_recipients=report_recipients,
        dry_run_email=dry_run_email,
    )
    session.commit()

    return DailyRunResult(
        report_id=report.id,
        status=report.status,
        collector_count=len(persistence_summaries),
        source_failure_count=source_failure_count,
        html_path=str(html_path) if html_path else None,
        delivery_status=delivery_result.status if delivery_result else None,
        source_coverage_note=daily_report.source_coverage_note,
    )


def main() -> None:
    """Run a local empty daily job from the command line."""
    settings = get_settings()
    engine = create_db_engine(settings.database_url)
    init_db(engine)
    with Session(engine) as session:
        result = run_daily(session, report_date=utc_now().date())
    print(  # noqa: T201
        f"Created local report {result.report_id} with status {result.status}. "
        "No collectors, LLM calls, or email sends run by default."
    )


def _persist_report(
    session: Session,
    daily_report: DailyReport,
    html_path: Path | None,
) -> Report:
    report = Report(
        report_date=datetime.combine(daily_report.report_date, time.min, tzinfo=UTC),
        title=daily_report.title,
        status="draft",
        html_path=str(html_path) if html_path else None,
        source_coverage_note=daily_report.source_coverage_note,
    )
    session.add(report)
    session.flush()

    for section in daily_report.sections:
        session.add(_report_section(report, section))
    session.flush()
    return report


def _report_section(report: Report, section: ReportSectionData) -> ReportSection:
    return ReportSection(
        report_id=report.id,
        section_key=section.key,
        title=section.title,
        position=section.position,
        content=_section_content(section),
        source_refs=sorted({url for event in section.events for url in event.source_urls}),
    )


def _section_content(section: ReportSectionData) -> str | None:
    if not section.events:
        return None
    return "\n".join(
        f"{event.headline}: {event.factual_summary}" for event in section.events
    )


def _write_report_html(
    daily_report: DailyReport,
    html: str,
    reports_dir: Path | None,
) -> Path | None:
    if reports_dir is None:
        return None
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{daily_report.report_date.isoformat()}-quant-intel-brief.html"
    path.write_text(html, encoding="utf-8")
    return path


def _maybe_send_preview(
    session: Session,
    report: Report,
    daily_report: DailyReport,
    *,
    email_sender: EmailSender | None,
    report_recipients: Iterable[str] | str | None,
    dry_run_email: bool,
) -> EmailDeliveryResult | None:
    if email_sender is None or not report_recipients:
        return None

    message = build_report_email(daily_report, report_recipients)
    result = email_sender.send(message, dry_run=dry_run_email)
    session.add(
        DeliveryLog(
            report_id=report.id,
            provider=result.provider,
            recipient_hash=hash_text(",".join(message.recipients)),
            status=result.status,
            error_message=result.error_message,
            delivered_at=utc_now() if result.status == "sent" else None,
        )
    )
    return result


def _coverage_note(
    report_note: str,
    persistence_summaries: list[CollectorPersistenceSummary],
    source_failure_count: int,
) -> str:
    if not persistence_summaries:
        return report_note
    success_count = sum(
        1 for summary in persistence_summaries if summary.status == CollectorStatus.SUCCESS
    )
    return (
        f"{report_note} Source runs: {success_count} successful, "
        f"{source_failure_count} noncritical failure(s)."
    )


def _source_failure_count(summaries: list[CollectorPersistenceSummary]) -> int:
    return sum(
        1
        for summary in summaries
        if summary.status not in {CollectorStatus.SUCCESS, CollectorStatus.EMPTY}
    )


__all__ = ["DailyRunResult", "main", "run_daily"]


if __name__ == "__main__":
    main()
