"""User-authorized premium metadata collector."""

from __future__ import annotations

from datetime import datetime
from typing import Any

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
from app.extractors.premium_extractor import PremiumExtractionError, PremiumMetadataExtractor


class PremiumBrowserCollector(SourceCollector):
    """Accept explicitly authorized premium metadata without browser automation."""

    def __init__(
        self,
        enabled: bool = False,
        authorized: bool = False,
        metadata_records: list[dict[str, Any]] | None = None,
        config: CollectorConfig | None = None,
        extractor: PremiumMetadataExtractor | None = None,
    ) -> None:
        super().__init__(
            source_name="premium_browser",
            source_type="premium_metadata",
            display_name="Premium Metadata",
            config=config,
        )
        self.enabled = enabled
        self.authorized = authorized
        self.metadata_records = metadata_records or []
        self.extractor = extractor or PremiumMetadataExtractor()

    async def collect(self) -> CollectorRunResult:
        fetched_at = utc_now()
        if not self.enabled:
            return self._result(
                CollectorStatus.FAILED,
                "Premium metadata collection is disabled.",
                fetched_at,
            )
        if not self.authorized:
            return self._result(
                CollectorStatus.FAILED,
                "Premium metadata collection requires explicit user authorization.",
                fetched_at,
            )

        items: list[CollectedItem] = []
        try:
            for record in self.metadata_records[: self.config.max_items]:
                metadata = self.extractor.extract_metadata(record)
                item = self._metadata_to_item(metadata, fetched_at)
                if item is not None:
                    items.append(item)
        except PremiumExtractionError as exc:
            return self._result(CollectorStatus.FAILED, str(exc), fetched_at)

        status = CollectorStatus.SUCCESS if items else CollectorStatus.EMPTY
        return self._result(
            status,
            f"Parsed {len(items)} premium metadata item(s).",
            fetched_at,
            items,
        )

    def _metadata_to_item(
        self,
        metadata: dict[str, Any],
        fetched_at: datetime,
    ) -> CollectedItem | None:
        url = compact_text_for_storage(metadata.get("url"), max_chars=2000)
        title = compact_text_for_storage(metadata.get("title"))
        if not url or not title:
            return None

        canonical_url = compact_text_for_storage(
            metadata.get("canonical_url"),
            max_chars=2000,
        ) or canonicalize_url_for_storage(url)
        source_item_id = compact_text_for_storage(metadata.get("source_item_id")) or hash_text(
            canonical_url
        )
        summary = compact_text_for_storage(metadata.get("summary"))
        excerpt = compact_text_for_storage(metadata.get("excerpt")) or summary
        return CollectedItem(
            source_name=self.source_name,
            source_item_id=source_item_id,
            url=url,
            canonical_url=canonical_url,
            title=title,
            summary=summary,
            excerpt=excerpt,
            author=compact_text_for_storage(metadata.get("author")),
            publisher=compact_text_for_storage(metadata.get("publisher")),
            published_at=parse_datetime_utc(metadata.get("published_at")),
            fetched_at=fetched_at,
            raw_payload_hash=hash_text("|".join([source_item_id, title, excerpt or ""])),
            raw_metadata={
                "source_name": metadata.get("source_name"),
                "tags": metadata.get("tags") if isinstance(metadata.get("tags"), list) else [],
                "user_authorized": True,
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
            source_url=None,
            fetched_at=fetched_at,
            items=items or [],
        )


__all__ = ["PremiumBrowserCollector"]
