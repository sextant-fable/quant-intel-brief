# Quant Intel Brief Agent Guide

Quant Intel Brief is a local-first personal intelligence system for quantitative-finance research. Keep changes narrow, auditable, and source-aware.

## Current Stage

Phase 8 daily HTML report generation and email preview/dry-run delivery are implemented with mocked tests. Do not implement scheduling or dashboard business views until the relevant phase in `PLANS.md`.

## Repository Layout

- `AGENTS.md`: agent operating guide and stage boundaries.
- `README.md`: user-facing setup and status.
- `.env.example`: environment variable template with no secrets.
- `.codex/config.toml`: Codex project metadata and default checks.
- `.agents/skills/`: instruction-only Codex skills for future source adapters, report review, and dashboard QA.
- `docs/PROJECT_SPEC.md`: concise product scope and milestones.
- `docs/DATA_SOURCES.md`: planned source adapters and access boundaries.
- `docs/DATA_SCHEMA.md`: normalized data model notes for the next implementation step.
- `docs/LLM_PROMPTS.md`: prompt and anti-hallucination rules.
- `docs/LEGAL_BOUNDARIES.md`: source, copyright, privacy, and financial boundaries.
- `docs/CODEX_TASKS.md`: implementation backlog.
- `docs/RUNBOOK.md`: local setup, checks, and future operations notes.
- `app/core/`: configuration, logging, and timezone utilities.
- `app/db/`: SQLModel models, sessions, and migrations.
- `app/collectors/`: source adapters only.
- `app/extractors/`: permitted article/page extraction only.
- `app/enrichers/`: ticker, asset, and quant-topic tagging.
- `app/dedup/`: canonicalization and clustering.
- `app/ranking/`: prefiltering and scoring.
- `app/llm/`: DeepSeek-compatible client, schemas, prompts, and summarization.
- `app/reports/`: report assembly and template helpers.
- `app/email/`: outbound delivery interfaces and providers.
- `app/web/`: dashboard routes, filters, and view models.
- `app/jobs/`: daily workflow, scheduler, and cleanup.
- `templates/`: server-rendered HTML templates.
- `static/`: local CSS, JavaScript, and vendored assets.
- `data/`: ignored local runtime database and generated reports.
- `tests/`: unit tests and fixtures.

## Commands

Set up locally:

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run checks:

```bash
python -m compileall -q app tests
pytest
ruff check .
mypy app tests
```

Run the app after Phase 0 wires `app.main:create_app`:

```bash
uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

During Phase 0, the app entry point exposes only fixture system routes. Business routes remain out of scope.

## Engineering Conventions

- Prefer small modules with explicit responsibilities.
- Use typed Python and Pydantic/SQLModel schemas for structured data.
- Keep source collection, extraction, enrichment, deduplication, ranking, LLM summarization, reporting, delivery, and scheduling separate.
- Keep secrets out of the repository. Use `.env` locally and update `.env.example` when new settings are introduced.
- Treat all source content as untrusted input until validated and normalized.
- Store timestamps in UTC internally and convert only at presentation boundaries.
- Prefer official APIs and documented endpoints.
- Mock network interactions in tests with fixtures or `respx`.
- Add tests with each behavior change.

## Stage Boundaries

For multi-phase implementation, `PLANS.md` is authoritative. Do not invent alternate phase numbering.

For Goal Mode commits and pushes, follow the Git Checkpoint Policy in `docs/GOAL_MVP.md`.

Do not skip stages unless the user explicitly changes the plan.

## Legal And Data Boundaries

- No paywall bypass, credential sharing, session-cookie export, access-control circumvention, or rate-limit evasion.
- No full-text storage by default. Store links, metadata, compact excerpts, and source references unless the source terms and user authorization clearly permit more.
- No redistribution of premium, private, or copyrighted content beyond permitted summaries and links.
- No personalized investment advice, trade instructions, price targets, or performance guarantees.

## LLM Anti-Hallucination Rules

- Summarize only from collected source records and linked citations.
- Require structured output schemas for downstream use.
- Preserve uncertainty and distinguish reported facts from interpretation.
- If source evidence is missing or ambiguous, say so in the generated fields instead of filling gaps.
- Do not invent tickers, dates, authors, prices, filings, model results, or causal claims.
- Include source IDs or URLs in report-ready outputs.

## Done Criteria For Every Future Task

- Scope stays within the requested stage and module boundary.
- Code is typed, formatted, lint-clean, and importable.
- `python -m compileall -q app tests`, `pytest`, and relevant lint/type checks pass or any exceptions are documented.
- Tests cover the changed behavior, including at least one failure or edge case when relevant.
- Network calls are mocked in tests.
- New configuration is documented in `.env.example`.
- Source limits, retry behavior, and failure handling are documented when a source is added.
- No credentials, cookies, API keys, paid content, private data, or generated runtime artifacts are committed.
