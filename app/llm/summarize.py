"""Source-grounded ranked-event summarization."""

from __future__ import annotations

from app.db.models import Cluster, ContentItem, RankedItem
from app.llm.client import JsonCompletionClient, LlmClientError
from app.llm.prompts import build_event_summary_messages
from app.llm.schemas import EventEvidence, EventSummary, SummaryResult

FORBIDDEN_ADVICE_TERMS = ("buy", "sell", "hold", "price target", "portfolio allocation")


class SummaryValidationError(ValueError):
    """Raised when model output violates grounding or safety rules."""


def summarize_ranked_event(
    ranked_item: RankedItem,
    cluster: Cluster,
    source_items: list[ContentItem],
    client: JsonCompletionClient,
) -> SummaryResult:
    """Summarize one ranked event with structured validation."""
    evidence = [_item_to_evidence(item) for item in source_items if item.id in cluster.item_ids]
    if not evidence:
        return _insufficient_evidence_result(ranked_item, cluster)

    messages = build_event_summary_messages(ranked_item, cluster, evidence)
    try:
        raw_summary = client.complete_json(messages)
        summary = EventSummary.model_validate(raw_summary)
        _validate_grounding(summary, evidence)
        _validate_non_advisory(summary)
    except (LlmClientError, SummaryValidationError, ValueError) as exc:
        return SummaryResult(
            success=False,
            ranked_item_id=ranked_item.id,
            event_id=cluster.id,
            ranked_score=ranked_item.score,
            error_message=str(exc),
        )

    return SummaryResult(
        success=True,
        ranked_item_id=ranked_item.id,
        event_id=cluster.id,
        ranked_score=ranked_item.score,
        summary=summary,
    )


def _item_to_evidence(item: ContentItem) -> EventEvidence:
    return EventEvidence(
        source_id=item.id,
        url=item.url,
        title=item.title,
        excerpt=item.excerpt or item.summary,
        source_name=item.source_name,
    )


def _insufficient_evidence_result(ranked_item: RankedItem, cluster: Cluster) -> SummaryResult:
    summary = EventSummary(
        event_id=cluster.id,
        headline="Insufficient source evidence",
        factual_summary="No source records were available for this ranked event.",
        market_relevance="Insufficient evidence to assess market relevance.",
        uncertainty="No source evidence was provided.",
        source_ids=[],
        source_urls=[],
        tickers=cluster.tickers,
        assets=cluster.assets,
        quant_topics=cluster.quant_topics,
        insufficient_evidence=True,
    )
    return SummaryResult(
        success=True,
        ranked_item_id=ranked_item.id,
        event_id=cluster.id,
        ranked_score=ranked_item.score,
        summary=summary,
    )


def _validate_grounding(summary: EventSummary, evidence: list[EventEvidence]) -> None:
    allowed_ids = {item.source_id for item in evidence}
    allowed_urls = {item.url for item in evidence}
    if not set(summary.source_ids) <= allowed_ids:
        raise SummaryValidationError("Summary cited source IDs that were not provided.")
    if not set(summary.source_urls) <= allowed_urls:
        raise SummaryValidationError("Summary cited source URLs that were not provided.")
    if not summary.source_ids and not summary.insufficient_evidence:
        raise SummaryValidationError("Summary must cite evidence or mark insufficient evidence.")


def _validate_non_advisory(summary: EventSummary) -> None:
    text = " ".join(
        [
            summary.headline,
            summary.factual_summary,
            summary.market_relevance,
            summary.uncertainty,
        ]
    ).lower()
    if any(term in text for term in FORBIDDEN_ADVICE_TERMS):
        raise SummaryValidationError("Summary contains advisory language.")


__all__ = ["SummaryValidationError", "summarize_ranked_event"]
