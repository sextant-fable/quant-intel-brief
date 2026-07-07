# Project Specification

## Goal

Build a daily intelligence brief system for quantitative-finance research, markets, data sources, developer activity, and relevant platform signals.

## Product Shape

Local-first personal tool with SQLite storage, explicit user-managed credentials, a simple server-rendered dashboard, and optional email delivery.

## Non-Goals In Phase 0

- No live source collection.
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
3. Initial public collectors.
4. Extraction, enrichment, and deduplication.
5. Ranking and report generation.
6. Dashboard and email delivery.
7. QA, observability, and operational runbook.
