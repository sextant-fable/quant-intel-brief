# Project Specification

## Goal

Build a daily intelligence brief system for quantitative-finance research, markets, data sources, developer activity, and relevant platform signals.

## Product Shape

Local-first personal tool with SQLite storage, explicit user-managed credentials, a simple server-rendered dashboard, and optional email delivery.

## Non-Goals Through Phase 9

- No automatic live source collection.
- No real LLM calls in tests.
- No real email sending in tests.
- No automated or scheduled email delivery.
- No production deployment.
- No dashboard action that triggers external collection, LLM calls, or email sending.
- No premium full-text storage or paywall/browser automation.

## Planned Users

- Individual quant researcher or trader.
- Research assistant workflow.
- Future dashboard viewer.

## Planned Outputs

- Daily dashboard.
- Daily email report.
- Source status page.
- Archived report details.

## Milestones

1. Project scaffold and documentation.
2. Phase 0: configuration loading, SQLModel schema, SQLite session helpers, and fixture-only app health/status routes.
3. Phase 1: shared collector contract, RSS fixture parser, mocked HTTP handling, and metadata persistence.
4. Phase 2: official/public API collectors for market, macro, SEC, research, and developer metadata.
5. Phase 3: social, community, video, QuantConnect, and premium metadata boundaries.
6. Phase 4: canonicalization, compact-excerpt boundaries, source references, and retention metadata.
7. Phase 5: deterministic event deduplication and rule-based source/ticker/asset/quant-theme tagging.
8. Phase 6: deterministic ranking and heat scoring.
9. Phase 7: DeepSeek-compatible structured summarization with mocked tests.
10. Phase 8: daily HTML report generation and email preview/dry-run delivery.
11. Phase 9: local FastAPI dashboard views for local data.
12. QA, observability, and operational runbook.
