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

Phase 2 and Phase 3 adapters may require local `.env` credentials for real personal runs later, but no live-run command is provided yet. Missing keys, user-agent settings, access tokens, or user IDs should return collector failure states before HTTP is attempted.

Premium metadata intake is disabled by default. For tests and future local runs, it accepts explicit metadata records only and rejects body/content/transcript/HTML/Markdown fields.

## Incident Notes

- Source failures should degrade report coverage, not crash the entire daily run.
- Email delivery should require explicit configuration and log delivery results.
- LLM failures should preserve raw ranked items for manual review.
