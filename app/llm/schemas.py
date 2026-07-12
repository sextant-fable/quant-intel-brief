"""Structured LLM output schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


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
    headline_zh: str = Field(min_length=1, max_length=160)
    factual_summary: str = Field(min_length=1, max_length=1200)
    factual_summary_zh: str = Field(min_length=1, max_length=600)
    market_relevance: str = Field(min_length=1, max_length=800)
    market_relevance_zh: str = Field(min_length=1, max_length=500)
    uncertainty: str = Field(min_length=1, max_length=500)
    what_to_watch: list[str] = Field(min_length=1, max_length=3)
    what_to_watch_zh: list[str] = Field(min_length=1, max_length=3)
    source_credibility: Literal["high", "medium", "low"]
    source_credibility_reason: str = Field(min_length=1, max_length=300)
    source_ids: list[str]
    source_urls: list[str]
    tickers: list[str] = Field(default_factory=list)
    assets: list[str] = Field(default_factory=list)
    quant_topics: list[str] = Field(default_factory=list)
    insufficient_evidence: bool = False

    @model_validator(mode="after")
    def validate_paired_fields(self) -> EventSummary:
        if len(self.source_ids) != len(self.source_urls):
            raise ValueError("source_ids and source_urls must have matching lengths")
        if len(self.what_to_watch) != len(self.what_to_watch_zh):
            raise ValueError("English and Chinese watch lists must have matching lengths")
        return self


class SummaryResult(BaseModel):
    """Summarization result that preserves ranked-event context on failure."""

    success: bool
    ranked_item_id: str | None = None
    event_id: str | None = None
    ranked_score: float | None = None
    summary: EventSummary | None = None
    error_message: str | None = None


__all__ = ["EventEvidence", "EventSummary", "SummaryResult"]
