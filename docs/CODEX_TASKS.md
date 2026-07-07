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
- [ ] Implement deduplication baseline.
- [ ] Implement ranking baseline.
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
