# Quant Intel Brief

Quant Intel Brief is a planned local-first personal intelligence system for quantitative finance, markets, research, developer ecosystems, and platform signals.

The project is designed to run on a personal machine first, with local SQLite storage and explicit user-controlled credentials. It is not a hosted multi-user service.

## Current Phase

Phase 10 local job orchestration, retention cleanup, and optional scheduler boundaries are implemented. The app has metadata-only collectors through Phase 3, Phase 4 storage hygiene, Phase 5 clustering/tagging, Phase 6 ranking, mocked source-grounded LLM summarization, fixture-rendered reports, email preview/dry-run delivery, local dashboard pages, tested local operations jobs, and a manual collect-once command/page for public, official, market API, community, and platform sources.

## Intended Workflow

1. Collect items from configured public and permitted private sources.
2. Extract readable content and metadata.
3. Enrich items with tickers, assets, topics, and quant-relevance tags.
4. Deduplicate and cluster related stories.
5. Rank items by relevance, novelty, credibility, and user preferences.
6. Summarize with LLMs using structured schemas.
7. Generate dashboard and email reports.

## Quick Start

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Checks

```bash
python -m compileall -q app tests
pytest
ruff check .
mypy app tests
```

## Running The App

Run the local app shell with:

```bash
uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Available local routes:

- `GET /health`
- `GET /status/sources`
- `GET /settings/public`
- `GET /dashboard/today`
- `GET /feed`
- `GET /reports`
- `GET /reports/{report_id}`
- `GET /sources`
- `GET /settings/sources`
- `POST /settings/sources`

Collectors do not run automatically from the app shell. Dashboard pages read only local database data.

Run one local empty daily job manually with:

```bash
python -m app.jobs.run_daily
```

The manual job creates a local draft report by default. It does not run live collectors, call an LLM, or send email unless future code passes explicit configured inputs.

Seed local demo data for visual review with:

```bash
python -m app.jobs.seed_demo
```

This writes simulated Fed, ETF/options, SEC, arXiv, GitHub, and Reddit metadata into local SQLite storage so the dashboard looks populated without external API calls.

Run selected live collectors manually with:

```bash
python -m app.jobs.collect_once --sources rss,sec_edgar,arxiv,github,fred
```

Supported source names are `rss`, `sec_edgar`, `arxiv`, `github`, `fred`, `newsapi`, `gdelt`, `alphavantage`, `finnhub`, `reddit`, `youtube`, `x_api`, `stackexchange`, and `quantconnect`.

This command is user-triggered only. It writes metadata and source status rows into local SQLite, but it does not run the scheduler, call an LLM, generate summaries, or send email. You can also configure and run the same manual collection from:

```text
http://127.0.0.1:8001/settings/sources
```

Configure source targets and credentials in `.env` or from the local source settings page:

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
ALPHAVANTAGE_API_KEY=
FINNHUB_API_KEY=
REDDIT_ACCESS_TOKEN=
REDDIT_USER_AGENT=
YOUTUBE_API_KEY=
X_BEARER_TOKEN=
STACKEXCHANGE_SITE=quant
QUANTCONNECT_USER_ID=
QUANTCONNECT_TOKEN=
```

For LLM providers, use OpenAI-compatible settings in `.env`:

```bash
LLM_PROVIDER=deepseek
LLM_API_KEY=
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

DeepSeek, GLM, GPT-compatible gateways, and other OpenAI-compatible APIs can use the same fields by changing provider, base URL, model, and key. `DEEPSEEK_*` settings remain supported as legacy aliases.

You can also configure the same values from the local dashboard:

```text
http://127.0.0.1:8001/settings/llm
```

The settings page saves the API key into the local `.env` file and does not display it after saving.

## Repository Layout

- `.agents/skills/`: local Codex skill instructions for source adapters, report checks, and dashboard QA.
- `.codex/`: local Codex configuration.
- `docs/`: product and engineering specifications.
- `app/`: application package.
- `templates/`: dashboard and email HTML templates.
- `static/`: CSS, JavaScript, and vendored UI assets.
- `data/`: local runtime data and generated reports.
- `tests/`: test suite placeholders.

## Status

Phase 10 is complete. The current backlog milestone is manual source collection for RSS, SEC EDGAR, arXiv, GitHub, and FRED.
