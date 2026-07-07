"""Rule-based asset-class tagging."""

from __future__ import annotations

from dataclasses import dataclass

ETF_TICKERS = frozenset({"SPY", "QQQ", "IWM", "TLT", "GLD"})
CRYPTO_TICKERS = frozenset({"BTC", "ETH"})
EQUITY_TICKERS = frozenset({"AAPL", "AMZN", "GOOGL", "JPM", "META", "MSFT", "NVDA", "TSLA"})


@dataclass(frozen=True, slots=True)
class AssetTag:
    """Asset class tag with explainable provenance."""

    value: str
    confidence: float
    provenance: str


def tag_assets(text: str, tickers: list[str] | None = None) -> list[AssetTag]:
    """Tag broad asset classes from source text and known tickers."""
    lowered = text.lower()
    ticker_set = set(tickers or [])
    tags: dict[str, AssetTag] = {}

    if ticker_set & ETF_TICKERS or any(word in lowered for word in ("etf", "treasury fund")):
        tags["etf"] = AssetTag("etf", 0.9, "rule:asset_keyword_or_ticker")
    if ticker_set & EQUITY_TICKERS or "equity" in lowered or "stock" in lowered:
        tags["equity"] = AssetTag("equity", 0.85, "rule:asset_keyword_or_ticker")
    if ticker_set & CRYPTO_TICKERS or "bitcoin" in lowered or "crypto" in lowered:
        tags["crypto"] = AssetTag("crypto", 0.9, "rule:asset_keyword_or_ticker")
    if any(word in lowered for word in ("option", "implied vol", "volatility surface")):
        tags["options"] = AssetTag("options", 0.88, "rule:asset_keyword")
    if any(word in lowered for word in ("fed", "cpi", "treasury", "rates", "yield")):
        tags["macro"] = AssetTag("macro", 0.82, "rule:asset_keyword")

    return [tags[key] for key in sorted(tags)]


__all__ = ["AssetTag", "tag_assets"]
