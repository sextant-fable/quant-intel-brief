"""Phase 9 local dashboard route tests."""

from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import Settings
from app.core.timezones import UTC
from app.db.models import ContentItem, Report, ReportSection, SourceStatus
from app.db.session import create_db_engine
from app.main import create_app


def _client_with_session() -> tuple[TestClient, Session]:
    engine = create_db_engine("sqlite://")
    app = create_app(
        settings=Settings(database_url="sqlite://", dashboard_title="Dashboard Test"),
        engine=engine,
    )
    return TestClient(app), Session(engine)


def test_empty_database_dashboard_routes_render() -> None:
    client, session = _client_with_session()
    session.close()

    assert client.get("/").status_code == 200
    today = client.get("/dashboard/today")
    feed = client.get("/feed")
    reports = client.get("/reports")
    sources = client.get("/sources")

    assert today.status_code == 200
    assert "No local content items yet." in today.text
    assert feed.status_code == 200
    assert "No local content items match the current filters." in feed.text
    assert reports.status_code == 200
    assert "No local reports have been generated yet." in reports.text
    assert sources.status_code == 200
    assert "No source status records yet." in sources.text


def test_feed_filters_local_content_items() -> None:
    client, session = _client_with_session()
    with session:
        session.add(
            ContentItem(
                source_name="newsapi",
                source_item_id="match",
                url="https://example.test/match",
                title="SPY volatility item",
                summary="Filtered item",
                published_at=datetime(2026, 7, 8, 12, 0, tzinfo=UTC),
                tickers=["SPY"],
                assets=["etf"],
                quant_topics=["volatility"],
            )
        )
        session.add(
            ContentItem(
                source_name="reddit",
                source_item_id="other",
                url="https://example.test/other",
                title="Unmatched community item",
                published_at=datetime(2026, 7, 8, 12, 0, tzinfo=UTC),
                tickers=["NVDA"],
                assets=["equity"],
                quant_topics=["community"],
            )
        )
        session.commit()

    response = client.get(
        "/feed",
        params={
            "date": "2026-07-08",
            "source": "newsapi",
            "ticker": "SPY",
            "asset_class": "etf",
            "quant_theme": "volatility",
        },
    )

    assert response.status_code == 200
    assert "SPY volatility item" in response.text
    assert "Unmatched community item" not in response.text


def test_source_status_redacts_secret_like_messages_in_json_and_html() -> None:
    client, session = _client_with_session()
    with session:
        session.add(
            SourceStatus(
                source_name="newsapi",
                status="failed",
                message="api_key=abc123 token=super-secret",
            )
        )
        session.commit()

    json_response = client.get("/status/sources")
    html_response = client.get("/sources")

    assert json_response.status_code == 200
    assert html_response.status_code == 200
    assert "abc123" not in json_response.text
    assert "super-secret" not in json_response.text
    assert "abc123" not in html_response.text
    assert "super-secret" not in html_response.text
    assert "***" in json_response.text
    assert "***" in html_response.text


def test_report_archive_and_detail_render_local_reports() -> None:
    client, session = _client_with_session()
    with session:
        report = Report(
            id="report-1",
            report_date=datetime(2026, 7, 8, 12, 0, tzinfo=UTC),
            title="Morning Report",
            status="draft",
            source_coverage_note="1 summarized event included.",
        )
        session.add(report)
        session.add(
            ReportSection(
                report_id=report.id,
                section_key="macro_fed",
                title="Macro/Fed",
                position=1,
                content="FOMC path update.",
                source_refs=["https://example.test/fomc"],
            )
        )
        session.commit()

    archive = client.get("/reports")
    detail = client.get("/reports/report-1")
    missing = client.get("/reports/missing")

    assert archive.status_code == 200
    assert "Morning Report" in archive.text
    assert detail.status_code == 200
    assert "Macro/Fed" in detail.text
    assert "FOMC path update." in detail.text
    assert missing.status_code == 404


def test_static_assets_are_served_locally() -> None:
    client, session = _client_with_session()
    session.close()

    response = client.get("/static/css/main.css")

    assert response.status_code == 200
    assert "color-scheme" in response.text
