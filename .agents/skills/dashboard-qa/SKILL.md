---
name: dashboard-qa
description: Instructions for checking dashboard routes, templates, filters, and static assets.
---

# Dashboard QA Skill

Use this skill when changing dashboard routes, templates, filters, or static assets.

## Review Focus

- Dashboard loads with an empty dataset and with realistic fixture data.
- Filters are predictable and preserve user context.
- Source status pages expose failures without leaking secrets.
- Layout remains usable on desktop and mobile widths.

## Acceptance Checklist

- `templates/` render without missing variables.
- `static/` assets are local or intentionally vendored.
- Tests cover route responses and view-model formatting once routes are implemented.
