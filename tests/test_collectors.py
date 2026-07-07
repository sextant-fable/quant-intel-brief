"""Collector framework and RSS adapter tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from sqlmodel import Session, select

from app.collectors.alphavantage import AlphaVantageCollector
from app.collectors.arxiv import ArxivCollector
from app.collectors.base import (
    CollectorConfig,
    CollectorStatus,
    SourceCollector,
    persist_collector_result,
)
from app.collectors.finnhub import FinnhubCollector
from app.collectors.fred import FredCollector
from app.collectors.gdelt import GdeltCollector
from app.collectors.github import GitHubCollector
from app.collectors.newsapi import NewsApiCollector
from app.collectors.rss import RssCollector
from app.collectors.sec_edgar import SecEdgarCollector
from app.db.models import ContentItem, RawItem, Source, SourceStatus
from app.db.session import create_db_engine, init_db

FIXTURES = Path(__file__).parent / "fixtures"
FORBIDDEN_TEXT_KEYS = {"body", "content", "full_text", "article_text", "transcript"}


def test_rss_feed_parse_success_from_fixture() -> None:
    collector = RssCollector(
        feed_url="https://feeds.example.test/rss.xml",
        source_name="fixture_rss",
    )

    result = collector.parse_feed((FIXTURES / "sample_rss.xml").read_text(encoding="utf-8"))

    assert result.status == CollectorStatus.SUCCESS
    assert len(result.items) == 2
    assert result.items[0].source_item_id == "fixture-1"
    assert result.items[0].canonical_url == "https://example.test/research/etf-flows"
    assert result.items[0].publisher == "Fixture Quant Feed"
    assert result.items[0].language == "en-us"
    assert result.items[0].excerpt == "Compact market metadata with HTML tags."
    assert "content" not in result.items[0].raw_metadata


def test_rss_empty_feed_returns_empty_result() -> None:
    collector = RssCollector(feed_url="https://feeds.example.test/empty.xml")

    result = collector.parse_feed(
        """<?xml version="1.0"?><rss version="2.0"><channel><title>Empty</title></channel></rss>"""
    )

    assert result.status == CollectorStatus.EMPTY
    assert result.items == []
    assert "no entries" in (result.message or "")


def test_duplicate_source_ids_and_canonical_urls_are_handled_deterministically() -> None:
    collector = RssCollector(feed_url="https://feeds.example.test/duplicates.xml")

    result = collector.parse_feed(
        """<?xml version="1.0"?>
        <rss version="2.0">
          <channel>
            <title>Duplicate Feed</title>
            <item>
              <guid>duplicate-id</guid>
              <title>First item wins</title>
              <link>https://example.test/item#section</link>
              <description>First compact excerpt.</description>
            </item>
            <item>
              <guid>duplicate-id</guid>
              <title>Duplicate source ID</title>
              <link>https://example.test/item?variant=ignored</link>
              <description>Duplicate compact excerpt.</description>
            </item>
            <item>
              <guid>different-id</guid>
              <title>Duplicate canonical URL</title>
              <link>https://example.test/item</link>
              <description>Duplicate compact excerpt.</description>
            </item>
          </channel>
        </rss>"""
    )

    assert result.status == CollectorStatus.SUCCESS
    assert [item.title for item in result.items] == ["First item wins"]
    assert result.skipped_duplicates == 2


@pytest.mark.asyncio
@respx.mock
async def test_rss_http_timeout_and_rate_limit_are_reported() -> None:
    timeout_url = "https://feeds.example.test/timeout.xml"
    rate_limit_url = "https://feeds.example.test/rate-limit.xml"
    config = CollectorConfig(retry_attempts=0, retry_backoff_seconds=0)

    respx.get(timeout_url).mock(side_effect=httpx.ReadTimeout("fixture timeout"))
    respx.get(rate_limit_url).mock(return_value=httpx.Response(429, text="slow down"))

    timeout_result = await RssCollector(feed_url=timeout_url, config=config).collect()
    rate_limit_result = await RssCollector(feed_url=rate_limit_url, config=config).collect()

    assert timeout_result.status == CollectorStatus.TIMEOUT
    assert "timed out" in (timeout_result.message or "")
    assert rate_limit_result.status == CollectorStatus.RATE_LIMITED
    assert "429" in (rate_limit_result.message or "")


def test_collector_result_persists_normalized_metadata_and_status() -> None:
    engine = create_db_engine("sqlite://")
    init_db(engine)
    collector = RssCollector(
        feed_url="https://feeds.example.test/rss.xml",
        source_name="fixture_rss",
        display_name="Fixture RSS",
    )
    result = collector.parse_feed((FIXTURES / "sample_rss.xml").read_text(encoding="utf-8"))

    with Session(engine) as session:
        summary = persist_collector_result(session, result)
        sources = session.exec(select(Source)).all()
        raw_items = session.exec(select(RawItem)).all()
        content_items = session.exec(select(ContentItem).order_by(ContentItem.source_item_id)).all()
        statuses = session.exec(select(SourceStatus)).all()

    assert summary.status == CollectorStatus.SUCCESS
    assert summary.raw_items_seen == 2
    assert summary.content_items_seen == 2
    assert [source.name for source in sources] == ["fixture_rss"]
    assert len(raw_items) == 2
    assert [item.source_item_id for item in content_items] == ["fixture-1", "fixture-2"]
    assert content_items[0].title == "ETF flows rebalance into systematic value"
    assert content_items[0].excerpt == "Compact market metadata with HTML tags."
    assert not hasattr(content_items[0], "content_text")
    assert len(statuses) == 1
    assert statuses[0].status == CollectorStatus.SUCCESS.value


def _phase2_config() -> CollectorConfig:
    return CollectorConfig(max_items=5, retry_attempts=0, retry_backoff_seconds=0)


def _phase2_cases() -> list[tuple[str, SourceCollector, str, str, str]]:
    config = _phase2_config()
    return [
        (
            "newsapi",
            NewsApiCollector(api_key="fixture-key", config=config),
            "https://newsapi.org/v2/everything",
            "newsapi_response.json",
            "ETF options volume rises before rebalance",
        ),
        (
            "gdelt",
            GdeltCollector(config=config),
            "https://api.gdeltproject.org/api/v2/doc/doc",
            "gdelt_response.json",
            "Macro volatility story appears in global coverage",
        ),
        (
            "alphavantage",
            AlphaVantageCollector(api_key="fixture-key", config=config),
            "https://www.alphavantage.co/query",
            "alphavantage_news.json",
            "Systematic strategy note mentions factor rotation",
        ),
        (
            "finnhub",
            FinnhubCollector(api_key="fixture-key", config=config),
            "https://finnhub.io/api/v1/news",
            "finnhub_news.json",
            "Options desk flags ETF hedging demand",
        ),
        (
            "fred",
            FredCollector(api_key="fixture-key", config=config),
            "https://api.stlouisfed.org/fred/series/observations",
            "fred_observations.json",
            "FRED FEDFUNDS observation for 2026-07-01",
        ),
        (
            "sec_edgar",
            SecEdgarCollector(user_agent="quant-intel-test contact@example.test", config=config),
            "https://data.sec.gov/submissions/CIK0000320193.json",
            "sec_submissions.json",
            "Fixture Public Company 10-Q filing 0000320193-26-000001",
        ),
        (
            "arxiv",
            ArxivCollector(config=config),
            "https://export.arxiv.org/api/query",
            "arxiv_response.xml",
            "Mocked quantitative finance paper",
        ),
        (
            "github",
            GitHubCollector(config=config),
            "https://api.github.com/search/repositories",
            "github_search.json",
            "fixture/quant-toolkit",
        ),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case_name", "collector", "endpoint", "fixture_name", "expected_title"),
    _phase2_cases(),
    ids=[case[0] for case in _phase2_cases()],
)
@respx.mock
async def test_phase2_collectors_parse_success_from_mocked_responses(
    case_name: str,
    collector: SourceCollector,
    endpoint: str,
    fixture_name: str,
    expected_title: str,
) -> None:
    response_text = (FIXTURES / fixture_name).read_text(encoding="utf-8")
    respx.get(endpoint).mock(return_value=httpx.Response(200, text=response_text))

    result = await collector.collect()

    assert result.source_name == case_name
    assert result.status == CollectorStatus.SUCCESS
    assert len(result.items) == 1
    item = result.items[0]
    assert item.title == expected_title
    assert item.source_item_id
    assert item.canonical_url is not None
    assert item.canonical_url.startswith("https://")
    assert item.published_at is not None
    assert item.fetched_at is not None
    assert item.raw_payload_hash
    assert FORBIDDEN_TEXT_KEYS.isdisjoint(item.raw_metadata)
    assert not hasattr(item, "content_text")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "collector",
    [
        NewsApiCollector(config=_phase2_config()),
        AlphaVantageCollector(config=_phase2_config()),
        FinnhubCollector(config=_phase2_config()),
        FredCollector(config=_phase2_config()),
        SecEdgarCollector(config=_phase2_config()),
    ],
    ids=["newsapi", "alphavantage", "finnhub", "fred", "sec_edgar"],
)
async def test_phase2_key_or_user_agent_required_collectors_fail_before_http(
    collector: SourceCollector,
) -> None:
    result = await collector.collect()

    assert result.status == CollectorStatus.FAILED
    assert "required" in (result.message or "")
    assert result.items == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case_name", "collector", "endpoint", "_fixture_name", "_expected_title"),
    _phase2_cases(),
    ids=[case[0] for case in _phase2_cases()],
)
@respx.mock
async def test_phase2_collectors_report_rate_limits(
    case_name: str,
    collector: SourceCollector,
    endpoint: str,
    _fixture_name: str,
    _expected_title: str,
) -> None:
    respx.get(endpoint).mock(return_value=httpx.Response(429, text="rate limited"))

    result = await collector.collect()

    assert result.source_name == case_name
    assert result.status == CollectorStatus.RATE_LIMITED
    assert result.items == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case_name", "collector", "endpoint", "_fixture_name", "_expected_title"),
    _phase2_cases(),
    ids=[case[0] for case in _phase2_cases()],
)
@respx.mock
async def test_phase2_collectors_report_http_failures(
    case_name: str,
    collector: SourceCollector,
    endpoint: str,
    _fixture_name: str,
    _expected_title: str,
) -> None:
    respx.get(endpoint).mock(return_value=httpx.Response(500, text="server error"))

    result = await collector.collect()

    assert result.source_name == case_name
    assert result.status == CollectorStatus.FAILED
    assert result.items == []


@pytest.mark.asyncio
async def test_phase2_collector_results_persist_normalized_metadata() -> None:
    engine = create_db_engine("sqlite://")
    init_db(engine)

    with Session(engine) as session:
        for _, collector, _, fixture_name, _ in _phase2_cases():
            response_text = (FIXTURES / fixture_name).read_text(encoding="utf-8")
            if isinstance(collector, ArxivCollector):
                result = collector.parse_feed(response_text)
            else:
                data: Any = httpx.Response(200, text=response_text).json()
                result = await _collect_from_fixture_data(collector, data)
            persist_collector_result(session, result)

        statuses = session.exec(select(SourceStatus)).all()
        content_items = session.exec(select(ContentItem)).all()

    assert len(statuses) == len(_phase2_cases())
    assert len(content_items) == len(_phase2_cases())
    assert all(item.excerpt is None or len(item.excerpt) <= 500 for item in content_items)
    assert all(not hasattr(item, "content_text") for item in content_items)


async def _collect_from_fixture_data(
    collector: SourceCollector,
    data: Any,
) -> Any:
    endpoint = next(
        case[2]
        for case in _phase2_cases()
        if case[1].source_name == collector.source_name
    )
    with respx.mock:
        respx.get(endpoint).mock(return_value=httpx.Response(200, json=data))
        return await collector.collect()
