"""Manual collect-once command tests."""

from __future__ import annotations

import pytest
from pydantic import SecretStr
from sqlmodel import Session, select

from app.collectors.base import CollectedItem, CollectorRunResult, CollectorStatus, SourceCollector
from app.core.config import Settings
from app.db.models import ContentItem, SourceStatus
from app.db.session import create_db_engine, init_db
from app.jobs.collect_once import (
    DEFAULT_SOURCES,
    build_collectors,
    collect_once,
    parse_sources,
)


def test_parse_sources_defaults_and_validates_supported_names() -> None:
    assert parse_sources(None) == DEFAULT_SOURCES
    assert parse_sources("") == DEFAULT_SOURCES
    assert parse_sources("rss, fred\narxiv") == ("rss", "fred", "arxiv")
    assert parse_sources(["github", "sec_edgar"]) == ("github", "sec_edgar")

    with pytest.raises(ValueError, match="Unsupported source"):
        parse_sources("rss,unknown")


def test_build_collectors_uses_local_settings_without_collecting() -> None:
    settings = Settings(
        rss_feed_urls="https://feeds.example.test/a.xml,https://feeds.example.test/b.xml",
        sec_user_agent="quant-intel-test contact@example.test",
        sec_cik="0000789019",
        arxiv_search_query="cat:q-fin.CP",
        github_query="topic:backtesting language:Python",
        fred_api_key=SecretStr("fixture-key"),
        fred_series_id="CPIAUCSL",
    )

    collectors = build_collectors(settings, ("rss", "sec_edgar", "arxiv", "github", "fred"))

    assert [collector.source_name for collector in collectors] == [
        "rss_1",
        "rss_2",
        "sec_edgar",
        "arxiv",
        "github",
        "fred",
    ]


@pytest.mark.asyncio
async def test_build_collectors_returns_rss_configuration_failure_without_http() -> None:
    settings = Settings(rss_feed_urls=None)
    collector = build_collectors(settings, ("rss",))[0]

    result = await collector.collect()

    assert result.source_name == "rss"
    assert result.status == CollectorStatus.FAILED
    assert "RSS_FEED_URLS" in (result.message or "")


@pytest.mark.asyncio
async def test_collect_once_persists_success_and_failure_statuses() -> None:
    engine = create_db_engine("sqlite://")
    init_db(engine)
    collectors = [
        FakeCollector(
            CollectorRunResult(
                source_name="fixture_success",
                source_type="fixture",
                display_name="Fixture Success",
                status=CollectorStatus.SUCCESS,
                items=[
                    CollectedItem(
                        source_name="fixture_success",
                        source_item_id="item-1",
                        url="https://example.test/item-1",
                        title="Fixture item",
                    )
                ],
            )
        ),
        FakeCollector(
            CollectorRunResult(
                source_name="fixture_failure",
                source_type="fixture",
                display_name="Fixture Failure",
                status=CollectorStatus.FAILED,
                message="Fixture failure.",
            )
        ),
    ]

    with Session(engine) as session:
        result = await collect_once(session, collectors=collectors)
        statuses = session.exec(select(SourceStatus).order_by(SourceStatus.source_name)).all()
        items = session.exec(select(ContentItem)).all()

    assert result.collector_count == 2
    assert result.total_items_seen == 1
    assert result.source_failure_count == 1
    assert [status.source_name for status in statuses] == ["fixture_failure", "fixture_success"]
    assert [status.status for status in statuses] == [
        CollectorStatus.FAILED.value,
        CollectorStatus.SUCCESS.value,
    ]
    assert [item.source_item_id for item in items] == ["item-1"]


@pytest.mark.asyncio
async def test_collect_once_records_collector_exceptions_as_failures() -> None:
    engine = create_db_engine("sqlite://")
    init_db(engine)

    with Session(engine) as session:
        result = await collect_once(session, collectors=[ExplodingCollector()])
        statuses = session.exec(select(SourceStatus)).all()

    assert result.collector_count == 1
    assert result.source_failure_count == 1
    assert statuses[0].source_name == "exploding"
    assert statuses[0].status == CollectorStatus.FAILED.value
    assert "Collector raised RuntimeError" in (statuses[0].message or "")


class FakeCollector(SourceCollector):
    def __init__(self, result: CollectorRunResult) -> None:
        super().__init__(
            source_name=result.source_name,
            source_type=result.source_type,
            display_name=result.display_name,
        )
        self.result = result

    async def collect(self) -> CollectorRunResult:
        return self.result


class ExplodingCollector(SourceCollector):
    def __init__(self) -> None:
        super().__init__(
            source_name="exploding",
            source_type="fixture",
            display_name="Exploding Fixture",
        )

    async def collect(self) -> CollectorRunResult:
        raise RuntimeError("boom")
