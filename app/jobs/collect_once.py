"""Manual one-shot source collection command."""

from __future__ import annotations

import argparse
import asyncio
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Protocol

from pydantic import SecretStr
from sqlmodel import Session

from app.collectors.alphavantage import AlphaVantageCollector
from app.collectors.arxiv import ArxivCollector
from app.collectors.base import (
    CollectorConfig,
    CollectorPersistenceSummary,
    CollectorRunResult,
    CollectorStatus,
    SourceCollector,
    persist_collector_result,
)
from app.collectors.finance_news_mcp import (
    FINANCE_NEWS_MCP_SOURCES,
    FinanceNewsMcpCollector,
    StreamableHttpFinanceNewsMcpClient,
)
from app.collectors.finnhub import FinnhubCollector
from app.collectors.fred import FredCollector
from app.collectors.gdelt import GdeltCollector
from app.collectors.github import GitHubCollector
from app.collectors.newsapi import NewsApiCollector
from app.collectors.quantconnect import QuantConnectCollector
from app.collectors.reddit import RedditCollector
from app.collectors.rss import RssCollector
from app.collectors.sec_edgar import SecEdgarCollector
from app.collectors.stackexchange import StackExchangeCollector
from app.collectors.x_api import XApiCollector
from app.collectors.youtube import YouTubeCollector
from app.core.config import Settings, get_settings
from app.core.timezones import utc_now
from app.db.models import CollectionRun
from app.db.session import create_db_engine, init_db

CORE_SOURCES = ("rss", "sec_edgar", "arxiv", "github", "fred")
SUPPORTED_SOURCES = (
    *CORE_SOURCES,
    "finance_news_mcp",
    "newsapi",
    "gdelt",
    "alphavantage",
    "finnhub",
    "reddit",
    "youtube",
    "x_api",
    "stackexchange",
    "quantconnect",
)
DEFAULT_SOURCES = CORE_SOURCES


class CollectorLike(Protocol):
    """Collector shape required by the manual collection runner."""

    source_name: str
    source_type: str
    display_name: str

    async def collect(self) -> CollectorRunResult:
        """Collect one source run."""


@dataclass(frozen=True, slots=True)
class CollectOnceResult:
    """Summary of one manual collect-once run."""

    requested_sources: tuple[str, ...]
    summaries: tuple[CollectorPersistenceSummary, ...]
    run_id: str | None = None
    started_at: datetime | None = None

    @property
    def collector_count(self) -> int:
        return len(self.summaries)

    @property
    def total_items_seen(self) -> int:
        return sum(summary.content_items_seen for summary in self.summaries)

    @property
    def source_failure_count(self) -> int:
        ok_statuses = {CollectorStatus.SUCCESS, CollectorStatus.EMPTY}
        return sum(1 for summary in self.summaries if summary.status not in ok_statuses)


async def collect_once(
    session: Session,
    *,
    settings: Settings | None = None,
    sources: str | Iterable[str] | None = None,
    collectors: Sequence[CollectorLike] | None = None,
    trigger: str = "manual",
) -> CollectOnceResult:
    """Collect configured sources once and persist source statuses/items locally."""
    selected_sources = parse_sources(sources)
    active_collectors = list(collectors) if collectors is not None else build_collectors(
        settings or get_settings(),
        selected_sources,
    )
    requested_sources = (
        tuple(collector.source_name for collector in active_collectors)
        if collectors is not None
        else selected_sources
    )
    summaries: list[CollectorPersistenceSummary] = []
    run = CollectionRun(
        trigger=trigger,
        requested_sources=list(requested_sources),
    )
    session.add(run)
    session.flush()

    for collector in active_collectors:
        try:
            result = await collector.collect()
        except Exception as exc:
            result = _exception_result(collector, exc)
        summaries.append(
            persist_collector_result(session, result, collection_run_id=run.id)
        )

    run.completed_at = utc_now()
    run.collector_count = len(summaries)
    run.new_item_count = sum(summary.content_items_seen for summary in summaries)
    ok_statuses = {CollectorStatus.SUCCESS, CollectorStatus.EMPTY}
    run.failure_count = sum(1 for summary in summaries if summary.status not in ok_statuses)
    session.add(run)
    session.commit()

    return CollectOnceResult(
        requested_sources=requested_sources,
        summaries=tuple(summaries),
        run_id=run.id,
        started_at=run.started_at,
    )


