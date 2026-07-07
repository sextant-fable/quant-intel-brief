"""Deterministic event clustering baseline."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import NamedTuple

from app.db.models import Cluster, ContentItem, EventItem
from app.dedup.canonicalize import canonicalize_url, source_payload_hash

STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "as",
        "for",
        "from",
        "in",
        "into",
        "of",
        "on",
        "the",
        "to",
        "with",
    }
)
TOKEN_RE = re.compile(r"[a-z0-9]+")


class ClusterResult(NamedTuple):
    """Clusters plus event-item relationships."""

    clusters: list[Cluster]
    event_items: list[EventItem]


@dataclass(slots=True)
class _ClusterState:
    cluster: Cluster
    title_tokens: frozenset[str]
    canonical_urls: set[str]
    source_names: set[str]


def cluster_items(
    items: list[ContentItem],
    title_similarity_threshold: float = 0.6,
) -> ClusterResult:
    """Cluster content items into deterministic event groups."""
    states: list[_ClusterState] = []
    sorted_items = sorted(items, key=lambda item: (item.published_at or item.fetched_at, item.id))

    for item in sorted_items:
        canonical_url = _item_canonical_url(item)
        tokens = _title_tokens(item.title)
        state = _find_matching_state(states, canonical_url, tokens, title_similarity_threshold)
        if state is None:
            state = _new_state(item, canonical_url, tokens)
            states.append(state)
        _append_item_to_state(state, item, canonical_url)

    clusters = [_finalize_cluster(state) for state in states]
    links = [
        EventItem(
            cluster_id=cluster.id,
            item_id=item_id,
            source_name=_source_for_item(items, item_id),
            confidence=1.0,
            provenance="dedup:canonical_url_or_title",
        )
        for cluster in clusters
        for item_id in cluster.item_ids
    ]
    return ClusterResult(clusters=clusters, event_items=links)


def _find_matching_state(
    states: list[_ClusterState],
    canonical_url: str,
    title_tokens: frozenset[str],
    threshold: float,
) -> _ClusterState | None:
    for state in states:
        if canonical_url in state.canonical_urls:
            return state
        if _jaccard(state.title_tokens, title_tokens) >= threshold:
            return state
    return None


def _new_state(
    item: ContentItem,
    canonical_url: str,
    title_tokens: frozenset[str],
) -> _ClusterState:
    cluster = Cluster(
        canonical_title=item.title,
        canonical_url=canonical_url,
        event_fingerprint=_event_fingerprint(canonical_url, title_tokens),
        item_ids=[],
        source_names=[],
        tickers=list(item.tickers),
        assets=list(item.assets),
        quant_topics=list(item.quant_topics),
    )
    return _ClusterState(
        cluster=cluster,
        title_tokens=title_tokens,
        canonical_urls=set(),
        source_names=set(),
    )


def _append_item_to_state(state: _ClusterState, item: ContentItem, canonical_url: str) -> None:
    if item.id not in state.cluster.item_ids:
        state.cluster.item_ids.append(item.id)
    state.canonical_urls.add(canonical_url)
    state.source_names.add(item.source_name)
    state.cluster.tickers = sorted(set(state.cluster.tickers) | set(item.tickers))
    state.cluster.assets = sorted(set(state.cluster.assets) | set(item.assets))
    state.cluster.quant_topics = sorted(set(state.cluster.quant_topics) | set(item.quant_topics))


def _finalize_cluster(state: _ClusterState) -> Cluster:
    state.cluster.item_ids = sorted(state.cluster.item_ids)
    state.cluster.source_names = sorted(state.source_names)
    return state.cluster


def _item_canonical_url(item: ContentItem) -> str:
    return item.canonical_url or canonicalize_url(item.url)


def _title_tokens(title: str) -> frozenset[str]:
    tokens = {token for token in TOKEN_RE.findall(title.lower()) if token not in STOPWORDS}
    return frozenset(tokens)


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _event_fingerprint(canonical_url: str, title_tokens: frozenset[str]) -> str:
    return source_payload_hash(canonical_url, " ".join(sorted(title_tokens)))


def _source_for_item(items: list[ContentItem], item_id: str) -> str:
    for item in items:
        if item.id == item_id:
            return item.source_name
    return "unknown"


__all__ = ["ClusterResult", "cluster_items"]
