"""Deterministic prefiltering before event ranking."""

from __future__ import annotations

from app.db.models import Cluster

LOW_VALUE_TITLE_TERMS = frozenset({"giveaway", "meme", "spam", "test post"})


def prefilter_clusters(clusters: list[Cluster]) -> list[Cluster]:
    """Remove obvious low-value clusters before scoring."""
    return [cluster for cluster in clusters if should_keep_cluster(cluster)]


def should_keep_cluster(cluster: Cluster) -> bool:
    """Return whether a cluster should enter deterministic ranking."""
    title = cluster.canonical_title.strip().lower()
    if not cluster.item_ids or len(title) < 5:
        return False
    if any(term in title for term in LOW_VALUE_TITLE_TERMS):
        return False
    return True


__all__ = ["prefilter_clusters", "should_keep_cluster"]
