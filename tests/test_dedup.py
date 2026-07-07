"""Phase 5 deterministic deduplication tests."""

from __future__ import annotations

from datetime import datetime

from app.db.models import ContentItem
from app.dedup.clusterer import cluster_items


def _item(
    item_id: str,
    title: str,
    url: str,
    source_name: str = "fixture",
    canonical_url: str | None = None,
) -> ContentItem:
    return ContentItem(
        id=item_id,
        source_name=source_name,
        source_item_id=item_id,
        url=url,
        canonical_url=canonical_url,
        title=title,
        published_at=datetime(2026, 7, 7, 12, 0, 0),
    )


def test_exact_duplicate_canonical_url_clusters_once() -> None:
    result = cluster_items(
        [
            _item(
                "item-1",
                "ETF options volume rises before rebalance",
                "https://a.test/x?utm_source=drop",
                canonical_url="https://example.test/story",
            ),
            _item(
                "item-2",
                "Different syndication title",
                "https://b.test/y#comments",
                canonical_url="https://example.test/story",
            ),
        ]
    )

    assert len(result.clusters) == 1
    assert result.clusters[0].item_ids == ["item-1", "item-2"]
    assert len(result.event_items) == 2


def test_near_duplicate_titles_cluster_without_same_link() -> None:
    result = cluster_items(
        [
            _item(
                "item-1",
                "ETF options volume rises before rebalance",
                "https://example.test/one",
            ),
            _item(
                "item-2",
                "ETF options volume jumps before rebalance",
                "https://example.test/two",
            ),
        ]
    )

    assert len(result.clusters) == 1
    assert result.clusters[0].event_fingerprint is not None


def test_distinct_events_remain_separate() -> None:
    result = cluster_items(
        [
            _item("macro", "Fed minutes shift rate-cut expectations", "https://example.test/fed"),
            _item("dev", "Open source backtest library ships update", "https://example.test/dev"),
        ]
    )

    assert len(result.clusters) == 2
    assert sorted(cluster.item_ids[0] for cluster in result.clusters) == ["dev", "macro"]
