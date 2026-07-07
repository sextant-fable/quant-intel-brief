# LLM Prompts

Prompt templates and structured output requirements will live in `app/llm/prompts.py` and `app/llm/schemas.py`.

## Prompt Principles

- Summarize only from collected source content.
- Preserve uncertainty and source attribution.
- Separate factual summary from interpretation.
- Avoid investment advice, price targets, or personalized recommendations.
- Request structured JSON outputs when downstream code depends on fields.
- Do not invent tickers, dates, authors, prices, filings, model results, or causal explanations.
- If evidence is missing, return an explicit unknown or insufficient-evidence field.
- Include source IDs or URLs in report-ready outputs.

## Planned Prompt Families

- Item summary.
- Cluster summary.
- Quant relevance explanation.
- Daily lead-story selection rationale.
- Email report rewrite.
- Dashboard headline rewrite.
