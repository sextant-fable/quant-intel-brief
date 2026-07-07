# Codex Tasks

Use this document to break future work into safe implementation tasks.

## Scaffold Status

- [x] Create repository structure.
- [x] Add documentation placeholders.
- [x] Add source adapter skill placeholders.
- [x] Add application package placeholders.
- [x] Add template and static asset placeholders.
- [x] Add test placeholders.

## Future Task Backlog

- [x] Define SQLModel models and migration-ready table metadata.
- [x] Implement configuration loading from `.env`.
- [x] Wire a fixture-only app factory and health/status routes.
- [x] Add Phase 0 schema and app shell tests.
- [x] Add normalized item schema tests for collector persistence.
- [x] Implement one public collector end to end with mocked HTTP tests.
- [x] Implement official/public API collectors with mocked HTTP tests.
- [x] Add missing-key, rate-limit, failure, and metadata-only collector tests.
- [x] Implement social, community, video, QuantConnect, and premium metadata collectors.
- [x] Add premium disabled-by-default and no-full-text boundary tests.
- [x] Add deterministic URL canonicalization tests.
- [x] Add compact excerpt and no-full-text extraction boundary tests.
- [x] Add source reference, payload hash, and retention metadata persistence tests.
- [x] Implement deduplication baseline.
- [x] Implement conservative ticker, asset, source, and quant-theme tagging baseline.
- [x] Implement ranking baseline.
- [x] Implement DeepSeek-compatible structured summarization with mocked tests.
- [ ] Implement report generation from fixtures only.
- [ ] Implement dashboard route from fixtures.
- [ ] Implement email preview before sending.

## Phase 0 Done Criteria

- Configuration loads without secrets committed.
- SQLite database schema is explicit and migration-ready.
- App factory can start locally with fixture-only health/status responses.
- Tests do not make external API calls.

## Phase 1 Done Criteria

- Shared collector result, fetch, retry, timeout, and rate-limit contracts exist.
- RSS/Atom parsing works from local fixtures.
- Collector metadata persists into source, raw item, content item, and source status tables.
- Duplicate source IDs and canonical URLs are handled deterministically.
- Tests use fixtures and mocked HTTP only.

## Phase 2 Done Criteria

- NewsAPI, GDELT, Alpha Vantage, Finnhub, FRED, SEC EDGAR, arXiv, and GitHub adapters emit normalized metadata.
- Key-gated collectors fail before HTTP when required local settings are absent.
- HTTP 429 and HTTP 500 responses are covered by mocked tests.
- Collectors store compact excerpts/summaries and safe metadata only.
- No social, video, premium, ranking, LLM, report, email, dashboard business, or scheduler behavior is implemented.

## Phase 3 Done Criteria

- Reddit, YouTube, X, Stack Exchange, QuantConnect, and premium metadata collectors emit normalized metadata.
- Social, video, and developer-platform collectors fail safely when required configuration is absent.
- Premium metadata collection is disabled by default, requires explicit authorization, and rejects full-text fields.
- Forbidden or access-denied responses are handled as source failures.
- No extraction beyond metadata boundaries, deduplication, ranking, LLM, report, email, dashboard business, or scheduler behavior is implemented.

## Phase 4 Done Criteria

- Canonical URL normalization is deterministic and strips common tracking parameters.
- Article extraction defaults to no text extraction and refuses full-text storage.
- Compact excerpts are sanitized and bounded when explicitly permitted.
- Raw and content items persist metadata-only storage policy, source references, payload hashes, and 30-day retention timestamps.
- No dedup clustering, enrichment, ranking, LLM, report, email, dashboard business, or scheduler behavior is implemented.

## Phase 5 Done Criteria

- Exact duplicate and near-duplicate content items cluster deterministically.
- Distinct events remain separate.
- Event-item relationships include confidence and provenance.
- Source, ticker, asset, and quant-theme tags include confidence and provenance.
- Ticker ambiguity is handled conservatively.
- No ranking, LLM, report, email, dashboard business, or scheduler behavior is implemented.

## Phase 6 Done Criteria

- Ranking order is deterministic for representative fixtures.
- Score components are visible in `RankedItem.score_components`.
- Recency, source credibility, coverage, asset importance, research signal, and community heat are tested.
- Community heat is capped and cannot dominate from one untrusted source alone.
- Explanations are complete and informational, not advisory.
- No LLM, report, email, dashboard business, or scheduler behavior is implemented.

## Phase 7 Done Criteria

- DeepSeek configuration uses `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, and `DEEPSEEK_MODEL`.
- Prompt construction sends only ranked-event context and compact source evidence.
- Structured summary output validates source IDs, URLs, uncertainty, and insufficient-evidence handling.
- Tests use fake clients and make no real external API calls.
- No report generation, email delivery, scheduler behavior, or dashboard business views are implemented.
