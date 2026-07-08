"""Phase 9 local dashboard route tests."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.collectors.base import CollectorPersistenceSummary, CollectorStatus
from app.core.config import Settings
from app.core.timezones import UTC
from app.db.models import ContentItem, Report, ReportSection, SourceStatus
from app.db.session import create_db_engine
from app.jobs.collect_once import CollectOnceResult
from app.main import create_app


def _client_with_session(env_path: Path | None = None) -> tuple[TestClient, Session]:
    engine = create_db_engine("sqlite://")
    app = create_app(
        settings=Settings(database_url="sqlite://", dashboard_title="Dashboard Test"),
        engine=engine,
    )
    if env_path is not None:
        app.state.env_file_path = env_path
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
    assert "built-in method" not in today.text
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


def test_llm_settings_page_saves_local_env_without_echoing_key(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    client, session = _client_with_session(env_path=env_path)
    session.close()

    get_response = client.get("/settings/llm")
    post_response = client.post(
        "/settings/llm",
        data={
            "provider": "glm",
            "api_key": "test-secret-key",
            "base_url": "https://api.z.ai/api/paas/v4/",
            "model": "glm-5.2",
        },
    )
    env_text = env_path.read_text(encoding="utf-8")

    assert get_response.status_code == 200
    assert "AI Settings" in get_response.text
    assert post_response.status_code == 200
    assert "AI settings saved locally" in post_response.text
    assert "test-secret-key" not in post_response.text
    assert "LLM_PROVIDER=glm" in env_text
    assert "LLM_API_KEY=test-secret-key" in env_text
    assert "LLM_BASE_URL=https://api.z.ai/api/paas/v4/" in env_text
    assert "LLM_MODEL=glm-5.2" in env_text


def test_llm_settings_blank_key_preserves_existing_key(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("LLM_API_KEY=existing-key\n", encoding="utf-8")
    client, session = _client_with_session(env_path=env_path)
    session.close()

    response = client.post(
        "/settings/llm",
        data={
            "provider": "kimi",
            "api_key": "",
            "base_url": "https://api.moonshot.ai/v1",
            "model": "kimi-k2.6",
        },
    )
    env_text = env_path.read_text(encoding="utf-8")

    assert response.status_code == 200
    assert "existing-key" not in response.text
    assert "LLM_API_KEY=existing-key" in env_text
    assert "LLM_PROVIDER=kimi" in env_text


def test_source_settings_page_saves_local_env_without_echoing_secrets(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    client, session = _client_with_session(env_path=env_path)
    session.close()

    get_response = client.get("/settings/sources")
    post_response = client.post(
        "/settings/sources",
        data={
            "action": "save",
            "source_rss": "on",
            "source_sec_edgar": "on",
            "source_arxiv": "on",
            "source_github": "on",
            "source_fred": "on",
            "rss_feed_urls": "https://feeds.example.test/a.xml\nhttps://feeds.example.test/b.xml",
            "sec_user_agent": "quant-intel-test contact@example.test",
            "sec_cik": "0000789019",
            "arxiv_search_query": "cat:q-fin.CP",
            "github_query": "topic:backtesting language:Python",
            "github_token": "github-secret-token",
            "fred_api_key": "fred-secret-key",
            "fred_series_id": "CPIAUCSL",
            "newsapi_key": "newsapi-secret-key",
            "newsapi_query": "ETF options",
            "gdelt_query": "systematic trading",
            "alphavantage_api_key": "alpha-secret-key",
            "alphavantage_topics": "financial_markets",
            "finnhub_api_key": "finnhub-secret-key",
            "finnhub_category": "forex",
            "reddit_access_token": "reddit-secret-token",
            "reddit_user_agent": "quant-intel-test",
            "reddit_query": "factor investing",
            "reddit_subreddit": "algotrading",
            "youtube_api_key": "youtube-secret-key",
            "youtube_query": "quant research",
            "x_bearer_token": "x-secret-token",
            "x_query": "quant finance lang:en",
            "stackexchange_key": "stack-secret-key",
            "stackexchange_query": "factor model",
            "stackexchange_site": "quant",
            "quantconnect_user_id": "qc-secret-user",
            "quantconnect_token": "qc-secret-token",
            "quantconnect_organization_id": "qc-org",
        },
    )
    env_text = env_path.read_text(encoding="utf-8")

    assert get_response.status_code == 200
    assert "Source Settings" in get_response.text
    assert post_response.status_code == 200
    assert "Source settings saved locally" in post_response.text
    assert "github-secret-token" not in post_response.text
    assert "fred-secret-key" not in post_response.text
    assert "newsapi-secret-key" not in post_response.text
    assert "alpha-secret-key" not in post_response.text
    assert "finnhub-secret-key" not in post_response.text
    assert "reddit-secret-token" not in post_response.text
    assert "youtube-secret-key" not in post_response.text
    assert "x-secret-token" not in post_response.text
    assert "stack-secret-key" not in post_response.text
    assert "qc-secret-user" not in post_response.text
    assert "qc-secret-token" not in post_response.text
    assert (
        "RSS_FEED_URLS=https://feeds.example.test/a.xml,https://feeds.example.test/b.xml"
        in env_text
    )
    assert "SEC_USER_AGENT=quant-intel-test contact@example.test" in env_text
    assert "GITHUB_TOKEN=github-secret-token" in env_text
    assert "FRED_API_KEY=fred-secret-key" in env_text
    assert "NEWSAPI_KEY=newsapi-secret-key" in env_text
    assert "ALPHAVANTAGE_API_KEY=alpha-secret-key" in env_text
    assert "FINNHUB_API_KEY=finnhub-secret-key" in env_text
    assert "REDDIT_ACCESS_TOKEN=reddit-secret-token" in env_text
    assert "YOUTUBE_API_KEY=youtube-secret-key" in env_text
    assert "X_BEARER_TOKEN=x-secret-token" in env_text
    assert "STACKEXCHANGE_KEY=stack-secret-key" in env_text
    assert "QUANTCONNECT_USER_ID=qc-secret-user" in env_text
    assert "QUANTCONNECT_TOKEN=qc-secret-token" in env_text


def test_source_settings_run_button_uses_manual_collect_without_live_http(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_path = tmp_path / ".env"
    captured: dict[str, Any] = {}

    async def fake_collect_once(
        session: Session,
        *,
        settings: Settings | None = None,
        sources: str | list[str] | tuple[str, ...] | None = None,
        collectors: Any = None,
    ) -> CollectOnceResult:
        captured["sources"] = tuple(sources or ())
        captured["fred_key"] = (
            settings.fred_api_key.get_secret_value()
            if settings is not None and settings.fred_api_key is not None
            else None
        )
        return CollectOnceResult(
            requested_sources=tuple(sources or ()),
            summaries=(
                CollectorPersistenceSummary(
                    source_name="arxiv",
                    status=CollectorStatus.SUCCESS,
                    raw_items_seen=1,
                    content_items_seen=1,
                    skipped_duplicates=0,
                ),
                CollectorPersistenceSummary(
                    source_name="fred",
                    status=CollectorStatus.FAILED,
                    raw_items_seen=0,
                    content_items_seen=0,
                    skipped_duplicates=0,
                ),
            ),
        )

    monkeypatch.setattr("app.web.routes.collect_once", fake_collect_once)
    client, session = _client_with_session(env_path=env_path)
    session.close()

    response = client.post(
        "/settings/sources",
        data={
            "action": "run",
            "source_arxiv": "on",
            "source_fred": "on",
            "rss_feed_urls": "",
            "sec_user_agent": "",
            "sec_cik": "0000320193",
            "arxiv_search_query": "cat:q-fin*",
            "github_query": "quant finance language:Python",
            "fred_api_key": "fred-secret-key",
            "fred_series_id": "FEDFUNDS",
        },
    )

    assert response.status_code == 200
    assert captured["sources"] == ("arxiv", "fred")
    assert captured["fred_key"] == "fred-secret-key"
    assert "Collector runs" in response.text
    assert "New items" in response.text
    assert "fred-secret-key" not in response.text
