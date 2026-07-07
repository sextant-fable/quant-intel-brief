# Quant Intel Brief

Quant Intel Brief is a planned local-first personal intelligence system for quantitative finance, markets, research, developer ecosystems, and platform signals.

The project is designed to run on a personal machine first, with local SQLite storage and explicit user-controlled credentials. It is not a hosted multi-user service.

## Current Phase

Phase 8 daily HTML report generation and email preview/dry-run delivery are implemented. The app has metadata-only collectors through Phase 3, Phase 4 storage hygiene, Phase 5 clustering/tagging, Phase 6 ranking, mocked source-grounded LLM summarization, and fixture-rendered reports. Scheduling and dashboard business views are intentionally not implemented yet.

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

Available fixture-only system routes:

- `GET /health`
- `GET /status/sources`
- `GET /settings/public`

Collectors do not run automatically from the app shell. Phase 1 through Phase 3 adapters are exercised through tests and future job wiring.

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

Phase 8 is complete. The next milestone is Phase 9: local dashboard report views.
