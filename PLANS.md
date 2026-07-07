# Quant Intel Brief Implementation Plan

This document is the phase contract for building Quant Intel Brief, a local-first personal Daily Quant Intelligence Briefing System. Codex should consult this file before any multi-phase implementation work and must not invent alternate phase numbering or scope.

## Global Rules

- Keep the system local-first: SQLite, local templates, local dashboard, user-managed credentials.
- Do not bypass paywalls, authentication, robots guidance, rate limits, or platform access controls.
- Do not store copyrighted full text by default. Store metadata, links, compact excerpts, hashes, and source references unless source terms and user authorization clearly permit more.
- Do not make external API calls in tests. Use fixtures, local files, and `respx` HTTP mocks.
- Do not commit secrets, cookies, API keys, session exports, generated reports, or runtime databases.
- Keep collection, extraction, tagging, deduplication, ranking, LLM summarization, reporting, email, dashboard, and scheduling as separate layers.
- Use DeepSeek through an OpenAI-compatible client only when the LLM phase begins.
- In an explicitly approved Goal Mode run, continue automatically from one phase to the next after the phase checkpoint passes, commits, and pushes.

## Phase Dependencies

```text
Phase 0 Foundation
  -> Phase 1 Public Source Framework
    -> Phase 2 Market, Macro, Research, And Developer Collectors
      -> Phase 3 Social, Community, Video, And Premium Metadata Collectors
        -> Phase 4 Normalization, Extraction Boundaries, And Storage Hygiene
          -> Phase 5 Event Deduplication And Tagging
            -> Phase 6 Ranking And Heat
              -> Phase 7 DeepSeek Summarization
                -> Phase 8 Daily HTML Email Report
                  -> Phase 9 Local FastAPI Dashboard
                    -> Phase 10 Scheduling, Retention, And Operations
```

## Checkpoint Policy

- Before starting a phase, Codex must read `AGENTS.md`, `PLANS.md`, relevant `docs/*.md`, and any relevant `.agents/skills/*/SKILL.md`.
- At phase start, state the phase scope, files expected to change, and what will remain out of scope.
- During a phase, keep commits or change batches small enough to review. If the repo is under git, inspect status before and after work.
- At phase completion, report changed files, tests run, skipped checks with reasons, commit/push status, and any follow-up risks.
- In Goal Mode, phase boundaries are audit checkpoints, not manual approval gates. Continue to the next phase automatically after successful validation, secret-safety checks, commit, and push.
- If a phase discovers legal, source-access, schema, or secret-handling uncertainty, stop and ask before proceeding.
- If validation or tooling fails, diagnose and attempt reasonable fixes within the active phase scope, then rerun validation. Stop only when the failure depends on external state, credentials, legal/source-access uncertainty, missing user decisions, unavailable required tooling that cannot be safely installed or worked around, or repeated failures that cannot be resolved without changing approved scope.

## Required Completion Commands

Every phase must run these before being declared complete:

```bash
python -m compileall -q app tests
pytest
ruff check .
mypy app tests
```

If a phase wires the web app, also run a local FastAPI route test through pytest. If a phase changes templates or dashboard behavior, add template/render tests. If a phase changes collectors or HTTP clients, run mocked HTTP tests only.

## Phase 0: Foundation And App Shell

Goal: create the minimum working local application foundation without any real source collection or business pipeline.

Dependencies: current scaffold only.

Likely files to change:

- `app/core/config.py`
- `app/core/logging.py`
- `app/core/timezones.py`
- `app/db/models.py`
- `app/db/session.py`
- `app/main.py`
- `app/web/routes.py`
- `docs/DATA_SCHEMA.md`
- `docs/RUNBOOK.md`
- `tests/test_scaffold.py`
- New focused tests under `tests/`

Implementation scope:

- Environment-backed settings using `.env.example` names.
- SQLModel base models for sources, raw items, normalized items, clusters, reports, deliveries, and source status.
- SQLite engine/session helpers.
- App factory with fixture-only health/status route.
- Logging setup that does not leak secrets.
- UTC helpers and local display timezone helpers.

