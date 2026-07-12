"""Independent Finance News MCP collector over Streamable HTTP."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup  # type: ignore[import-untyped]
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, TextContent

from app.collectors.base import (
    CollectedItem,
    CollectorConfig,
    CollectorRunResult,
    CollectorStatus,
    SourceCollector,
    canonicalize_url_for_storage,
    compact_text_for_storage,
    hash_text,
    parse_datetime_utc,
)
from app.core.timezones import UTC, ensure_utc, utc_now

FINANCE_NEWS_MCP_SOURCES = (
    "bloomberg",
    "wsj",
    "cnbc",
    "marketwatch",
    "ft",
    "seekingalpha",
)
SOURCE_DISPLAY_NAMES = {
    "bloomberg": "Bloomberg",
    "wsj": "WSJ",
    "cnbc": "CNBC",
    "marketwatch": "MarketWatch",
    "ft": "Financial Times",
    "seekingalpha": "Seeking Alpha",
}


class FinanceNewsMcpClient(Protocol):
    """Client operation required by the source-specific MCP collector."""

    async def get_latest_news(self, *, source: str, limit: int) -> list[dict[str, Any]]:
        """Return one source's latest public finance-news metadata."""


class StreamableHttpFinanceNewsMcpClient:
    """Official MCP SDK client for an independently running HTTP server."""

    def __init__(self, endpoint_url: str, *, timeout_seconds: float = 30) -> None:
        self.endpoint_url = endpoint_url
        self.timeout_seconds = timeout_seconds
        self._unavailable_reason: str | None = None

    async def get_latest_news(self, *, source: str, limit: int) -> list[dict[str, Any]]:
        if self._unavailable_reason is not None:
            raise RuntimeError(
                f"MCP endpoint was unavailable earlier in this run ({self._unavailable_reason})."
            )
        timeout = max(1.0, self.timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as http_client:
                async with streamable_http_client(
                    self.endpoint_url,
                    http_client=http_client,
                ) as (read_stream, write_stream, _):
                    async with ClientSession(
                        read_stream,
                        write_stream,
                        read_timeout_seconds=timedelta(seconds=timeout),
                    ) as session:
                        await session.initialize()
                        result = await session.call_tool(
                            "get_latest_finance_news",
                            {"limit": limit, "source": source},
                            read_timeout_seconds=timedelta(seconds=timeout),
                        )
            return _articles_from_tool_result(result)
        except Exception as exc:
            self._unavailable_reason = type(exc).__name__
            raise


class FinanceNewsMcpCollector(SourceCollector):
    """Collect one publisher from the independent Finance News MCP server."""

    def __init__(
        self,
        *,
        endpoint_url: str | None,
        publisher_source: str,
        config: CollectorConfig | None = None,
        client: FinanceNewsMcpClient | None = None,
    ) -> None:
        if publisher_source not in FINANCE_NEWS_MCP_SOURCES:
            raise ValueError(f"Unsupported Finance News MCP source: {publisher_source}")
        display_name = SOURCE_DISPLAY_NAMES[publisher_source]
        super().__init__(
            source_name=f"finance_news_mcp_{publisher_source}",
            source_type="mcp_rss",
            display_name=f"{display_name} via Finance News MCP",
            config=config,
        )
        self.endpoint_url = (endpoint_url or "").strip()
        self.publisher_source = publisher_source
        self.client = client

    async def collect(self) -> CollectorRunResult:
        fetched_at = utc_now()
        if not _is_http_url(self.endpoint_url):
            return self._result(
                CollectorStatus.FAILED,
                "FINANCE_NEWS_MCP_URL must be an HTTP(S) MCP endpoint.",
                fetched_at,
            )

        client = self.client or StreamableHttpFinanceNewsMcpClient(
            self.endpoint_url,
            timeout_seconds=self.config.timeout_seconds,
        )
        try:
            articles = await client.get_latest_news(
                source=self.publisher_source,
                limit=max(1, self.config.max_items),
            )
        except Exception as exc:
            return self._result(
                CollectorStatus.FAILED,
                f"Finance News MCP request failed ({type(exc).__name__}).",
                fetched_at,
            )

        error = next(
            (
                compact_text_for_storage(article.get("error"))
                for article in articles
                if article.get("error")
            ),
            None,
        )
        if error:
            return self._result(CollectorStatus.FAILED, error, fetched_at)

        items = [
            item
            for article in articles[: self.config.max_items]
            if (item := self._article_to_item(article, fetched_at)) is not None
        ]
        items.sort(
            key=lambda item: ensure_utc(item.published_at)
            if item.published_at is not None
            else datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        status = CollectorStatus.SUCCESS if items else CollectorStatus.EMPTY
        return self._result(
            status,
            f"Parsed {len(items)} {self.display_name} item(s).",
            fetched_at,
            items=items,
        )

    def _article_to_item(
        self,
        article: dict[str, Any],
        fetched_at: datetime,
    ) -> CollectedItem | None:
        url = compact_text_for_storage(article.get("link"), max_chars=2000)
        title = _plain_text(article.get("title"), max_chars=500)
        if not url or not title:
            return None

        canonical_url = canonicalize_url_for_storage(url)
        summary = _plain_text(article.get("description"), max_chars=500)
        source_item_id = hash_text(canonical_url)
        published_at = parse_datetime_utc(article.get("published_date"))
        return CollectedItem(
            source_name=self.source_name,
            source_item_id=source_item_id,
            url=url,
            canonical_url=canonical_url,
            title=title,
            summary=summary,
            excerpt=summary,
            publisher=SOURCE_DISPLAY_NAMES[self.publisher_source],
            published_at=published_at,
            fetched_at=fetched_at,
            raw_payload_hash=hash_text("|".join([source_item_id, title, summary or ""])),
            raw_metadata={
                "mcp_tool": "get_latest_finance_news",
                "publisher_source": self.publisher_source,
            },
        )

    def _result(
        self,
        status: CollectorStatus,
        message: str,
        fetched_at: datetime,
        *,
        items: list[CollectedItem] | None = None,
    ) -> CollectorRunResult:
        return CollectorRunResult(
            source_name=self.source_name,
            source_type=self.source_type,
            display_name=self.display_name,
            status=status,
            message=message,
            source_url=self.endpoint_url or None,
            fetched_at=fetched_at,
            items=items or [],
        )


def _articles_from_tool_result(result: CallToolResult) -> list[dict[str, Any]]:
    if result.isError:
        raise ValueError("Finance News MCP tool returned an error result.")

    structured = _article_list(result.structuredContent)
    if structured is not None:
        return structured

    for block in result.content:
        if not isinstance(block, TextContent):
            continue
        try:
            decoded = json.loads(block.text)
        except json.JSONDecodeError:
            continue
        articles = _article_list(decoded)
        if articles is not None:
            return articles
    raise ValueError("Finance News MCP tool returned no article list.")


def _article_list(value: Any) -> list[dict[str, Any]] | None:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if not isinstance(value, dict):
        return None
    for key in ("result", "articles", "items"):
        nested = value.get(key)
        if isinstance(nested, list):
            return [item for item in nested if isinstance(item, dict)]
    return None


def _plain_text(value: Any, *, max_chars: int) -> str | None:
    if value is None:
        return None
    text = BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)
    return compact_text_for_storage(text, max_chars=max_chars)


def _is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return (
        parsed.scheme in {"http", "https"}
        and bool(parsed.netloc)
        and parsed.username is None
        and parsed.password is None
    )


__all__ = [
    "FINANCE_NEWS_MCP_SOURCES",
    "FinanceNewsMcpClient",
    "FinanceNewsMcpCollector",
    "StreamableHttpFinanceNewsMcpClient",
]
