---
name: financial-source-adapter
description: Instructions for adding or updating compliant source collector adapters.
---

# Financial Source Adapter Skill

Use this skill when adding or updating a source collector in `app/collectors/`.

## Scope

- Define one adapter per source.
- Keep authentication and rate-limit settings in configuration.
- Normalize raw source data into the shared item schema documented in `docs/DATA_SCHEMA.md`.
- Record source URL, fetched timestamp, original publication timestamp, author/publisher metadata, and source-specific IDs when available.

## Boundaries

- Do not bypass paywalls or platform access controls.
- Do not commit API keys, tokens, cookies, or session exports.
- Do not mix ranking or LLM summarization into collectors.
- Do not store full text unless source terms and user authorization explicitly permit it.

## Acceptance Checklist

- Source configuration is documented in `.env.example` and `docs/DATA_SOURCES.md`.
- Failure modes and retry behavior are documented.
- Tests cover parsing, empty responses, duplicate IDs, and rate-limit responses.