Must not implement:

- Collectors, HTTP calls, extraction, deduplication, ranking, LLM calls, report generation, email sending, scheduler, or real dashboard pages.
- Any external API access.
- Full-text storage.

Definition of done:

- App can be created locally without credentials.
- Database schema is explicit and migration-ready.
- Health/status route returns fixture-only local state.
- Settings load defaults from `.env.example` without requiring secrets.
- Runtime database files remain ignored.

Required tests:

- Settings default loading and environment override tests.
- SQLite in-memory model creation test.
- App factory and health route test.
- Secret redaction/logging test if logging configuration is implemented.

Commands before completion:

```bash
python -m compileall -q app tests
pytest
ruff check .
mypy app tests
```

## Phase 1: Public Source Framework

Goal: implement the shared collector contract and persistence path using fixtures and mocked HTTP, before adding broad source coverage.

Dependencies: Phase 0.

Likely files to change:

- `app/collectors/base.py`
- `app/collectors/rss.py`
- `app/db/models.py`
- `app/db/session.py`
- `docs/DATA_SOURCES.md`
- `.agents/skills/financial-source-adapter/SKILL.md`
- `tests/test_collectors.py`
- `tests/fixtures/`

Implementation scope:

- Typed collector result schemas.
- Common timeout, retry, and rate-limit handling.
- RSS collector as the first permitted public adapter.
- Normalized metadata persistence with canonical URL and source IDs.
- Fixture-driven source status records.

Must not implement:

- Paid or premium sources.
- DeepSeek/LLM logic.
- Ranking, deduplication, reports, email, dashboard business views, or scheduling.
- Any unmocked external network calls in tests.

Definition of done:

- One RSS/feed source can be parsed from fixtures and stored as normalized metadata.
- Duplicate source IDs or canonical URLs are handled deterministically.
- Failure states are persisted or returned without crashing the app shell.
- Source behavior and limits are documented.

Required tests:

- Feed parse success.
- Empty feed.
- Duplicate item handling.
- HTTP timeout/rate-limit mock.
- Persistence of normalized item metadata.

Commands before completion:

```bash
python -m compileall -q app tests
pytest tests/test_collectors.py tests/test_scaffold.py
pytest
ruff check .
mypy app tests
```

## Phase 2: Market, Macro, Research, And Developer Collectors

Goal: add official/public API collectors for core quant-relevant metadata.

Dependencies: Phase 1.

Likely files to change:

- `app/collectors/newsapi.py`
- `app/collectors/gdelt.py`
- `app/collectors/alphavantage.py`
- `app/collectors/finnhub.py`
- `app/collectors/fred.py`
- `app/collectors/sec_edgar.py`
- `app/collectors/arxiv.py`
- `app/collectors/github.py`
- `docs/DATA_SOURCES.md`
- `.env.example`
- `tests/test_collectors.py`
- `tests/fixtures/`

Implementation scope:

- US market, ETF, options, macro/Fed, SEC, FRED, arXiv, and GitHub metadata adapters where official endpoints permit use.
- Source-specific parsing into shared normalized records.
- Source status, rate-limit, and error reporting.
- Tests using fixtures and mocked responses.

Must not implement:

- Social/community/video collectors.
- Premium browsing.
- Full-text article storage.
- Deduplication, ranking, LLM summaries, reports, email, dashboard business views, or scheduler.

Definition of done:

- Each implemented collector has documented access requirements and rate-limit notes.
- Every collector can run against fixtures/mocked HTTP without credentials.
- Records include source IDs, canonical links, publication times, fetched times, and compact excerpts or summaries only.
- No collector stores secret headers, cookies, or full copyrighted text.

Required tests:

- Success and failure response per collector.
- Missing API key behavior.
- Rate-limit or quota response handling.
- Normalization field completeness.
- No full-text storage guard.

Commands before completion:

