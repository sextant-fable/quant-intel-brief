"""SQLModel database models for the local intelligence store."""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar
from uuid import uuid4

from sqlalchemy import JSON, UniqueConstraint
from sqlmodel import Column, Field, SQLModel

from app.core.timezones import utc_now


def new_id() -> str:
    """Return a compact stable ID for local records."""
    return uuid4().hex


class TimestampMixin(SQLModel):
    """Timestamp fields shared by local tables."""

    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime | None = Field(default=None, nullable=True)


class Source(TimestampMixin, table=True):
    """Configured upstream source metadata."""

    __tablename__: ClassVar[str] = "sources"
    __table_args__: ClassVar[tuple[UniqueConstraint, ...]] = (
        UniqueConstraint("name", name="uq_sources_name"),
    )

    id: str = Field(default_factory=new_id, primary_key=True)
    name: str = Field(index=True, nullable=False)
    source_type: str = Field(index=True, nullable=False)
    display_name: str
    access_mode: str = "public"
    enabled: bool = True
    terms_url: str | None = None
    terms_checked_at: datetime | None = None


class RawItem(SQLModel, table=True):
    """Source item metadata as fetched, without copyrighted full text."""

    __tablename__: ClassVar[str] = "raw_items"
    __table_args__: ClassVar[tuple[UniqueConstraint, ...]] = (
        UniqueConstraint("source_id", "source_item_id", name="uq_raw_items_source_item"),
    )

    id: str = Field(default_factory=new_id, primary_key=True)
    source_id: str = Field(foreign_key="sources.id", index=True)
    source_item_id: str = Field(index=True)
    url: str
    canonical_url: str | None = Field(default=None, index=True)
    title: str | None = None
    publisher: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    fetched_at: datetime = Field(default_factory=utc_now, nullable=False)
    raw_payload_hash: str | None = Field(default=None, index=True)
    storage_policy: str = Field(default="metadata_only", index=True)
    retain_for_days: int = 30
    retention_until: datetime | None = Field(default=None, index=True)
    source_reference: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    raw_metadata: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class ContentItem(SQLModel, table=True):
    """Normalized item used by later pipeline phases."""

    __tablename__: ClassVar[str] = "content_items"
    __table_args__: ClassVar[tuple[UniqueConstraint, ...]] = (
        UniqueConstraint("source_name", "source_item_id", name="uq_content_items_source_item"),
    )

    id: str = Field(default_factory=new_id, primary_key=True)
    source_id: str | None = Field(default=None, foreign_key="sources.id", index=True)
    raw_item_id: str | None = Field(default=None, foreign_key="raw_items.id", index=True)
    source_name: str = Field(index=True)
    source_item_id: str
    url: str
    canonical_url: str | None = Field(default=None, index=True)
    title: str
    summary: str | None = None
    excerpt: str | None = None
    author: str | None = None
    publisher: str | None = None
    published_at: datetime | None = Field(default=None, index=True)
    fetched_at: datetime = Field(default_factory=utc_now, nullable=False)
    language: str | None = None
    tickers: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    assets: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    quant_topics: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    raw_payload_hash: str | None = Field(default=None, index=True)
    source_terms_checked_at: datetime | None = None
    storage_policy: str = Field(default="metadata_only", index=True)
    retain_for_days: int = 30
    retention_until: datetime | None = Field(default=None, index=True)
    source_reference: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class CollectionRun(SQLModel, table=True):
    """One user- or system-triggered collection batch."""

    __tablename__: ClassVar[str] = "collection_runs"

    id: str = Field(default_factory=new_id, primary_key=True)
    trigger: str = Field(default="manual", index=True)
    requested_sources: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    started_at: datetime = Field(default_factory=utc_now, nullable=False, index=True)
    completed_at: datetime | None = Field(default=None, index=True)
    collector_count: int = 0
    new_item_count: int = 0
    failure_count: int = 0


class CollectionRunItem(SQLModel, table=True):
    """Content item observed during a collection batch."""

    __tablename__: ClassVar[str] = "collection_run_items"
    __table_args__: ClassVar[tuple[UniqueConstraint, ...]] = (
        UniqueConstraint("run_id", "item_id", name="uq_collection_run_items_run_item"),
    )

    id: str = Field(default_factory=new_id, primary_key=True)
    run_id: str = Field(foreign_key="collection_runs.id", index=True)
    item_id: str = Field(foreign_key="content_items.id", index=True)
    source_name: str = Field(index=True)
    linked_at: datetime = Field(default_factory=utc_now, nullable=False)


class EntityTag(SQLModel, table=True):
    """Tag attached to a content item or later event."""

    __tablename__: ClassVar[str] = "entity_tags"

    id: str = Field(default_factory=new_id, primary_key=True)
    item_id: str | None = Field(default=None, foreign_key="content_items.id", index=True)
    entity_type: str = Field(index=True)
    value: str = Field(index=True)
    confidence: float = 1.0
    provenance: str = "rule"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class Cluster(SQLModel, table=True):
    """Deduplicated event placeholder for later phases."""

    __tablename__: ClassVar[str] = "clusters"

    id: str = Field(default_factory=new_id, primary_key=True)
    canonical_title: str
    event_fingerprint: str | None = Field(default=None, index=True)
    canonical_url: str | None = Field(default=None, index=True)
    summary: str | None = None
    item_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    source_names: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    tickers: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    assets: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    quant_topics: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime | None = None


