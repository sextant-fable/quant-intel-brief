"""Freshness and diversity policy for the daily briefing candidate pool."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.timezones import ensure_utc, utc_now
from app.db.models import Cluster, ContentItem, RankedItem
from app.reports.sections import SECTION_KEYS, section_key_for_cluster

NEWS_SOURCES = frozenset({"alphavantage", "finnhub", "gdelt", "newsapi"})
COMMUNITY_SOURCES = frozenset({"reddit", "stackexchange", "x_api", "youtube"})
SEC_SOURCES = frozenset({"sec_edgar"})
ARXIV_SOURCES = frozenset({"arxiv"})
LONG_RESEARCH_SOURCES = frozenset({"fred", "github", "quantconnect"})


@dataclass(frozen=True, slots=True)
class BriefSelectionPolicy:
    """Deterministic limits for a pre-market briefing run."""

    items_per_source: int = 20
    news_window_hours: int = 72
    community_window_hours: int = 72
    sec_window_days: int = 30
    arxiv_window_days: int = 30
    research_window_days: int = 14
    default_window_days: int = 7
    top_source_limit: int = 2
    top_section_limit: int = 3


@dataclass(frozen=True, slots=True)
class SelectedRankedEvent:
    """A ranked event plus its deterministic report section."""

    ranked_item: RankedItem
    section_key: str


def select_daily_candidates(
    items: Iterable[ContentItem],
    *,
    limit: int,
    now: datetime | None = None,
    policy: BriefSelectionPolicy | None = None,
) -> list[ContentItem]:
    """Select a fresh, per-source-balanced pool using publication timestamps only."""
    if limit <= 0:
        return []

    active_policy = policy or BriefSelectionPolicy()
    active_now = ensure_utc(now or utc_now())
    buckets: dict[str, list[ContentItem]] = defaultdict(list)

    for item in items:
        if not _is_daily_eligible(item, now=active_now, policy=active_policy):
            continue
        buckets[item.source_name].append(item)

    for source_items in buckets.values():
        source_items.sort(key=_published_sort_key, reverse=True)
        del source_items[max(1, active_policy.items_per_source) :]

    ordered_sources = sorted(
        buckets,
        key=lambda source: (
            -_published_sort_key(buckets[source][0])[0],
            source,
        ),
    )
    selected: list[ContentItem] = []
    max_bucket_size = max((len(bucket) for bucket in buckets.values()), default=0)
    for index in range(max_bucket_size):
        for source in ordered_sources:
            bucket = buckets[source]
            if index < len(bucket):
                selected.append(bucket[index])
                if len(selected) >= limit:
                    return selected
    return selected


def cluster_publication_times(
    clusters: Iterable[Cluster],
    items: Iterable[ContentItem],
) -> dict[str, datetime]:
    """Return the newest real publication timestamp represented by each cluster."""
    item_by_id = {item.id: item for item in items}
    publication_times: dict[str, datetime] = {}
    for cluster in clusters:
        values = [
            ensure_utc(item.published_at)
            for item_id in cluster.item_ids
            if (item := item_by_id.get(item_id)) is not None and item.published_at is not None
        ]
        if values:
            publication_times[cluster.id] = max(values)
    return publication_times


def select_diverse_top_events(
    ranked_items: Iterable[RankedItem],
    clusters: Mapping[str, Cluster],
    *,
    limit: int = 10,
    policy: BriefSelectionPolicy | None = None,
) -> list[SelectedRankedEvent]:
    """Select Top events with source, section, and five-lens coverage constraints."""
    if limit <= 0:
        return []

    active_policy = policy or BriefSelectionPolicy()
    candidates = [
        SelectedRankedEvent(
            ranked_item=ranked_item,
            section_key=section_key_for_cluster(cluster),
        )
        for ranked_item in ranked_items
        if ranked_item.cluster_id is not None
        and (cluster := clusters.get(ranked_item.cluster_id)) is not None
    ]
    source_counts: Counter[str] = Counter()
    section_counts: Counter[str] = Counter()
    selected: list[SelectedRankedEvent] = []
    selected_ids: set[str] = set()

    # First pass gives each available market lens one place before filling by score.
    for section_key in SECTION_KEYS:
        candidate = next(
            (
                item
                for item in candidates
                if item.section_key == section_key
                and _can_select(
                    item,
                    clusters=clusters,
                    source_counts=source_counts,
                    section_counts=section_counts,
                    policy=active_policy,
                )
            ),
            None,
        )
        if candidate is not None:
            _append_selected(
                candidate,
                clusters=clusters,
                selected=selected,
                selected_ids=selected_ids,
                source_counts=source_counts,
                section_counts=section_counts,
            )
            if len(selected) >= limit:
                return selected

    for candidate in candidates:
        ranked_id = candidate.ranked_item.id
        if ranked_id in selected_ids:
            continue
        if not _can_select(
            candidate,
            clusters=clusters,
            source_counts=source_counts,
            section_counts=section_counts,
            policy=active_policy,
        ):
            continue
        _append_selected(
            candidate,
            clusters=clusters,
            selected=selected,
            selected_ids=selected_ids,
            source_counts=source_counts,
            section_counts=section_counts,
        )
        if len(selected) >= limit:
            break
    return selected


def source_window(source_name: str, policy: BriefSelectionPolicy) -> timedelta:
    """Return the daily eligibility window for one source."""
    if _is_news_source(source_name):
        return timedelta(hours=policy.news_window_hours)
    if source_name in COMMUNITY_SOURCES:
        return timedelta(hours=policy.community_window_hours)
    if source_name in SEC_SOURCES:
        return timedelta(days=policy.sec_window_days)
    if source_name in ARXIV_SOURCES:
        return timedelta(days=policy.arxiv_window_days)
    if source_name in LONG_RESEARCH_SOURCES:
        return timedelta(days=policy.research_window_days)
    return timedelta(days=policy.default_window_days)


def is_long_term_research_item(
    item: ContentItem,
    *,
    now: datetime | None = None,
    policy: BriefSelectionPolicy | None = None,
) -> bool:
    """Return whether an item belongs in the long-term Research Feed."""
    if item.source_name not in {"arxiv", "github", "quantconnect", "stackexchange"}:
        return False
    if item.source_name != "stackexchange":
        return True
    if item.published_at is None:
        return True
    active_policy = policy or BriefSelectionPolicy()
    active_now = ensure_utc(now or utc_now())
    return active_now - ensure_utc(item.published_at) > timedelta(
        hours=active_policy.community_window_hours
    )


def _is_daily_eligible(
    item: ContentItem,
    *,
    now: datetime,
    policy: BriefSelectionPolicy,
) -> bool:
    if item.published_at is None:
        return False
    published_at = ensure_utc(item.published_at)
    if published_at > now + timedelta(minutes=5):
        return False
    return now - published_at <= source_window(item.source_name, policy)


def _is_news_source(source_name: str) -> bool:
    return (
        source_name in NEWS_SOURCES
        or source_name == "rss"
        or source_name.startswith("rss_")
        or source_name.startswith("finance_news_mcp_")
    )


def _published_sort_key(item: ContentItem) -> tuple[float, str]:
    if item.published_at is None:
        return (float("-inf"), item.id)
    return (ensure_utc(item.published_at).timestamp(), item.id)


def _can_select(
    candidate: SelectedRankedEvent,
    *,
    clusters: Mapping[str, Cluster],
    source_counts: Counter[str],
    section_counts: Counter[str],
    policy: BriefSelectionPolicy,
) -> bool:
    cluster_id = candidate.ranked_item.cluster_id
    if cluster_id is None or (cluster := clusters.get(cluster_id)) is None:
        return False
    if section_counts[candidate.section_key] >= policy.top_section_limit:
        return False
    sources = set(cluster.source_names) or {"unknown"}
    return all(source_counts[source] < policy.top_source_limit for source in sources)


def _append_selected(
    candidate: SelectedRankedEvent,
    *,
    clusters: Mapping[str, Cluster],
    selected: list[SelectedRankedEvent],
    selected_ids: set[str],
    source_counts: Counter[str],
    section_counts: Counter[str],
) -> None:
    cluster_id = candidate.ranked_item.cluster_id
    if cluster_id is None:
        return
    cluster = clusters[cluster_id]
    selected.append(candidate)
    selected_ids.add(candidate.ranked_item.id)
    section_counts[candidate.section_key] += 1
    for source in set(cluster.source_names) or {"unknown"}:
        source_counts[source] += 1


__all__ = [
    "BriefSelectionPolicy",
    "SelectedRankedEvent",
    "cluster_publication_times",
    "is_long_term_research_item",
    "select_daily_candidates",
    "select_diverse_top_events",
    "source_window",
]