```bash
python -m compileall -q app tests
pytest tests/test_collectors.py
pytest
ruff check .
mypy app tests
```

## Phase 3: Social, Community, Video, And Premium Metadata Collectors

Goal: add metadata-only adapters for Reddit, YouTube, X, Stack Exchange, QuantConnect, and user-authorized premium-source metadata.

Dependencies: Phase 2.

Likely files to change:

- `app/collectors/reddit.py`
- `app/collectors/youtube.py`
- `app/collectors/x_api.py`
- `app/collectors/stackexchange.py`
- `app/collectors/quantconnect.py`
- `app/collectors/premium_browser.py`
- `app/extractors/premium_extractor.py`
- `docs/DATA_SOURCES.md`
- `docs/LEGAL_BOUNDARIES.md`
- `.env.example`
- `tests/test_collectors.py`
- `tests/fixtures/`

Implementation scope:

- Metadata-only collection from official APIs where permitted.
- Premium-source metadata capture only when user-authorized and explicitly enabled.
- Strict source status and legal-boundary reporting.

Must not implement:

- Paywall bypass, cookie export, credential sharing, scraping behind access controls, or premium full-text storage.
- Transcript storage unless terms clearly permit it.
- Ranking, LLM summaries, report generation, email delivery, scheduler, or real dashboard business logic.

Definition of done:

- Social/community/video collectors are disabled unless configured.
- Premium metadata path refuses to run unless explicitly enabled.
- Stored records are links, metadata, compact excerpts, and hashes only.
- Legal boundaries are documented and enforced by tests.

Required tests:

- Disabled-by-default premium collector test.
- Missing credential behavior.
- Mock success and error response for each adapter.
- Metadata-only storage assertion.
- Access-denied or forbidden response handling.

Commands before completion:

```bash
python -m compileall -q app tests
pytest tests/test_collectors.py
pytest
ruff check .
mypy app tests
```

## Phase 4: Normalization, Extraction Boundaries, And Storage Hygiene

Goal: create safe normalization and permitted extraction boundaries before event logic.

Dependencies: Phase 3.

Likely files to change:

- `app/extractors/article_extractor.py`
- `app/extractors/premium_extractor.py`
- `app/dedup/canonicalize.py`
- `app/db/models.py`
- `docs/DATA_SCHEMA.md`
- `docs/LEGAL_BOUNDARIES.md`
- `tests/fixtures/`
- New extraction/canonicalization tests

Implementation scope:

- Canonical URL normalization.
- Compact excerpt extraction from permitted content.
- Hashing and source reference storage.
- Retention flags needed for 30-day history.

Must not implement:

- Full article archiving by default.
- Paywall bypass or premium body extraction.
- Dedup clustering, ranking, LLM summaries, reports, email, dashboard business views, or scheduler.

Definition of done:

- Normalized records are consistent across source types.
- Extraction refuses or no-ops when content storage is not permitted.
- Canonicalization is deterministic and covered by tests.
- 30-day retention requirements are represented in schema or docs.

Required tests:

- Canonical URL variants.
- Excerpt length and sanitization.
- No-full-text-storage guard.
- Source reference and hash persistence.
- UTC timestamp normalization.

Commands before completion:

```bash
python -m compileall -q app tests
pytest
ruff check .
mypy app tests
```

## Phase 5: Event Deduplication And Tagging

Goal: group raw/normalized items into events and tag them by asset class, ticker, source, and quant theme.

Dependencies: Phase 4.

Likely files to change:

- `app/dedup/clusterer.py`
- `app/dedup/canonicalize.py`
- `app/enrichers/ticker_extractor.py`
- `app/enrichers/asset_tagger.py`
- `app/enrichers/quant_tagger.py`
- `app/db/models.py`
- `docs/DATA_SCHEMA.md`
- `tests/test_dedup.py`
- New enrichment tests

Implementation scope:

- Deterministic deduplication baseline.
- Event model and event-item relationships.
- Rule-based ticker, asset-class, source, and quant-theme tagging.
- Confidence fields and explainable tag provenance.

