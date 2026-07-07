"""Phase 5 rule-based enrichment tests."""

from __future__ import annotations

from app.db.models import ContentItem
from app.enrichers.asset_tagger import tag_assets
from app.enrichers.quant_tagger import tag_item_entities, tag_quant_topics
from app.enrichers.ticker_extractor import extract_tickers


def test_ticker_extraction_handles_ambiguous_uppercase_conservatively() -> None:
    text = "AI and SEC comments mention ETF regulation, while $SPY and NVDA trade actively."

    tickers = extract_tickers(text)

    assert [tag.value for tag in tickers] == ["NVDA", "SPY"]
    assert all(tag.value not in {"AI", "SEC", "ETF"} for tag in tickers)
    assert all(tag.provenance.startswith("rule:") for tag in tickers)


def test_asset_class_and_quant_theme_tagging() -> None:
    text = "SPY ETF options implied vol factor backtesting note on market microstructure."

    ticker_values = [tag.value for tag in extract_tickers(text)]
    assets = tag_assets(text, tickers=ticker_values)
    themes = tag_quant_topics(text)

    assert [tag.value for tag in assets] == ["etf", "options"]
    assert [tag.value for tag in themes] == [
        "backtesting",
        "factor",
        "microstructure",
        "volatility",
    ]
    assert all(tag.confidence > 0 for tag in assets + themes)


def test_item_entity_tags_include_source_and_provenance() -> None:
    item = ContentItem(
        id="item-1",
        source_name="fixture_source",
        source_item_id="source-1",
        url="https://example.test/item",
        title="NVDA volatility surface note",
        summary="Factor risk model update for equity options.",
    )

    tags = tag_item_entities(item)
    by_type = {(tag.entity_type, tag.value) for tag in tags}

    assert ("source", "fixture_source") in by_type
    assert ("ticker", "NVDA") in by_type
    assert ("asset", "equity") in by_type
    assert ("asset", "options") in by_type
    assert ("quant_theme", "factor") in by_type
    assert ("quant_theme", "risk_model") in by_type
    assert ("quant_theme", "volatility") in by_type
    assert item.tickers == ["NVDA"]
    assert "rule:" in tags[0].provenance
