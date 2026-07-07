"""Phase 4 normalization, extraction-boundary, and storage hygiene tests."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlmodel import Session, select

from app.collectors.base import (
    CollectedItem,
    CollectorRunResult,
    CollectorStatus,
    parse_datetime_utc,
    persist_collector_result,
)
from app.core.timezones import UTC, ensure_utc
from app.db.models import ContentItem, RawItem
from app.db.session import create_db_engine, init_db
from app.dedup.canonicalize import build_source_reference, canonicalize_url
from app.extractors.article_extractor import (
    ArticleExtractionPolicy,
    ExtractionNotPermittedError,
    extract_article_metadata,
)


def test_canonical_url_variants_are_deterministic() -> None:
    first = canonicalize_url(
        "HTTPS://Example.COM:443/research/item/?utm_source=news&b=2&a=1#comments"
    )
    second = canonicalize_url("https://example.com/research/item?b=2&a=1")
    third = canonicalize_url("http://Example.com:80/research/item/?ref=feed&a=1&b=2")

    assert first == "https://example.com/research/item?a=1&b=2"
    assert second == first
    assert third == "http://example.com/research/item?a=1&b=2"


def test_excerpt_extraction_sanitizes_html_and_limits_length() -> None:
    extracted = extract_article_metadata(
        "https://example.test/article?utm_campaign=drop",
        html="""
        <html>
          <head><script>alert("drop")</script></head>
          <body><h1>Ignored headline</h1><p>Alpha   beta gamma delta epsilon zeta.</p></body>
        </html>
        """,
        title="  Example   Article  ",
        policy=ArticleExtractionPolicy(allow_excerpt=True, max_excerpt_chars=32),
    )

    assert extracted.canonical_url == "https://example.test/article"
    assert extracted.title == "Example Article"
    assert extracted.excerpt == "Ignored headline Alpha beta..."
    assert "alert" not in (extracted.excerpt or "")


def test_extraction_noops_without_excerpt_permission_and_refuses_full_text_storage() -> None:
    no_text = extract_article_metadata(
        "https://example.test/article",
        text="This compact text should not be extracted unless explicitly permitted.",
    )

    assert no_text.excerpt is None

    with pytest.raises(ExtractionNotPermittedError):
        extract_article_metadata(
            "https://example.test/article",
            text="Full body",
            policy=ArticleExtractionPolicy(store_full_text=True),
        )


def test_source_reference_hashes_without_storing_payload() -> None:
    reference = build_source_reference(
        "https://example.test/item?utm_source=drop",
        "source-id",
        "title",
    )

    assert reference.url == "https://example.test/item?utm_source=drop"
    assert reference.canonical_url == "https://example.test/item"
    assert len(reference.payload_hash) == 64
    assert "title" not in reference.payload_hash


def test_source_reference_and_retention_are_persisted_with_metadata_only_policy() -> None:
    engine = create_db_engine("sqlite://")
    init_db(engine)
    fetched_at = datetime(2026, 7, 7, 12, 0, 0)
    item = CollectedItem(
        source_name="phase4_fixture",
        source_item_id="fixture-1",
        url="https://example.test/item?utm_source=drop&b=2&a=1#frag",
        title="Fixture normalization item",
        excerpt="Compact excerpt only.",
        fetched_at=fetched_at,
    )
    result = CollectorRunResult(
        source_name="phase4_fixture",
        source_type="fixture",
        display_name="Phase 4 Fixture",
        status=CollectorStatus.SUCCESS,
        items=[item],
    )

    with Session(engine) as session:
        persist_collector_result(session, result)
        raw_item = session.exec(select(RawItem)).one()
        content_item = session.exec(select(ContentItem)).one()

    assert raw_item.canonical_url == "https://example.test/item?a=1&b=2"
    assert content_item.canonical_url == raw_item.canonical_url
    assert raw_item.storage_policy == "metadata_only"
    assert content_item.storage_policy == "metadata_only"
    assert raw_item.retain_for_days == 30
    assert content_item.retain_for_days == 30
    assert raw_item.retention_until is not None
    assert content_item.retention_until is not None
    assert ensure_utc(raw_item.retention_until) == ensure_utc(fetched_at) + timedelta(days=30)
    assert ensure_utc(content_item.retention_until) == ensure_utc(raw_item.retention_until)
    assert raw_item.source_reference["canonical_url"] == raw_item.canonical_url
    assert len(raw_item.source_reference["payload_hash"]) == 64
    assert "Compact excerpt only." not in raw_item.source_reference["payload_hash"]
    assert not hasattr(content_item, "content_text")


def test_source_timestamp_parsing_normalizes_to_utc() -> None:
    parsed = parse_datetime_utc("2026-07-07T09:30:00-04:00")

    assert parsed is not None
    assert parsed.tzinfo is UTC
    assert parsed.hour == 13