def build_collectors(
    settings: Settings,
    sources: Iterable[str] | None = None,
) -> list[CollectorLike]:
    """Build collector instances for the requested source names."""
    selected_sources = parse_sources(sources)
    config = _collector_config(settings)
    collectors: list[CollectorLike] = []
    for source_name in selected_sources:
        if source_name == "rss":
            collectors.extend(_rss_collectors(settings, config))
        elif source_name == "finance_news_mcp":
            collectors.extend(_finance_news_mcp_collectors(settings, config))
        elif source_name == "sec_edgar":
            collectors.append(
                SecEdgarCollector(
                    user_agent=settings.sec_user_agent,
                    cik=settings.sec_cik,
                    config=config,
                )
            )
        elif source_name == "arxiv":
            collectors.append(
                ArxivCollector(
                    search_query=settings.arxiv_search_query,
                    config=config,
                )
            )
        elif source_name == "github":
            collectors.append(
                GitHubCollector(
                    token=_secret_value(settings.github_token),
                    query=settings.github_query,
                    config=config,
                )
            )
        elif source_name == "fred":
            collectors.append(
                FredCollector(
                    api_key=_secret_value(settings.fred_api_key),
                    series_id=settings.fred_series_id,
                    config=config,
                )
            )
        elif source_name == "newsapi":
            collectors.append(
                NewsApiCollector(
                    api_key=_secret_value(settings.newsapi_key),
                    query=settings.newsapi_query,
                    config=config,
                )
            )
        elif source_name == "gdelt":
            collectors.append(GdeltCollector(query=settings.gdelt_query, config=config))
        elif source_name == "alphavantage":
            collectors.append(
                AlphaVantageCollector(
                    api_key=_secret_value(settings.alphavantage_api_key),
                    topics=settings.alphavantage_topics,
                    config=config,
                )
            )
        elif source_name == "finnhub":
            collectors.append(
                FinnhubCollector(
                    api_key=_secret_value(settings.finnhub_api_key),
                    category=settings.finnhub_category,
                    config=config,
                )
            )
        elif source_name == "reddit":
            collectors.append(
                RedditCollector(
                    access_token=_secret_value(settings.reddit_access_token),
                    user_agent=settings.reddit_user_agent,
                    query=settings.reddit_query,
                    subreddit=settings.reddit_subreddit,
                    config=config,
                )
            )
        elif source_name == "youtube":
            collectors.append(
                YouTubeCollector(
                    api_key=_secret_value(settings.youtube_api_key),
                    query=settings.youtube_query,
                    config=config,
                )
            )
        elif source_name == "x_api":
            collectors.append(
                XApiCollector(
                    bearer_token=_secret_value(settings.x_bearer_token),
                    query=settings.x_query,
                    config=config,
                )
            )
        elif source_name == "stackexchange":
            collectors.append(
                StackExchangeCollector(
                    enabled=True,
                    api_key=_secret_value(settings.stackexchange_key),
                    query=settings.stackexchange_query,
                    site=settings.stackexchange_site,
                    config=config,
                )
            )
        elif source_name == "quantconnect":
            collectors.append(
                QuantConnectCollector(
                    user_id=_secret_value(settings.quantconnect_user_id),
                    api_token=_secret_value(settings.quantconnect_token),
                    organization_id=settings.quantconnect_organization_id,
                    config=config,
                )
            )
        else:
            raise ValueError(f"Unsupported source: {source_name}")
    return collectors


def parse_sources(sources: str | Iterable[str] | None) -> tuple[str, ...]:
    """Normalize source names from CLI/env-style input."""
    if sources is None:
        return DEFAULT_SOURCES
    if isinstance(sources, str):
        source_names = _split_list_setting(sources)
    else:
        source_names = tuple(name.strip() for name in sources if name.strip())

    if not source_names:
        return DEFAULT_SOURCES

    unsupported = tuple(name for name in source_names if name not in SUPPORTED_SOURCES)
    if unsupported:
        supported = ", ".join(SUPPORTED_SOURCES)
        invalid = ", ".join(unsupported)
        raise ValueError(f"Unsupported source(s): {invalid}. Supported: {supported}.")

    return source_names


def main(argv: Sequence[str] | None = None) -> int:
    """Run manual one-shot collection from the command line."""
    parser = argparse.ArgumentParser(description="Collect configured sources once.")
    parser.add_argument(
        "--sources",
        default=",".join(DEFAULT_SOURCES),
        help="Comma-separated source names. Supported: "
        f"{', '.join(SUPPORTED_SOURCES)}.",
    )
    args = parser.parse_args(argv)

    try:
        sources = parse_sources(args.sources)
    except ValueError as exc:
        parser.error(str(exc))

    settings = get_settings()
    engine = create_db_engine(settings.database_url)
    init_db(engine)
    with Session(engine) as session:
        result = asyncio.run(collect_once(session, settings=settings, sources=sources))

    print(  # noqa: T201
        "Manual collect once complete: "
        f"{result.collector_count} collector run(s), "
        f"{result.total_items_seen} new content item(s), "
        f"{result.source_failure_count} source failure(s)."
    )
    for summary in result.summaries:
        print(  # noqa: T201
            f"- {summary.source_name}: {summary.status.value}; "
            f"new items={summary.content_items_seen}; "
            f"skipped duplicates={summary.skipped_duplicates}"
        )
    return 0


