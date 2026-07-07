"""Phase 6 deterministic ranking tests."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.core.timezones import UTC
from app.db.models import Cluster
from app.ranking.prefilter import prefilter_clusters
from app.ranking.ranker import COMMUNITY_HEAT_COMPONENT_CAP, rank_clusters


def _cluster(
    cluster_id: str,
    title: str,
    source_names: list[str],
    *,
    item_count: int = 1,
    assets: list[str] | None = None,
    quant_topics: list[str] | None = None,
    created_at: datetime | None = None,
) -> Cluster:
    return Cluster(
        id=cluster_id,
        canonical_title=title,
        item_ids=[f"{cluster_id}-item-{index}" for index in range(item_count)],
        source_names=source_names,
        assets=assets or [],
        quant_topics=quant_topics or [],
        created_at=created_at or datetime(2026, 7, 7, 12, 0, tzinfo=UTC),
    )


def test_ranking_order_from_representative_fixtures() -> None:
    now = datetime(2026, 7, 7, 14, 0, tzinfo=UTC)
    high = _cluster(
        "high",
        "SEC filing and Fed macro volatility update",
        ["sec_edgar", "fred", "newsapi"],
        item_count=3,
        assets=["macro", "options"],
        quant_topics=["volatility"],
    )
    low = _cluster(
        "low",
        "Community chatter about a quant topic",
        ["reddit"],
        item_count=1,
    )

    ranked = rank_clusters([low, high], now=now, community_metrics={"low": 100})

    assert [item.cluster_id for item in ranked] == ["high", "low"]
    assert ranked[0].score > ranked[1].score


def test_recency_decay_reduces_score_component() -> None:
    now = datetime(2026, 7, 7, 14, 0, tzinfo=UTC)
    recent = _cluster("recent", "SPY ETF options update", ["newsapi"], assets=["etf"])
    stale = _cluster(
        "stale",
        "SPY ETF options update",
        ["newsapi"],
        assets=["etf"],
        created_at=now - timedelta(hours=72),
    )

    ranked = {item.cluster_id: item for item in rank_clusters([recent, stale], now=now)}

    assert (
        ranked["recent"].score_components["recency"]
        > ranked["stale"].score_components["recency"]
    )
    assert ranked["stale"].score_components["recency"] == 0.0


def test_source_credibility_weighting_is_visible() -> None:
    now = datetime(2026, 7, 7, 14, 0, tzinfo=UTC)
    sec = _cluster("sec", "SEC metadata update", ["sec_edgar"])
    social = _cluster("social", "Same topic discussed socially", ["x_api"], assets=["equity"])

    ranked = {item.cluster_id: item for item in rank_clusters([sec, social], now=now)}

    assert ranked["sec"].score_components["source_credibility"] > ranked["social"].score_components[
        "source_credibility"
    ]


def test_community_heat_component_is_capped_and_not_sufficient_alone() -> None:
    now = datetime(2026, 7, 7, 14, 0, tzinfo=UTC)
    untrusted = _cluster("untrusted", "Social-only item about market gossip", ["reddit"])
    trusted = _cluster("trusted", "ETF volatility research note", ["arxiv"], assets=["etf"])

    ranked = rank_clusters(
        [untrusted, trusted],
        now=now,
        community_metrics={"untrusted": 10000, "trusted": 0},
    )
    by_id = {item.cluster_id: item for item in ranked}

    assert by_id["untrusted"].score_components["community_heat"] <= COMMUNITY_HEAT_COMPONENT_CAP
    assert by_id["untrusted"].score < by_id["trusted"].score


def test_prefilter_removes_empty_and_obvious_noise() -> None:
    keep = _cluster("keep", "FRED macro update", ["fred"], assets=["macro"])
    empty = _cluster("empty", "FRED macro update", ["fred"], assets=["macro"], item_count=0)
    noise = _cluster("noise", "spam giveaway", ["reddit"], item_count=1)

    assert prefilter_clusters([keep, empty, noise]) == [keep]


def test_explanation_field_is_complete_and_non_advisory() -> None:
    now = datetime(2026, 7, 7, 14, 0, tzinfo=UTC)
    cluster = _cluster(
        "explain",
        "GitHub factor backtesting library update",
        ["github"],
        assets=["equity"],
        quant_topics=["backtesting", "factor"],
    )

    ranked = rank_clusters([cluster], now=now)[0]

    assert ranked.explanation is not None
    for component in ranked.score_components:
        assert component in ranked.explanation or ranked.score_components[component] == 0
    assert "buy" not in ranked.explanation.lower()
    assert "sell" not in ranked.explanation.lower()
    assert "price target" not in ranked.explanation.lower()
