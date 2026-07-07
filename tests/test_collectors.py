"""Collector framework and RSS adapter tests."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx
from sqlmodel import Session, select

from app.collectors.base import (
    CollectorConfig,
    CollectorStatus,
    persist_collector_result,
)
from app.collectors.rss import RssCollector
from app.db.models import ContentItem, RawItem, Source, SourceStatus
from app.db.session import create_db_engine, init_db

FIXTURES = Path(__file__).parent / "fixtures"


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
