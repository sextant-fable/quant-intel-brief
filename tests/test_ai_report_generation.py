"""User-triggered AI report generation tests."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import SecretStr
from sqlmodel import Session, select

from app.core.config import Settings
from app.core.timezones import UTC
from app.db.models import ContentItem, Report, ReportSection
from app.db.session import create_db_engine, init_db
from app.jobs.generate_ai_report import generate_ai_report_from_local_content


class FakeSummaryClient:
    """Fake OpenAI-compatible client that never makes network calls."""

    def __init__(self) -> None:
        self.calls: list[list[dict[str, str]]] = []

    def complete_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        self.calls.append(messages)
        return {
            "event_id": "event-1",
            "headline": "SPY options volatility item",
            "factual_summary": "The provided source reports a SPY options volatility item.",
            "market_relevance": "Relevant as an informational options-volatility signal.",
            "uncertainty": "Only one local source record was summarized.",
            "source_ids": ["content-1"],
            "source_urls": ["https://example.test/spy-options"],
            "tickers": ["SPY"],
            "assets": ["options", "etf"],
            "quant_topics": ["volatility"],
            "insufficient_evidence": False,
        }


def test_generate_ai_report_from_local_content_uses_injected_llm_client(
    tmp_path: Path,
) -> None:
    engine = create_db_engine("sqlite://")
    init_db(engine)
    fake_client = FakeSummaryClient()

    with Session(engine) as session:
        session.add(
            ContentItem(
                id="content-1",
                source_name="newsapi",
                source_item_id="source-1",
                url="https://example.test/spy-options",
                title="SPY options volatility item",
                summary="Options desks discussed SPY implied volatility.",
                fetched_at=datetime(2026, 7, 8, 11, 0, tzinfo=UTC),
            )
        )
        session.commit()

        result = generate_ai_report_from_local_content(
            session,
            settings=Settings(llm_api_key=SecretStr("test-key")),
            client=fake_client,
            report_date=datetime(2026, 7, 8, tzinfo=UTC).date(),
            reports_dir=tmp_path,
            max_events=1,
        )
        reports = session.exec(select(Report)).all()
        sections = session.exec(select(ReportSection)).all()

    assert result.source_item_count == 1
    assert result.ranked_event_count == 1
    assert result.successful_summary_count == 1
    assert result.failed_summary_count == 0
    assert len(fake_client.calls) == 1
    assert len(reports) == 1
    assert any(section.content for section in sections)
    assert result.report.html_path is not None
    assert Path(result.report.html_path).is_file()