class EventItem(SQLModel, table=True):
    """Relationship between a deduplicated event cluster and content item."""

    __tablename__: ClassVar[str] = "event_items"
    __table_args__: ClassVar[tuple[UniqueConstraint, ...]] = (
        UniqueConstraint("cluster_id", "item_id", name="uq_event_items_cluster_item"),
    )

    id: str = Field(default_factory=new_id, primary_key=True)
    cluster_id: str = Field(foreign_key="clusters.id", index=True)
    item_id: str = Field(foreign_key="content_items.id", index=True)
    source_name: str = Field(index=True)
    relation: str = "member"
    confidence: float = 1.0
    provenance: str = "dedup_rule"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class RankedItem(SQLModel, table=True):
    """Ranking result placeholder for later phases."""

    __tablename__: ClassVar[str] = "ranked_items"

    id: str = Field(default_factory=new_id, primary_key=True)
    cluster_id: str | None = Field(default=None, foreign_key="clusters.id", index=True)
    item_id: str | None = Field(default=None, foreign_key="content_items.id", index=True)
    score: float = Field(default=0.0, index=True)
    score_components: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    explanation: str | None = None
    ranked_at: datetime = Field(default_factory=utc_now, nullable=False)


class Report(SQLModel, table=True):
    """Generated report metadata."""

    __tablename__: ClassVar[str] = "reports"

    id: str = Field(default_factory=new_id, primary_key=True)
    report_date: datetime = Field(index=True)
    title: str
    status: str = Field(default="draft", index=True)
    html_path: str | None = None
    source_coverage_note: str | None = None
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class ReportSection(SQLModel, table=True):
    """Section metadata for a generated report."""

    __tablename__: ClassVar[str] = "report_sections"

    id: str = Field(default_factory=new_id, primary_key=True)
    report_id: str = Field(foreign_key="reports.id", index=True)
    section_key: str = Field(index=True)
    title: str
    position: int = 0
    content: str | None = None
    source_refs: list[str] = Field(default_factory=list, sa_column=Column(JSON))


class ReportEventRecord(SQLModel, table=True):
    """Structured report event used by Top 10 and bilingual dashboard views."""

    __tablename__: ClassVar[str] = "report_event_records"

    id: str = Field(default_factory=new_id, primary_key=True)
    report_id: str = Field(foreign_key="reports.id", index=True)
    section_key: str = Field(index=True)
    position: int = Field(default=0, index=True)
    event_id: str = Field(index=True)
    ranked_item_id: str | None = Field(default=None, index=True)
    score: float = Field(default=0.0, index=True)
    headline: str
    headline_zh: str
    factual_summary: str
    factual_summary_zh: str
    market_relevance: str
    market_relevance_zh: str
    uncertainty: str
    what_to_watch: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    what_to_watch_zh: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    source_credibility: str = Field(default="medium", index=True)
    source_credibility_reason: str
    source_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    source_urls: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    tickers: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    assets: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    quant_topics: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class DeliveryLog(SQLModel, table=True):
    """Email or notification delivery result."""

    __tablename__: ClassVar[str] = "delivery_logs"

    id: str = Field(default_factory=new_id, primary_key=True)
    report_id: str = Field(foreign_key="reports.id", index=True)
    provider: str
    recipient_hash: str | None = None
    status: str = Field(index=True)
    error_message: str | None = None
    delivered_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class SourceStatus(SQLModel, table=True):
    """Last known status for a source adapter."""

    __tablename__: ClassVar[str] = "source_statuses"

    id: str = Field(default_factory=new_id, primary_key=True)
    source_id: str | None = Field(default=None, foreign_key="sources.id", index=True)
    source_name: str = Field(index=True)
    status: str = Field(index=True)
    message: str | None = None
    last_checked_at: datetime = Field(default_factory=utc_now, nullable=False)


class PremiumSourceNote(SQLModel, table=True):
    """User-authored notes for premium-source reading queue items."""

    __tablename__: ClassVar[str] = "premium_source_notes"
    __table_args__: ClassVar[tuple[UniqueConstraint, ...]] = (
        UniqueConstraint("canonical_url", name="uq_premium_source_notes_canonical_url"),
    )

    id: str = Field(default_factory=new_id, primary_key=True)
    content_item_id: str | None = Field(default=None, foreign_key="content_items.id", index=True)
    url: str
    canonical_url: str = Field(index=True)
    title: str
    publisher: str | None = None
    public_summary: str | None = None
    user_note: str | None = None
    tickers: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    importance: int = Field(default=3, ge=1, le=5)
    status: str = Field(default="to_read", index=True)
    storage_policy: str = Field(default="user_notes_only", index=True)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime | None = None


__all__ = [
    "Cluster",
    "CollectionRun",
    "CollectionRunItem",
    "ContentItem",
    "DeliveryLog",
    "EntityTag",
    "EventItem",
    "RankedItem",
    "RawItem",
    "Report",
    "ReportEventRecord",
    "ReportSection",
    "PremiumSourceNote",
    "Source",
    "SourceStatus",
    "new_id",
]
