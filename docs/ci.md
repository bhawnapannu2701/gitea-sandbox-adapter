# CI

Workflow file: `.github/workflows/ci.yml`

Configured jobs:

- Fast quality/unit job on Ubuntu and Windows with Python 3.11 and 3.12
- Linux Docker integration job with generated local `.env`, pinned images,
  start, populate, API validation, snapshot, restore, integration pytest, and
  stop

Workflow controls:

- `permissions: contents: read`
- concurrency cancellation for stale branch or pull request runs
- no repository secrets required
- failure diagnostics are generated with the adapter's redaction layer
- raw Docker Compose logs are captured only temporarily on the runner
- only `diagnostics/diagnose.json` and `diagnostics/compose.redacted.log` are
  eligible for artifact upload
- `.env`, tokens, raw logs, cookies, Playwright authentication state, snapshots,
  Gitea archives, PostgreSQL dumps, and credential-bearing logs are not uploaded

Current status:

- Workflow configuration was created and locally inspected.
- GitHub-hosted execution has not run because no commit, push, pull request, or
  merge was performed in this session.
- CI pass is not claimed.
