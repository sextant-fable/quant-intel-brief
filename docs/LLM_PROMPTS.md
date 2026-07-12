# LLM Prompts

Prompt templates and structured output requirements live in `app/llm/prompts.py` and `app/llm/schemas.py`.

## Prompt Principles

- Summarize only from collected source content.
- Preserve uncertainty and source attribution.
- Separate factual summary from interpretation.
- Avoid investment advice, price targets, or personalized recommendations.
- Request structured JSON outputs when downstream code depends on fields.
- Do not invent tickers, dates, authors, prices, filings, model results, or causal explanations.
- If evidence is missing, return an explicit unknown or insufficient-evidence field.
- Include source IDs or URLs in report-ready outputs.
- Use plain English as the primary language and avoid unexplained specialist jargon.
- Translate only key conclusions into concise Simplified Chinese; do not replace the English analysis.
- Produce one to three evidence-grounded watch points in matching English and Chinese lists.
- Rate source confidence as high, medium, or low based on source type and corroboration, without treating confidence as proof.

## Planned Prompt Families

- Event summary: implemented in Phase 7.
- Report section summary: planned for report phases.
- Daily lead-story selection rationale: planned for report phases.
- Email report rewrite: planned for report phases.
- Dashboard headline rewrite: planned for dashboard phases.

## Phase 7 Behavior

- `OpenAICompatibleClient` uses `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL`.
- `LLM_PROVIDER` records the configured provider label, such as `deepseek`, `glm`, or `openai`.
- `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, and `DEEPSEEK_MODEL` remain legacy fallback aliases.
- Tests use fake clients and do not make real LLM calls.
- `EventSummary` validates structured fields before downstream use.
- Summaries must cite only provided source IDs and URLs.
- Missing evidence returns an explicit insufficient-evidence summary without calling the LLM.
- Unknown source citations or advisory language fail validation and preserve ranked-event context for manual review.
- Mismatched event IDs, source ID/URL pairs, or English/Chinese watch lists fail validation.
