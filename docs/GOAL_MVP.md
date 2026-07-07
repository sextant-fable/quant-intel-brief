# Goal Mode MVP Contract

This document governs Goal Mode work for implementing the MVP of Quant Intel Brief from Phase 0 through Phase 10. `PLANS.md` remains the authoritative implementation plan for phase numbering, dependencies, scope, files likely to change, tests, and definitions of done.

## Execution Rule

Codex must execute phases sequentially from Phase 0 through Phase 10, one phase at a time.

After every phase, Codex must stop for a mandatory review checkpoint and wait for the user's explicit reply:

```text
continue
```

Codex must not proceed to the next phase without that exact user approval.

## Mandatory Phase Gate

Before starting each phase, Codex must:

- Read `AGENTS.md`.
- Read `PLANS.md`.
- Read this file.
- Read relevant `docs/*.md`.
- Read relevant `.agents/skills/*/SKILL.md`.
- State the phase being started and confirm it matches `PLANS.md`.
- State what will remain out of scope for that phase.

Before declaring each phase complete, Codex must run:

```bash
python -m compileall -q app tests
pytest
ruff check .
mypy app tests
```

Codex must not declare a phase complete if tests fail. If any validation command cannot run, Codex must stop, explain why, and wait for user direction.

## Git Checkpoint Policy

Codex must inspect `git status` before starting each phase and before completing each phase.

Codex must not commit or push if validation commands fail.

Codex must not commit or push secrets, `.env`, runtime DB files, generated reports, cookies, tokens, local browser profiles, or private artifacts.

At the phase checkpoint, Codex must show changed files and summarize diffs.

After tests pass, Codex must stop and wait for the user's review.

Only after the user explicitly approves the checkpoint should Codex create a phase commit.

Only after a successful commit should Codex push to the current tracked branch.

If no git remote or upstream branch exists, Codex must stop and report the required setup command instead of guessing.

Commit messages should follow:

```text
Phase N: <short phase name>
```

Codex must not squash or rewrite history unless the user explicitly requests it.

## Safety Rules

- No real external API calls in tests.
- No real email sending.
- No paywall bypass.
- No premium-source full-text processing or storage.
- No secrets, cookies, tokens, API keys, or credentials committed.
- No generated reports, runtime databases, or local private artifacts committed.
- No full-text copyrighted storage by default.
- No investment advice, trade instructions, price targets, or performance guarantees.

## Documentation Rule

Docs must be updated in the same phase when behavior changes. At minimum, update the relevant file among:

- `README.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/PROJECT_SPEC.md`
- `docs/DATA_SOURCES.md`
- `docs/DATA_SCHEMA.md`
- `docs/LLM_PROMPTS.md`
- `docs/LEGAL_BOUNDARIES.md`
- `docs/CODEX_TASKS.md`
- `docs/RUNBOOK.md`

Do not change `PLANS.md` during implementation unless there is a direct contradiction, legal boundary issue, or user-approved scope change. If `PLANS.md` changes, Codex must explain exactly why.

## Checkpoint Report Format

At the end of each phase, Codex must report:

- Phase completed.
- Files changed.
- Tests and validation commands run.
- Any skipped checks and why.
- Confirmation that no forbidden actions occurred.
- Remaining risks or follow-up notes.
- A clear request for the user's `continue` reply before the next phase.
