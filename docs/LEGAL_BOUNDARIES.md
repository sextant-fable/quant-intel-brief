# Legal Boundaries

This project must respect source terms, copyright, privacy, and financial-advice boundaries.

## Source Access

- Use official APIs where available.
- Do not bypass paywalls, authentication, rate limits, robots guidance, or access controls.
- Do not commit credentials, cookies, private tokens, or exported sessions.
- Confirm platform terms before collection, storage, or redistribution.

## Content Use

- Store links and metadata by default.
- Do not store full text by default.
- Store extracted text only when source terms and user authorization clearly permit it.
- Keep generated summaries concise and source-grounded.
- Avoid reproducing full copyrighted articles or premium content.
- Compact excerpts must be bounded, sanitized, and used only when extraction is permitted.

## Premium And Social Boundaries

- Premium sources may provide user-authorized metadata only unless a later phase explicitly documents a permitted source-specific exception.
- Do not export, store, or replay browser cookies, local profiles, session files, or paywalled page bodies.
- Do not collect or store YouTube transcripts, X post expansions, Reddit selftext bodies, Stack Exchange answers, QuantConnect code files, or premium article bodies in Phase 3.
- Access-denied, forbidden, or missing-credential responses must be recorded as source failures, not worked around.

## Phase 4 Extraction Boundary

- `extract_article_metadata` defaults to metadata-only behavior and no-ops text extraction unless compact excerpts are explicitly permitted.
- Full-text storage requests must fail fast.
- Source references and hashes may be stored to support traceability without archiving the source payload.

## Financial Boundary

The system is for information organization and research assistance. It must not provide personalized investment advice, trading instructions, or guarantees.

Ranking and heat scores are informational prioritization signals. They must not be phrased as buy/sell/hold instructions, price targets, or portfolio recommendations.

## LLM Summary Boundary

- LLM summaries must be grounded only in provided evidence records.
- Summaries must cite only source IDs and URLs that were passed into the prompt.
- Missing or ambiguous evidence must remain explicit instead of being filled in by inference.
- LLM output must not include buy/sell/hold instructions, price targets, or portfolio allocation advice.
