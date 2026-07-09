# Repository Content Policy

This repository is public-safe by design. It should contain source code, generic prompt templates, and public documentation only.

## Upload Allowed

- Source code under `apps/` and `tools/`.
- Generic prompt templates under `prompts/`.
- Public documentation under `docs/`.
- Database schema migrations under `db/migrations/` when they contain schema only.

## Upload Forbidden

- API keys, OAuth tokens, client secrets, service account files.
- `.env` or any environment file.
- Raw analytics exports from GSC, GA4, PageSpeed, CrUX, SERP tools, or any paid tools.
- SQLite, Postgres dumps, CSV/TSV exports, reports, screenshots, or customer data.
- Internal AI memory, project progress, project plans, handoff logs, backlog, and private working files.
- Prompt files containing real metrics, URLs from private analysis, API responses, or business-sensitive conclusions.

## Prompt Safety Rule

Prompts committed to GitHub must be generic. They can define:

- Role.
- Required local data sources.
- Analysis method.
- Output format.
- Quality bar.
- Safety constraints.

They must not contain:

- Real metric values.
- Real exports.
- API tokens.
- Private client data.
- Hardcoded conclusions from local analytics.

## Pre-Push Checklist

Run:

```powershell
git status --short --ignored
git check-ignore -v .env data .ai PROJECT_STATUS.md CHANGELOG.md
```

Only push after confirming private files are ignored.
