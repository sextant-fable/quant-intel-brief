"""Phase 6 deterministic ranking tests."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

from app.core.timezones import UTC
from app.db.models import Cluster, ContentItem, RankedItem
from app.ranking.prefilter import prefilter_clusters
from app.ranking.ranker import COMMUNITY_HEAT_COMPONENT_CAP, rank_clusters
from app.ranking.selection import (
    BriefSelectionPolicy,
    is_long_term_research_item,
    select_daily_candidates,
    select_diverse_top_events,
)


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
    assert ranked["stale"].score_components["recency"] > 0.0


def test_ranking_recency_uses_supplied_publication_time() -> None:
    now = datetime(2026, 7, 7, 14, 0, tzinfo=UTC)
    cluster = _cluster("published", "Fresh filing update", ["sec_edgar"], created_at=now)

    ranked = rank_clusters(
        [cluster],
        now=now,
        published_at_by_cluster={"published": now - timedelta(days=7)},
    )[0]

    assert ranked.score_components["recency"] < 0.03


def test_cross_source_corroboration_requires_distinct_sources() -> None:
    now = datetime(2026, 7, 7, 14, 0, tzinfo=UTC)
    single = _cluster("single", "Macro release update", ["newsapi"], item_count=3)
    corroborated = _cluster(
        "corroborated",
        "Macro release update",
        ["newsapi", "finance_news_mcp_bloomberg"],
        item_count=2,
    )

    ranked = {item.cluster_id: item for item in rank_clusters([single, corroborated], now=now)}

    assert ranked["single"].score_components["cross_source_corroboration"] == 0.0
    assert ranked["corroborated"].score_components["cross_source_corroboration"] > 0.0


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


def test_daily_candidates_use_publication_windows_and_per_source_quota() -> None:
    now = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)
    policy = BriefSelectionPolicy(items_per_source=20)
    items = [
        _content_item(
            f"news-{index}",
            "newsapi",
            published_at=now - timedelta(hours=index),
        )
        for index in range(25)
    ]
    items.extend(
        _content_item(
            f"finnhub-{index}",
            "finnhub",
            published_at=now - timedelta(minutes=index),
        )
        for index in range(25)
    )
    items.extend(
        [
            _content_item("old-news", "newsapi", published_at=now - timedelta(days=4)),
            _content_item("old-stack", "stackexchange", published_at=now - timedelta(days=4)),
            _content_item("recent-sec", "sec_edgar", published_at=now - timedelta(days=10)),
            _content_item("recent-arxiv", "arxiv", published_at=now - timedelta(days=20)),
            _content_item("missing-date", "newsapi", published_at=None),
        ]
    )

    selected = select_daily_candidates(items, limit=100, now=now, policy=policy)
    counts = Counter(item.source_name for item in selected)
    selected_ids = {item.id for item in selected}

    assert counts["newsapi"] == 20
    assert counts["finnhub"] == 20
    assert {"recent-sec", "recent-arxiv"} <= selected_ids
    assert {"old-news", "old-stack", "missing-date"}.isdisjoint(selected_ids)
    assert is_long_term_research_item(
        next(item for item in items if item.id == "old-stack"),
        now=now,
        policy=policy,
    )


def test_top_event_selection_covers_lenses_and_enforces_diversity() -> None:
    clusters = {
        "macro-1": _cluster("macro-1", "Fed inflation update", ["newsapi"], assets=["macro"]),
        "macro-2": _cluster("macro-2", "FOMC policy update", ["newsapi"], assets=["macro"]),
        "macro-3": _cluster("macro-3", "CPI release update", ["newsapi"], assets=["macro"]),
        "etf": _cluster("etf", "SPY options update", ["finnhub"], assets=["options"]),
        "sec": _cluster("sec", "Issuer files 10-Q", ["sec_edgar"]),
        "research": _cluster(
            "research",
            "New factor paper",
            ["arxiv"],
            quant_topics=["factor"],
        ),
        "community": _cluster("community", "Community market discussion", ["reddit"]),
    }
    ranked = [
        RankedItem(
            id=f"ranked-{cluster_id}",
            cluster_id=cluster_id,
            score=100 - index,
        )
        for index, cluster_id in enumerate(clusters)
    ]

    selected = select_diverse_top_events(ranked, clusters, limit=10)
    source_counts: Counter[str] = Counter()
    section_counts = Counter(item.section_key for item in selected)
    for item in selected:
        cluster = clusters[item.ranked_item.cluster_id or ""]
        source_counts.update(set(cluster.source_names))

    assert {item.section_key for item in selected} == {
        "macro_fed",
        "etf_options",
        "sec_companies",
        "quant_research",
        "community_heat",
    }
    assert max(source_counts.values()) <= 2
    assert max(section_counts.values()) <= 3
    assert len(selected) == 6


def _content_item(
    item_id: str,
    source_name: str,
    *,
    published_at: datetime | None,
) -> ContentItem:
    return ContentItem(
        id=item_id,
        source_name=source_name,
        source_item_id=item_id,
        url=f"https://example.test/{item_id}",
        title=f"Title for {item_id}",
        published_at=published_at,
        fetched_at=datetime(2026, 7, 12, 12, 0, tzinfo=UTC),
    )
