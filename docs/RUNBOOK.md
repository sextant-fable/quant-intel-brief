# Runbook

Operational instructions will be completed as features are implemented.

## Local Setup

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Planned Commands

```bash
python -m compileall -q app tests
quant-intel-brief
pytest
ruff check .
mypy app tests
```

## App Shell

Run the local app shell:

```bash
uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Useful local system routes:

- `GET /health`
- `GET /status/sources`
- `GET /settings/public`

These routes expose only local system/status information. They do not run collectors, call external APIs, call an LLM, or send email.

## Collector Checks

The RSS adapter and Phase 2/3 collectors are available as library components and are covered by fixture/mocked tests:

```bash
pytest tests/test_collectors.py
```

Collectors are not wired to a scheduler or dashboard action yet. Do not use live feeds in tests; add local fixtures or `respx` mocks instead.

Phase 2 and Phase 3 adapters may require local `.env` credentials for real personal runs. Missing keys, user-agent settings, access tokens, or user IDs should return collector failure states before HTTP is attempted.

Premium metadata intake is disabled by default. For tests and future local runs, it accepts explicit metadata records only and rejects body/content/transcript/HTML/Markdown fields.

## Phase 4 Normalization Checks

Canonicalization, compact-excerpt extraction boundaries, source references, and 30-day retention metadata are covered by:

```bash
pytest tests/test_extraction_boundaries.py
```

Article extraction defaults to metadata-only behavior. Full-text storage attempts should raise an error instead of silently persisting content.

## Phase 5 Dedup And Tagging Checks

Event clustering and rule-based tagging are covered by:

```bash
pytest tests/test_dedup.py tests/test_enrichers.py
```

The Phase 5 baseline is deterministic and conservative. It does not rank events, call an LLM, generate reports, or drive dashboard business views.

## Phase 6 Ranking Checks

Deterministic ranking and heat scoring are covered by:

```bash
pytest tests/test_ranking.py
```

Ranking explanations are informational importance notes only. They must not contain trade instructions, price targets, or personalized recommendations.

## Phase 7 LLM Summary Checks

OpenAI-compatible structured summarization is covered by mocked tests:

```bash
pytest tests/test_llm_summarization.py
```

Tests must use fake clients and make no real LLM calls. Local future runs should use `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL`; legacy `DEEPSEEK_*` aliases still work. Real API keys must stay in `.env` and never be committed.

Local dashboard configuration is available at:

```text
http://127.0.0.1:8000/settings/llm
```

Use this page to choose DeepSeek, GLM/Z.AI, Kimi/Moonshot, or a custom OpenAI-compatible provider. The page writes to the local `.env` file, leaves saved API keys hidden, and does not test-call the provider. Legacy `DEEPSEEK_API_KEY` values are recognized and can be migrated by saving the page.

## Manual Collect Once

Run selected collectors manually:

```bash
python -m app.jobs.collect_once --sources rss,finance_news_mcp,sec_edgar,arxiv,github,fred,newsapi,gdelt,alphavantage,finnhub,reddit,youtube,x_api,stackexchange,quantconnect
```

The command writes metadata-only records and source statuses into local SQLite. It does not run the scheduler, call an LLM, generate summaries, or send email.

The same manual run can be started from the local dashboard:

```text
http://127.0.0.1:8000/settings/sources
```

Use `Save Source Settings` to update local `.env` values. Use `Run Collect Once` to run only the checked sources. The page hides saved secrets after saving and shows `saved` next to stored source keys.

### Finance News MCP

Run the third-party MCP in its own terminal and environment:

```bash
git clone https://github.com/jvenkatasandeep/finance-news-mcp.git
cd finance-news-mcp
uv sync
uv run fastmcp run main.py:mcp --transport http --host 127.0.0.1 --port 8002
```

Then save these local app settings:

```bash
FINANCE_NEWS_MCP_URL=http://127.0.0.1:8002/mcp
FINANCE_NEWS_MCP_SOURCES=bloomberg,wsj,cnbc,marketwatch,ft,seekingalpha
FINANCE_NEWS_MCP_ITEMS_PER_SOURCE=20
```

The app calls `get_latest_finance_news` once per configured publisher so each publisher has an independent source quota and status. If the MCP is stopped or malformed, those publishers fail noncritically. Only titles, links, public descriptions, publishers, and publication timestamps are retained.

## Manual AI Report Generation

After collection, open:

```text
http://127.0.0.1:8000/reports
```

Use `Generate AI Report` to summarize top-ranked local content with the configured OpenAI-compatible provider. This is a user-triggered LLM call. It does not send email, start the scheduler, bypass paywalls, or process premium full text.

The Feed groups items by the exact collection run. Each batch shows its first three items by default; use `View all / 展开全部` for the remainder. Batch headers show US Eastern time (EST/EDT automatically) and browser-local time. The database stores UTC, and report freshness remains based on source `published_at` rather than collection time.

New reports contain up to 10 ranked events. English is primary; concise Simplified Chinese translations are included for the headline, factual takeaway, market relevance, and watch points. Existing reports created before this format remain readable as legacy reports.

Daily report candidates are selected by real publication time, not collection time. Defaults are 20 candidates per source, a 72-hour window for news/community content, 30 days for SEC/arXiv, two Top 10 entries per source, and three per market section. Empty market sections say that no qualifying new event was found instead of reusing stale content. Older Stack Exchange questions appear only under the Feed page's long-term Research Feed.

## One-Click Brief Refresh

Open the Today page and use `Refresh Brief`:

```text
http://127.0.0.1:8000/dashboard/today
```

This explicit action selects only sources with the minimum local configuration, runs them once, and generates a new Top 10 report from local content. Public arXiv, GitHub, GDELT, and Stack Exchange adapters may run without keys; credential-gated sources run only when their local credentials are present. The action does not send email or enable automatic scheduling.

Each Top 10 event displays its cited original-source links. `Refresh Brief` collects and generates a report together; use `Generate AI Report` on Reports when you only want to summarize data already stored locally.

Useful local `.env` settings:

```bash
RSS_FEED_URLS=
SEC_USER_AGENT=your-app-name your-email@example.com
SEC_CIK=0000320193
ARXIV_SEARCH_QUERY=cat:q-fin*
GITHUB_QUERY=quant finance language:Python
GITHUB_TOKEN=
FRED_API_KEY=
FRED_SERIES_ID=FEDFUNDS
NEWSAPI_KEY=
NEWSAPI_QUERY=quant finance OR ETF OR options
GDELT_QUERY=quant finance
ALPHAVANTAGE_API_KEY=
ALPHAVANTAGE_TOPICS=financial_markets,economy_macro
FINNHUB_API_KEY=
FINNHUB_CATEGORY=general
REDDIT_ACCESS_TOKEN=
REDDIT_USER_AGENT=
REDDIT_QUERY=quant finance OR algotrading
REDDIT_SUBREDDIT=
YOUTUBE_API_KEY=
YOUTUBE_QUERY=quant finance
X_BEARER_TOKEN=
X_QUERY=quant finance lang:en
STACKEXCHANGE_KEY=
STACKEXCHANGE_QUERY=quant finance
STACKEXCHANGE_SITE=quant
QUANTCONNECT_USER_ID=
QUANTCONNECT_TOKEN=
QUANTCONNECT_ORGANIZATION_ID=
```

Collector command tests use injected fake collectors and mocked adapter tests only:

```bash
pytest tests/test_collect_once.py tests/test_collectors.py
```

## Premium Sources

Use the local premium reading queue at:

```text
http://127.0.0.1:8000/premium
```

The page supports:

- public RSS metadata collection into a premium reading queue;
- manual WSJ/Bloomberg-style reading links;
- user-authored notes, tickers, importance scores, and read status;
- LLM-ready context made only from titles, links, public summaries, and user notes.

The page does not use login cookies, bypass paywalls, scrape premium full text, or store copyrighted article bodies. Do not paste full article text into notes.

## Phase 8 Report And Email Checks

Daily HTML report rendering and email preview/dry-run behavior are covered by:

```bash
pytest tests/test_report_generation.py tests/test_email_sender.py
```

Email tests use fake SMTP and `httpx.MockTransport` only. Do not send real email in tests, and do not commit generated reports from `data/reports/`.

## Phase 9 Dashboard Checks

Local dashboard routes, filters, static assets, and source status redaction are covered by:

```bash
pytest tests/test_dashboard_routes.py
```

Dashboard pages read the local database only. They must not trigger collectors, LLM calls, email delivery, or scheduler jobs.

## Phase 10 Operations Checks

Daily job orchestration, retention cleanup, and scheduler boundaries are covered by:

```bash
pytest tests/test_jobs.py
```

Run a local empty daily job manually with:

```bash
python -m app.jobs.run_daily
```

The default manual command creates a local draft report without live collectors, LLM calls, or email sending. Scheduler wiring is disabled unless `ENABLE_SCHEDULER=true`; use `DAILY_RUN_TIME=HH:MM` and `RETENTION_DAYS=30` for local operations tuning.

## Demo Seed

Populate the local dashboard with deterministic demo data:

```bash
python -m app.jobs.seed_demo
```

The seed command writes simulated Fed, ETF/options, SEC, arXiv, GitHub, and Reddit metadata plus a demo report. It makes no external API calls and stores metadata-only demo excerpts.

Demo seeding is covered by:

```bash
pytest tests/test_seed_demo.py
```

## Incident Notes

- Source failures should degrade report coverage, not crash the entire daily run.
- Email delivery should require explicit configuration and log delivery results.
- LLM failures should preserve raw ranked items for manual review.
