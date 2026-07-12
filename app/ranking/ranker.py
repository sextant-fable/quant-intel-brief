"""Deterministic event ranking and heat scoring."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from app.core.timezones import ensure_utc, utc_now
from app.db.models import Cluster, RankedItem
from app.ranking.prefilter import prefilter_clusters

SOURCE_WEIGHTS = {
    "sec_edgar": 1.0,
    "fred": 0.95,
    "arxiv": 0.85,
    "github": 0.75,
    "quantconnect": 0.72,
    "alphavantage": 0.72,
    "finnhub": 0.72,
    "newsapi": 0.7,
    "gdelt": 0.68,
    "premium_browser": 0.65,
    "stackexchange": 0.5,
    "reddit": 0.35,
    "youtube": 0.35,
    "x_api": 0.3,
}
FINANCE_NEWS_MCP_WEIGHTS = {
    "bloomberg": 0.92,
    "cnbc": 0.82,
    "ft": 0.92,
    "marketwatch": 0.78,
    "seekingalpha": 0.62,
    "wsj": 0.92,
}
IMPORTANT_ASSETS = frozenset({"macro", "options", "etf", "equity"})
RESEARCH_TOPICS = frozenset({"backtesting", "factor", "microstructure", "risk_model", "volatility"})
COMMUNITY_HEAT_COMPONENT_CAP = 0.1


def rank_clusters(
    clusters: list[Cluster],
    *,
    now: datetime | None = None,
    community_metrics: dict[str, float] | None = None,
    published_at_by_cluster: Mapping[str, datetime] | None = None,
) -> list[RankedItem]:
    """Rank clusters using explainable deterministic score components."""
    ranked_at = ensure_utc(now or utc_now())
    metrics = community_metrics or {}
    publication_times = published_at_by_cluster or {}
    ranked_items = [
        _rank_cluster(
            cluster,
            ranked_at=ranked_at,
            published_at=publication_times.get(cluster.id),
            community_heat=metrics.get(cluster.id, 0.0),
        )
        for cluster in prefilter_clusters(clusters)
    ]
    return sorted(ranked_items, key=lambda item: (-item.score, item.cluster_id or ""))


def _rank_cluster(
    cluster: Cluster,
    ranked_at: datetime,
    published_at: datetime | None,
    community_heat: float,
) -> RankedItem:
    components = {
        "source_credibility": _source_credibility(cluster),
        "recency": _recency(published_at or cluster.created_at, ranked_at),
        "cross_source_corroboration": _cross_source_corroboration(cluster),
        "asset_importance": _asset_importance(cluster),
        "research_signal": _research_signal(cluster),
        "community_heat": _community_heat(cluster, community_heat),
    }
    score = round(sum(components.values()) * 100, 2)
    return RankedItem(
        cluster_id=cluster.id,
        score=score,
        score_components=components,
        explanation=_explanation(cluster, components),
        ranked_at=ranked_at,
    )


def _source_credibility(cluster: Cluster) -> float:
    if not cluster.source_names:
        return 0.0
    values = [_source_weight(source) for source in cluster.source_names]
    blended = (max(values) * 0.65) + ((sum(values) / len(values)) * 0.35)
    return round(blended * 0.25, 4)


def _source_weight(source_name: str) -> float:
    prefix = "finance_news_mcp_"
    if source_name.startswith(prefix):
        publisher = source_name.removeprefix(prefix)
        return FINANCE_NEWS_MCP_WEIGHTS.get(publisher, 0.7)
    if source_name == "rss" or source_name.startswith("rss_"):
        return 0.65
    return SOURCE_WEIGHTS.get(source_name, 0.45)


def _recency(published_at: datetime, ranked_at: datetime) -> float:
    age_hours = max(0.0, (ranked_at - ensure_utc(published_at)).total_seconds() / 3600)
    return round((1 / (1 + (age_hours / 24))) * 0.2, 4)


def _cross_source_corroboration(cluster: Cluster) -> float:
    source_count = len(set(cluster.source_names))
    if source_count < 2:
        return 0.0
    source_component = min(source_count, 4) / 4
    item_component = min(len(cluster.item_ids), 4) / 4
    return round(((source_component * 0.8) + (item_component * 0.2)) * 0.18, 4)


def _asset_importance(cluster: Cluster) -> float:
    assets = set(cluster.assets)
    topics = set(cluster.quant_topics)
    title = cluster.canonical_title.lower()
    score = 0.0
    if assets & IMPORTANT_ASSETS:
        score += 0.11
    if "sec_edgar" in cluster.source_names or "sec" in title:
        score += 0.05
    if "fred" in cluster.source_names or "fed" in title or "cpi" in title:
        score += 0.05
    if "options" in assets or "etf" in assets or "volatility" in topics:
        score += 0.04
    return round(min(score, 0.22), 4)


def _research_signal(cluster: Cluster) -> float:
    sources = set(cluster.source_names)
    topics = set(cluster.quant_topics)
    score = 0.0
    if sources & {"arxiv", "github", "quantconnect"}:
        score += 0.07
    if topics & RESEARCH_TOPICS:
        score += 0.05
    return round(min(score, 0.12), 4)


def _community_heat(cluster: Cluster, community_heat: float) -> float:
    if community_heat <= 0:
        return 0.0
    trusted_signal = bool(
        set(cluster.source_names) - {"reddit", "youtube", "x_api"}
        or cluster.assets
        or cluster.quant_topics
    )
    trust_multiplier = 1.0 if trusted_signal else 0.4
    normalized = min(community_heat, 100.0) / 100.0
    capped_heat = min(COMMUNITY_HEAT_COMPONENT_CAP, normalized * COMMUNITY_HEAT_COMPONENT_CAP)
    return round(capped_heat * trust_multiplier, 4)


def _explanation(cluster: Cluster, components: dict[str, float]) -> str:
    nonzero = [name for name, value in components.items() if value > 0]
    component_text = ", ".join(nonzero) if nonzero else "no positive components"
    return (
        f"Ranked as market-relevant because {cluster.canonical_title!r} has "
        f"component support from {component_text}. "
        "This is an informational importance score, not a trading recommendation."
    )


__all__ = ["COMMUNITY_HEAT_COMPONENT_CAP", "rank_clusters"]