Must not implement:

- LLM tagging.
- Ranking/heat scores.
- Report generation.
- Email sending.
- Scheduler.
- Dashboard business views beyond fixtures.

Definition of done:

- Similar fixture items cluster into a single event.
- Distinct items remain separate.
- Tags are reproducible and include provenance.
- False positives are handled conservatively.

Required tests:

- Exact duplicate clustering.
- Near-duplicate title/link clustering.
- Distinct-event separation.
- Ticker ambiguity cases.
- Asset class and quant theme tagging.

Commands before completion:

```bash
python -m compileall -q app tests
pytest tests/test_dedup.py
pytest
ruff check .
mypy app tests
```

## Phase 6: Ranking And Heat

Goal: rank events by market importance and heat using deterministic, explainable rules.

Dependencies: Phase 5.

Likely files to change:

- `app/ranking/prefilter.py`
- `app/ranking/ranker.py`
- `app/db/models.py`
- `docs/DATA_SCHEMA.md`
- `tests/test_ranking.py`

Implementation scope:

- Prefilter low-value noise.
- Score events by source credibility, recency, duplication/coverage, asset relevance, macro/Fed/SEC importance, options/ETF relevance, GitHub/research signal, and community heat.
- Store rank score components and explanations.

Must not implement:

- LLM summaries.
- Email report generation.
- Scheduler.
- Personalized financial advice or trade recommendations.

Definition of done:

- Ranking is deterministic for a fixed fixture set.
- Score components are visible and testable.
- Market-sensitive language remains descriptive, not advisory.
- Heat cannot be driven by one untrusted signal alone.

Required tests:

- Ranking order from representative fixtures.
- Recency decay.
- Source credibility weighting.
- Community heat cap.
- Explanation field completeness.

Commands before completion:

```bash
python -m compileall -q app tests
pytest tests/test_ranking.py
pytest
ruff check .
mypy app tests
```

## Phase 7: DeepSeek Summarization

Goal: summarize ranked events in English through DeepSeek using an OpenAI-compatible client and strict structured outputs.

Dependencies: Phase 6.

Likely files to change:

- `app/llm/client.py`
- `app/llm/schemas.py`
- `app/llm/prompts.py`
- `app/llm/summarize.py`
- `docs/LLM_PROMPTS.md`
- `.env.example`
- New LLM tests

Implementation scope:

