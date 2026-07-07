# Codex Tasks

Use this document to break future work into safe implementation tasks.

## Scaffold Status

- [x] Create repository structure.
- [x] Add documentation placeholders.
- [x] Add source adapter skill placeholders.
- [x] Add application package placeholders.
- [x] Add template and static asset placeholders.
- [x] Add test placeholders.

## Future Task Backlog

- [x] Define SQLModel models and migration-ready table metadata.
- [x] Implement configuration loading from `.env`.
- [x] Wire a fixture-only app factory and health/status routes.
- [x] Add Phase 0 schema and app shell tests.
- [ ] Add normalized item schema tests for collector persistence.
- [ ] Implement one public collector end to end with mocked HTTP tests.
- [ ] Implement deduplication baseline.
- [ ] Implement ranking baseline.
- [ ] Implement report generation from fixtures only.
- [ ] Implement dashboard route from fixtures.
- [ ] Implement email preview before sending.

## Phase 0 Done Criteria

- Configuration loads without secrets committed.
- SQLite database schema is explicit and migration-ready.
- App factory can start locally with fixture-only health/status responses.
- Tests do not make external API calls.
