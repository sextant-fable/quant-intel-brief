"""Prompt construction for source-grounded event summaries."""

from __future__ import annotations

import json
from typing import Any

from app.db.models import Cluster, RankedItem
from app.llm.schemas import EventEvidence, EventSummary

SYSTEM_PROMPT = """You summarize quantitative-finance intelligence events.
Use only the provided evidence records. Preserve uncertainty. Do not invent facts.
Do not give investment advice, trading instructions, price targets, or guarantees.
Return valid JSON matching the requested schema."""


def build_event_summary_messages(
    ranked_item: RankedItem,
    cluster: Cluster,
    evidence: list[EventEvidence],
) -> list[dict[str, str]]:
    """Build a source-grounded prompt for one ranked event."""
    evidence_payload = [item.model_dump() for item in evidence]
    schema_payload: dict[str, Any] = EventSummary.model_json_schema()
    user_payload = {
        "task": "Summarize this ranked event in English using only the evidence.",
        "event": {
            "event_id": cluster.id,
            "canonical_title": cluster.canonical_title,
            "tickers": cluster.tickers,
            "assets": cluster.assets,
            "quant_topics": cluster.quant_topics,
            "score": ranked_item.score,
            "score_components": ranked_item.score_components,
            "ranking_explanation": ranked_item.explanation,
        },
        "evidence": evidence_payload,
        "required_schema": schema_payload,
        "rules": [
            "Cite only source_ids and source_urls present in evidence.",
            "If evidence is missing or ambiguous, set insufficient_evidence to true.",
            (
                "Do not add prices, dates, authors, filings, tickers, "
                "or causal claims absent from evidence."
            ),
            "Do not include buy, sell, hold, price target, or portfolio advice.",
        ],
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(user_payload, sort_keys=True)},
    ]


__all__ = ["SYSTEM_PROMPT", "build_event_summary_messages"]