def _collector_config(settings: Settings) -> CollectorConfig:
    return CollectorConfig(
        timeout_seconds=settings.collector_timeout_seconds,
        retry_attempts=settings.http_retry_attempts,
        retry_backoff_seconds=settings.http_retry_backoff_seconds,
        max_items=settings.max_items_per_source,
    )


def _rss_collectors(settings: Settings, config: CollectorConfig) -> list[CollectorLike]:
    feed_urls = _split_list_setting(settings.rss_feed_urls)
    if not feed_urls:
        return [
            StaticResultCollector(
                source_name="rss",
                source_type="rss",
                display_name="RSS Feed",
                status=CollectorStatus.FAILED,
                message="RSS_FEED_URLS is required for RSS collection.",
            )
        ]

    use_numbered_names = len(feed_urls) > 1
    collectors: list[CollectorLike] = []
    for index, feed_url in enumerate(feed_urls, start=1):
        collectors.append(
            RssCollector(
                feed_url=feed_url,
                source_name=f"rss_{index}" if use_numbered_names else "rss",
                display_name=f"RSS Feed {index}" if use_numbered_names else "RSS Feed",
                config=config,
            )
        )
    return collectors


def _finance_news_mcp_collectors(
    settings: Settings,
    config: CollectorConfig,
) -> list[CollectorLike]:
    publisher_sources = _split_list_setting(settings.finance_news_mcp_sources)
    invalid_sources = [
        source for source in publisher_sources if source not in FINANCE_NEWS_MCP_SOURCES
    ]
    if invalid_sources:
        return [
            StaticResultCollector(
                source_name="finance_news_mcp",
                source_type="mcp_rss",
                display_name="Finance News MCP",
                status=CollectorStatus.FAILED,
                message=f"Unsupported MCP publisher source(s): {', '.join(invalid_sources)}.",
            )
        ]

    active_sources = publisher_sources or FINANCE_NEWS_MCP_SOURCES
    mcp_config = replace(
        config,
        max_items=min(max(1, settings.finance_news_mcp_items_per_source), 100),
    )
    shared_client = StreamableHttpFinanceNewsMcpClient(
        settings.finance_news_mcp_url or "",
        timeout_seconds=mcp_config.timeout_seconds,
    )
    return [
        FinanceNewsMcpCollector(
            endpoint_url=settings.finance_news_mcp_url,
            publisher_source=publisher_source,
            config=mcp_config,
            client=shared_client,
        )
        for publisher_source in active_sources
    ]


def _split_list_setting(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(part.strip() for part in re.split(r"[\n,]+", value) if part.strip())


def _secret_value(value: SecretStr | None) -> str | None:
    return value.get_secret_value() if value else None


def _exception_result(collector: CollectorLike, exc: Exception) -> CollectorRunResult:
    return CollectorRunResult(
        source_name=collector.source_name,
        source_type=collector.source_type,
        display_name=collector.display_name,
        status=CollectorStatus.FAILED,
        message=f"Collector raised {type(exc).__name__}: {exc}",
        fetched_at=utc_now(),
    )


class StaticResultCollector(SourceCollector):
    """Collector that returns a preconfigured status without network access."""

    def __init__(
        self,
        *,
        source_name: str,
        source_type: str,
        display_name: str,
        status: CollectorStatus,
        message: str,
    ) -> None:
        super().__init__(
            source_name=source_name,
            source_type=source_type,
            display_name=display_name,
        )
        self._status = status
        self._message = message

    async def collect(self) -> CollectorRunResult:
        return CollectorRunResult(
            source_name=self.source_name,
            source_type=self.source_type,
            display_name=self.display_name,
            status=self._status,
            message=self._message,
            fetched_at=utc_now(),
        )


__all__ = [
    "CollectOnceResult",
    "CollectorLike",
    "CORE_SOURCES",
    "DEFAULT_SOURCES",
    "SUPPORTED_SOURCES",
    "StaticResultCollector",
    "build_collectors",
    "collect_once",
    "main",
    "parse_sources",
]


if __name__ == "__main__":
    raise SystemExit(main())
