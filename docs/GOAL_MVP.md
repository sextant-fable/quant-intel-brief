# Goal Mode MVP Contract

This document governs Goal Mode work for implementing the MVP of Quant Intel Brief from Phase 0 through Phase 10. `PLANS.md` remains the authoritative implementation plan for phase numbering, dependencies, scope, files likely to change, tests, and definitions of done.

## Execution Rule

Codex must execute phases sequentially from Phase 0 through Phase 10, one phase at a time.

Within an explicitly approved Goal Mode run, the user pre-authorizes Codex to split the active phase into smaller internal stages. After each internal stage passes validation and secret-safety checks, Codex must automatically create a stage commit and push it to the current tracked branch.

At every Phase 0 through Phase 10 boundary, Codex must perform a mandatory audit checkpoint after successful validation and any required checkpoint commit/push. In Goal Mode, the user pre-authorizes Codex to continue automatically to the next phase after that checkpoint passes.

Codex must stop only for a true blocker: failed validation that cannot be fixed within the active scope, external state, credentials, legal/source-access uncertainty, missing user decisions, unavailable required tooling that cannot be safely installed or worked around, forbidden files that cannot be safely excluded, or repeated failures that cannot be resolved without changing approved scope.

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

Codex must not declare a phase complete if tests fail. If any validation command fails or cannot run, Codex must diagnose the issue, attempt reasonable fixes within the active phase scope, and rerun validation. Codex must stop only when the failure is blocked by external state, credentials, legal/source-access uncertainty, missing user decisions, unavailable required tooling that cannot be safely installed or worked around, or repeated failures that cannot be resolved without changing the approved scope.

## Git Checkpoint Policy

Codex must inspect `git status` before starting each phase, before each internal stage commit, and before completing each phase.

Codex must not commit or push if validation commands fail. If validation fails, Codex must attempt to fix the issue first, then rerun validation. Failed or partially fixed states must remain uncommitted unless the user explicitly requests a diagnostic checkpoint.

Codex must not commit or push secrets, `.env`, runtime DB files, generated reports, cookies, tokens, local browser profiles, or private artifacts.

At each internal stage checkpoint, Codex must inspect changed files and summarize the diff before committing when practical. At each phase checkpoint, Codex must show changed files and summarize diffs before stopping for user review.

After internal stage tests pass, Codex is pre-authorized to commit and push. After phase-boundary tests pass, Codex must complete any required checkpoint commit/push and then continue automatically to the next phase unless a true blocker is present.

The user's Goal Mode approval authorizes internal stage commits, phase checkpoint commits, and automatic phase-to-phase progression.

Only after a successful commit should Codex push to the current tracked branch.

If no git remote or upstream branch exists, Codex must stop and report the required setup command instead of guessing.

Commit messages should follow:

```text
Phase N: <short phase name>
```

For internal stage commits, use the active phase number and a short stage name, for example `Phase 2: Add FRED fixture parser`.

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
- Commit SHA and push status for automatic stage or phase checkpoint commits.
- Remaining risks or follow-up notes.
- Whether Codex continued automatically to the next phase or stopped because of a true blocker.
