"""Conservative rule-based ticker extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass

KNOWN_TICKERS = frozenset(
    {
        "AAPL",
        "AMZN",
        "BTC",
        "ETH",
        "GLD",
        "GOOGL",
        "IWM",
        "JPM",
        "META",
        "MSFT",
        "NVDA",
        "QQQ",
        "SPY",
        "TLT",
        "TSLA",
    }
)
AMBIGUOUS_UPPERCASE_WORDS = frozenset(
    {
        "AI",
        "API",
        "CPI",
        "ETF",
        "FED",
        "GDP",
        "LLM",
        "SEC",
        "USA",
    }
)
CASHTAG_RE = re.compile(r"(?<!\w)\$([A-Z]{1,5})(?!\w)")
UPPERCASE_RE = re.compile(r"(?<![A-Za-z])([A-Z]{2,5})(?![A-Za-z])")


@dataclass(frozen=True, slots=True)
class TickerTag:
    """Ticker tag with conservative confidence and provenance."""

    value: str
    confidence: float
    provenance: str = "rule:ticker_symbol"


def extract_tickers(text: str, known_tickers: frozenset[str] = KNOWN_TICKERS) -> list[TickerTag]:
    """Extract known tickers and explicit cashtags from text."""
    tags: dict[str, TickerTag] = {}

    for match in CASHTAG_RE.finditer(text):
        ticker = match.group(1).upper()
        if ticker in known_tickers:
            tags[ticker] = TickerTag(value=ticker, confidence=0.98, provenance="rule:cashtag")

    for match in UPPERCASE_RE.finditer(text):
        ticker = match.group(1).upper()
        if ticker in known_tickers and ticker not in AMBIGUOUS_UPPERCASE_WORDS:
            tags.setdefault(ticker, TickerTag(value=ticker, confidence=0.9))

    return [tags[key] for key in sorted(tags)]


__all__ = ["KNOWN_TICKERS", "TickerTag", "extract_tickers"]
