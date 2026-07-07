"""Structured LLM output schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EventEvidence(BaseModel):
    """Source evidence passed to the model."""

    source_id: str
    url: str
    title: str
    excerpt: str | None = None
    source_name: str | None = None


class EventSummary(BaseModel):
    """Strict event summary returned by the model."""

    event_id: str
    headline: str = Field(min_length=1, max_length=160)
    factual_summary: str = Field(min_length=1, max_length=1200)
    market_relevance: str = Field(min_length=1, max_length=800)
    uncertainty: str = Field(min_length=1, max_length=500)
    source_ids: list[str]
    source_urls: list[str]
    tickers: list[str] = Field(default_factory=list)
    assets: list[str] = Field(default_factory=list)
    quant_topics: list[str] = Field(default_factory=list)
    insufficient_evidence: bool = False


class SummaryResult(BaseModel):
    """Summarization result that preserves ranked-event context on failure."""

    success: bool
    ranked_item_id: str | None = None
    event_id: str | None = None
    ranked_score: float | None = None
    summary: EventSummary | None = None
    error_message: str | None = None


__all__ = ["EventEvidence", "EventSummary", "SummaryResult"]
