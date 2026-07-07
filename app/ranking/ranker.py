"""Deterministic event ranking and heat scoring."""

from __future__ import annotations

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
IMPORTANT_ASSETS = frozenset({"macro", "options", "etf", "equity"})
RESEARCH_TOPICS = frozenset({"backtesting", "factor", "microstructure", "risk_model", "volatility"})
COMMUNITY_HEAT_COMPONENT_CAP = 0.15


def rank_clusters(
    clusters: list[Cluster],
    *,
    now: datetime | None = None,
    community_metrics: dict[str, float] | None = None,
) -> list[RankedItem]:
    """Rank clusters using explainable deterministic score components."""
    ranked_at = ensure_utc(now or utc_now())
    metrics = community_metrics or {}
    ranked_items = [
        _rank_cluster(cluster, ranked_at=ranked_at, community_heat=metrics.get(cluster.id, 0.0))
        for cluster in prefilter_clusters(clusters)
    ]
    return sorted(ranked_items, key=lambda item: (-item.score, item.cluster_id or ""))


def _rank_cluster(cluster: Cluster, ranked_at: datetime, community_heat: float) -> RankedItem:
    components = {
        "source_credibility": _source_credibility(cluster),
        "recency": _recency(cluster, ranked_at),
        "coverage": _coverage(cluster),
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
    values = [SOURCE_WEIGHTS.get(source, 0.45) for source in cluster.source_names]
    return round((sum(values) / len(values)) * 0.25, 4)


def _recency(cluster: Cluster, ranked_at: datetime) -> float:
    age_hours = max(0.0, (ranked_at - ensure_utc(cluster.created_at)).total_seconds() / 3600)
    return round(max(0.0, 1 - (age_hours / 36)) * 0.18, 4)


def _coverage(cluster: Cluster) -> float:
    item_component = min(len(cluster.item_ids), 4) / 4
    source_component = min(len(set(cluster.source_names)), 3) / 3
    return round(((item_component * 0.55) + (source_component * 0.45)) * 0.18, 4)


def _asset_importance(cluster: Cluster) -> float:
    assets = set(cluster.assets)
    topics = set(cluster.quant_topics)
    title = cluster.canonical_title.lower()
    score = 0.0
    if assets & IMPORTANT_ASSETS:
        score += 0.12
    if "sec" in cluster.source_names or "sec" in title:
        score += 0.05
    if "fred" in cluster.source_names or "fed" in title or "cpi" in title:
        score += 0.05
    if "options" in assets or "etf" in assets or "volatility" in topics:
        score += 0.04
    return round(min(score, 0.24), 4)


def _research_signal(cluster: Cluster) -> float:
    sources = set(cluster.source_names)
    topics = set(cluster.quant_topics)
    score = 0.0
    if sources & {"arxiv", "github", "quantconnect"}:
        score += 0.08
    if topics & RESEARCH_TOPICS:
        score += 0.07
    return round(min(score, 0.15), 4)


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