- DeepSeek-compatible client configuration using `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, and `DEEPSEEK_MODEL`.
- Structured output schemas for event summaries and report sections.
- Prompt rules that cite source IDs/URLs and preserve uncertainty.
- Mocked LLM tests only.

Must not implement:

- Real LLM calls in tests.
- Hallucinated facts, uncited claims, investment advice, price targets, or trading instructions.
- Email sending or scheduler.

Definition of done:

- Summaries are generated only from stored event/source references.
- Missing evidence results in explicit insufficient-evidence output.
- Structured schemas validate model output.
- LLM failures leave ranked events available for manual review.

Required tests:

- Prompt construction from fixtures.
- Structured response validation.
- Missing evidence behavior.
- Mocked DeepSeek success and failure.
- Anti-hallucination guard fields.

Commands before completion:

```bash
python -m compileall -q app tests
pytest
ruff check .
mypy app tests
```

## Phase 8: Daily HTML Email Report

Goal: generate a detailed daily pre-market HTML email report from ranked, summarized events.

Dependencies: Phase 7.

Likely files to change:

- `app/reports/generator.py`
- `app/reports/templates.py`
- `templates/email_report.html`
- `app/email/sender.py`
- `app/email/smtp_sender.py`
- `app/email/resend_sender.py`
- `docs/RUNBOOK.md`
- `tests/test_report_generation.py`
- `tests/test_email_sender.py`

Implementation scope:

- Report data model and HTML rendering.
- Pre-market report sections for market overview, macro/Fed, ETFs/options, SEC, research, GitHub/community, and watchlist.
- Email preview and dry-run delivery path.
- SMTP/Resend interfaces behind explicit configuration.

Must not implement:

- Automatic scheduled sending.
- Sending without explicit user configuration.
- Uncited claims, full-text reproduction, or investment advice.
- Dashboard business views beyond report preview fixtures.

Definition of done:

- HTML report renders from fixtures.
- Every event summary includes source references.
- Email sender can run in dry-run/preview mode without network calls.
- Delivery providers are tested with mocks only.

Required tests:

- Report section ordering.
- Template rendering with empty and full fixtures.
- Source citation presence.
- Email dry-run behavior.
- Mock SMTP/Resend send behavior.

Commands before completion:

```bash
python -m compileall -q app tests
pytest tests/test_report_generation.py tests/test_email_sender.py
pytest
ruff check .
mypy app tests
```

## Phase 9: Local FastAPI Dashboard

Goal: render a local dashboard for today's brief, feeds, report archive, report detail, and source status.

Dependencies: Phase 8.

Likely files to change:

- `app/web/routes.py`
- `app/web/filters.py`
- `app/web/view_models.py`
- `templates/base.html`
- `templates/dashboard_today.html`
- `templates/feed.html`
- `templates/reports.html`
- `templates/report_detail.html`
- `templates/source_status.html`
- `static/css/main.css`
- `static/js/main.js`
- `.agents/skills/dashboard-qa/SKILL.md`
- New dashboard route/template tests

Implementation scope:

- Server-rendered dashboard routes.
- Filters for date, source, ticker, asset class, and quant theme.
- Source status page that does not leak secrets.
- Report archive backed by local storage.
- Empty-state and fixture-backed views.

Must not implement:

- Hosted multi-user authentication.
- React, Next.js, Redis, Celery, PostgreSQL, or cloud deployment.
- Auto-refresh that triggers external API calls.
- Any secret display in HTML or logs.

Definition of done:

- Dashboard loads locally from fixture/local database data.
- Empty states are readable.
- Source status exposes failures without leaking secrets.
- Templates render consistently for desktop and mobile widths.

Required tests:

- Route response tests.
- Template render tests.
- Filter behavior tests.
- Source status redaction tests.
- Empty database dashboard tests.

Commands before completion:

```bash
python -m compileall -q app tests
pytest
ruff check .
mypy app tests
```

## Phase 10: Scheduling, Retention, And Operations

Goal: wire the daily pipeline, 30-day history retention, cleanup, and operational runbook.

Dependencies: Phase 9.

Likely files to change:

- `app/jobs/run_daily.py`
- `app/jobs/scheduler.py`
- `app/jobs/cleanup.py`
- `app/core/config.py`
- `app/db/models.py`
- `docs/RUNBOOK.md`
- `docs/CODEX_TASKS.md`
- New job and retention tests

Implementation scope:

- Daily pre-market job orchestration.
- Manual run command.
- Optional local scheduler.
- 30-day retention cleanup for items, events, reports, and delivery logs.
- Operational failure handling and source coverage notes.

Must not implement:

- Cloud deployment automation.
- Background infrastructure such as Celery, Redis, or external queues.
- Sending email without explicit configuration and user-controlled recipients.
- Retaining full text or premium content beyond allowed metadata.

Definition of done:

- Manual daily run works locally with configured sources or fixtures.
- Scheduler is optional and disabled unless configured.
- Cleanup preserves only the configured history window.
- Runbook explains setup, manual run, scheduler, retention, and recovery.

Required tests:

- Daily job orchestration with fixture collectors.
- Partial source failure handling.
- Scheduler disabled-by-default behavior.
- 30-day retention cleanup.
- Report generation despite noncritical source failures.

Commands before completion:

```bash
python -m compileall -q app tests
pytest
ruff check .
mypy app tests
```

## Future Backlog After Phase 10

- Additional source adapters only after terms review.
- Better ranking calibration from personal feedback.
- Export/import of local configuration minus secrets.
- Optional local-only notification channels.
- Packaging improvements for personal machine setup.
