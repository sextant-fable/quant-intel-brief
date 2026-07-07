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

## Phase 0 App Shell

Run the local fixture-only app shell:

```bash
uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Useful local system routes:

- `GET /health`
- `GET /status/sources`
- `GET /settings/public`

These routes expose only local fixture/status information. They do not run collectors, call external APIs, call an LLM, or send email.

## Incident Notes

- Source failures should degrade report coverage, not crash the entire daily run.
- Email delivery should require explicit configuration and log delivery results.
- LLM failures should preserve raw ranked items for manual review.
