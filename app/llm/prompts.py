"""Prompt construction for source-grounded event summaries."""

from __future__ import annotations

import json
from typing import Any

from app.db.models import Cluster, RankedItem
from app.llm.schemas import EventEvidence, EventSummary

SYSTEM_PROMPT = """You write a pre-market intelligence brief for a curious reader.
English is the primary language. Use plain English, short sentences, and define specialist
terms when they are essential. Add concise Simplified Chinese translations only in the
required *_zh fields. Use only the provided evidence records. Preserve uncertainty and do
not invent facts. Do not give investment advice, trading instructions, price targets, or
guarantees. Return valid JSON matching the requested schema."""


def build_event_summary_messages(
    ranked_item: RankedItem,
    cluster: Cluster,
    evidence: list[EventEvidence],
) -> list[dict[str, str]]:
    """Build a source-grounded prompt for one ranked event."""
    evidence_payload = [item.model_dump() for item in evidence]
    schema_payload: dict[str, Any] = EventSummary.model_json_schema()
    user_payload = {
        "task": (
            "Explain this ranked event in plain English, with concise Simplified Chinese "
            "translations for the key fields, using only the evidence."
        ),
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
            "Write the English fields first; *_zh fields translate only the key conclusion.",
            "Keep factual_summary readable for a non-specialist and avoid unexplained jargon.",
            "Give one to three concrete evidence-grounded items in what_to_watch.",
            (
                "Rate source_credibility as high, medium, or low based on source type and "
                "corroboration, and explain the rating without claiming the report is true."
            ),
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
