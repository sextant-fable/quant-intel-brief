"""Deterministic market-section classification shared by ranking and reports."""

from __future__ import annotations

from collections.abc import Iterable

from app.db.models import Cluster

SECTION_DEFINITIONS: tuple[tuple[str, str, str], ...] = (
    ("macro_fed", "Macro & Fed", "宏观与美联储"),
    ("etf_options", "ETFs & Options", "ETF 与期权"),
    ("sec_companies", "SEC & Companies", "SEC 与公司"),
    ("quant_research", "Quant Research", "量化研究"),
    ("community_heat", "Community Heat", "社区热度"),
)
SECTION_KEYS = tuple(key for key, _, _ in SECTION_DEFINITIONS)

COMMUNITY_SOURCES = frozenset({"reddit", "stackexchange", "x_api", "youtube"})
RESEARCH_SOURCES = frozenset({"arxiv", "github", "quantconnect"})
RESEARCH_TOPICS = frozenset(
    {"arxiv", "backtesting", "factor", "microstructure", "risk_model", "volatility"}
)


def section_key_for_cluster(cluster: Cluster) -> str:
    """Classify an event before LLM summarization."""
    return section_key_from_signals(
        title=cluster.canonical_title,
        assets=cluster.assets,
        quant_topics=cluster.quant_topics,
        source_names=cluster.source_names,
    )


def section_key_from_signals(
    *,
    title: str,
    assets: Iterable[str] = (),
    quant_topics: Iterable[str] = (),
    source_names: Iterable[str] = (),
    extra_text: str = "",
) -> str:
    """Classify source-grounded signals into one of the five daily lenses."""
    normalized_assets = {asset.lower() for asset in assets}
    normalized_topics = {topic.lower() for topic in quant_topics}
    normalized_sources = {source.lower() for source in source_names}
    text = " ".join([title, extra_text]).lower()

    if normalized_sources & COMMUNITY_SOURCES or any(
        term in text for term in ("community", "reddit", "stack exchange", "youtube")
    ):
        return "community_heat"
    if "fred" in normalized_sources or "macro" in normalized_assets:
        return "macro_fed"
    if "sec_edgar" in normalized_sources or any(
        term in text for term in ("sec", "filing", "10-k", "10-q", "8-k")
    ):
        return "sec_companies"
    if normalized_sources & RESEARCH_SOURCES:
        return "quant_research"
    if normalized_assets & {"etf", "options"} or any(
        term in text for term in ("etf", "option", "implied vol", "volatility surface")
    ):
        return "etf_options"
    if any(term in text for term in ("fed", "fomc", "inflation", "cpi", "gdp", "payroll")):
        return "macro_fed"
    if normalized_topics & RESEARCH_TOPICS or any(
        term in text for term in ("research", "paper", "arxiv", "backtest", "factor model")
    ):
        return "quant_research"
    return "sec_companies"


__all__ = [
    "SECTION_DEFINITIONS",
    "SECTION_KEYS",
    "section_key_for_cluster",
    "section_key_from_signals",
]
