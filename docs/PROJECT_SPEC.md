# Project Specification

## Goal

Build a daily intelligence brief system for quantitative-finance research, markets, data sources, developer activity, and relevant platform signals.

## Product Shape

Local-first personal tool with SQLite storage, explicit user-managed credentials, a simple server-rendered dashboard, and optional email delivery.

## Non-Goals Through Phase 2

- No automatic live source collection.
- No LLM calls.
- No ranking model.
- No automated email delivery.
- No production deployment.
- No real dashboard business views.

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
5. Extraction, enrichment, and deduplication.
6. Ranking and report generation.
7. Dashboard and email delivery.
8. QA, observability, and operational runbook.
