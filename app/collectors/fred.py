"""FRED macro series metadata collector."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

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
from app.core.timezones import utc_now


class FredCollector(SourceCollector):
    """Collect FRED macro observation metadata."""

    endpoint = "https://api.stlouisfed.org/fred/series/observations"

    def __init__(
        self,
        api_key: str | None = None,
        series_id: str = "FEDFUNDS",
        config: CollectorConfig | None = None,
        endpoint: str | None = None,
    ) -> None:
        super().__init__(
            source_name="fred",
            source_type="macro_api",
            display_name="FRED",
            config=config,
        )
        self.api_key = api_key
        self.series_id = series_id
        self.endpoint = endpoint or self.endpoint

    async def collect(self, client: httpx.AsyncClient | None = None) -> CollectorRunResult:
        fetched_at = utc_now()
        if not self.api_key:
            return self._result(CollectorStatus.FAILED, "FRED_API_KEY is required.", fetched_at)

        fetch = await self.fetch_json(
            self.endpoint,
            params={
                "series_id": self.series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "limit": self.config.max_items,
                "sort_order": "desc",
            },
            client=client,
        )
        if fetch.status != CollectorStatus.SUCCESS:
            return self._result(fetch.status, fetch.message or "FRED request failed.", fetched_at)

        data = fetch.data if isinstance(fetch.data, dict) else {}
        if "error_code" in data:
            return self._result(CollectorStatus.FAILED, str(data.get("error_message")), fetched_at)

        observations_value = data.get("observations")
        observations = observations_value if isinstance(observations_value, list) else []
        items = [
            item
            for observation in observations
            if (item := self._observation_to_item(observation, fetched_at))
        ]
        status = CollectorStatus.SUCCESS if items else CollectorStatus.EMPTY
        return self._result(status, f"Parsed {len(items)} FRED observation(s).", fetched_at, items)

    def _observation_to_item(
        self,
        observation: Any,
        fetched_at: datetime,
    ) -> CollectedItem | None:
        if not isinstance(observation, dict):
            return None
        date_value = compact_text_for_storage(observation.get("date"))
        value = compact_text_for_storage(observation.get("value"))
        if not date_value or value is None:
            return None

        url = f"https://fred.stlouisfed.org/series/{self.series_id}"
        canonical_url = canonicalize_url_for_storage(url)
        source_item_id = f"{self.series_id}:{date_value}"
        title = f"FRED {self.series_id} observation for {date_value}"
        summary = f"Value: {value}"
        return CollectedItem(
            source_name=self.source_name,
            source_item_id=source_item_id,
            url=url,
            canonical_url=canonical_url,
            title=title,
            summary=summary,
            excerpt=summary,
            publisher="Federal Reserve Bank of St. Louis",
            published_at=parse_datetime_utc(date_value),
            fetched_at=fetched_at,
            raw_payload_hash=hash_text("|".join([source_item_id, value])),
            raw_metadata={
                "series_id": self.series_id,
                "realtime_start": observation.get("realtime_start"),
                "realtime_end": observation.get("realtime_end"),
            },
        )

    def _result(
        self,
        status: CollectorStatus,
        message: str,
        fetched_at: datetime,
        items: list[CollectedItem] | None = None,
    ) -> CollectorRunResult:
        return CollectorRunResult(
            source_name=self.source_name,
            source_type=self.source_type,
            display_name=self.display_name,
            status=status,
            message=message,
            source_url=self.endpoint,
            fetched_at=fetched_at,
            items=items or [],
        )


__all__ = ["FredCollector"]
