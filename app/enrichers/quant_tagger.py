"""Rule-based quant theme tagging and item tag assembly."""

from __future__ import annotations

from dataclasses import dataclass

from app.db.models import ContentItem, EntityTag
from app.enrichers.asset_tagger import tag_assets
from app.enrichers.ticker_extractor import extract_tickers

THEME_KEYWORDS = {
    "backtesting": ("backtest", "backtesting", "walk-forward"),
    "factor": ("factor", "momentum", "value", "quality"),
    "machine_learning": ("machine learning", " ml ", "model training"),
    "microstructure": ("microstructure", "order book", "liquidity", "market structure"),
    "risk_model": ("risk model", "portfolio risk", "drawdown", "var "),
    "volatility": ("volatility", "implied vol", "vol surface", "options"),
}


@dataclass(frozen=True, slots=True)
class QuantThemeTag:
    """Quant theme tag with explainable provenance."""

    value: str
    confidence: float
    provenance: str


def tag_quant_topics(text: str) -> list[QuantThemeTag]:
    """Tag quant themes from conservative keyword rules."""
    normalized = f" {text.lower()} "
    tags: list[QuantThemeTag] = []
    for theme, keywords in sorted(THEME_KEYWORDS.items()):
        if any(keyword in normalized for keyword in keywords):
            tags.append(QuantThemeTag(theme, 0.82, f"rule:theme:{theme}"))
    return tags


def tag_item_entities(item: ContentItem) -> list[EntityTag]:
    """Build ticker, asset, source, and quant-theme tags for one content item."""
    text = " ".join(part for part in [item.title, item.summary, item.excerpt] if part)
    ticker_tags = extract_tickers(text)
    tickers = [tag.value for tag in ticker_tags]
    asset_tags = tag_assets(text, tickers=tickers)
    topic_tags = tag_quant_topics(text)

    item.tickers = tickers
    item.assets = [tag.value for tag in asset_tags]
    item.quant_topics = [tag.value for tag in topic_tags]

    tags: list[EntityTag] = [
        EntityTag(
            item_id=item.id,
            entity_type="source",
            value=item.source_name,
            confidence=1.0,
            provenance="rule:source_name",
        )
    ]
    tags.extend(
        EntityTag(
            item_id=item.id,
            entity_type="ticker",
            value=tag.value,
            confidence=tag.confidence,
            provenance=tag.provenance,
        )
        for tag in ticker_tags
    )
    tags.extend(
        EntityTag(
            item_id=item.id,
            entity_type="asset",
            value=tag.value,
            confidence=tag.confidence,
            provenance=tag.provenance,
        )
        for tag in asset_tags
    )
    tags.extend(
        EntityTag(
            item_id=item.id,
            entity_type="quant_theme",
            value=tag.value,
            confidence=tag.confidence,
            provenance=tag.provenance,
        )
        for tag in topic_tags
    )
    return tags


__all__ = ["QuantThemeTag", "tag_item_entities", "tag_quant_topics"]
