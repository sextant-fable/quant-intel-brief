---
name: report-quality-check
description: Instructions for reviewing generated reports for quality, sourcing, and legal boundaries.
---

# Report Quality Check Skill

Use this skill when reviewing generated daily briefs, email reports, or report templates.

## Review Focus

- Every claim has a source item or citation path.
- Market-sensitive statements are phrased as information, not investment advice.
- Summaries preserve uncertainty and avoid overstating causality.
- Duplicate clusters are not repeated as separate lead stories.
- LLM output does not invent facts missing from source records.
- HTML email output remains readable without external scripts.

## Acceptance Checklist

- Report has title, date, source coverage note, ranked sections, and source links.
- Top stories include why they matter for quant or market workflows.
- LLM output matches the schemas in `app/llm/schemas.py`.
- Legal boundaries in `docs/LEGAL_BOUNDARIES.md` are respected.
