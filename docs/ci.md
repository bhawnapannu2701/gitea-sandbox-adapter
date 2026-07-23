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
- pull requests run CI
- direct pushes to `main` run CI
- ordinary pushes to feature branches do not create a duplicate CI run when a
  pull request is already open
- no repository secrets required
- failure diagnostics are generated with the adapter's redaction layer
- raw Docker Compose logs are captured only temporarily on the runner
- only `diagnostics/diagnose.json` and `diagnostics/compose.redacted.log` are
  eligible for artifact upload
- `.env`, tokens, raw logs, cookies, Playwright authentication state, snapshots,
  Gitea archives, PostgreSQL dumps, and credential-bearing logs are not uploaded

Current status:

- The first GitHub-hosted CI executions for pull request #2 ran on
  2026-07-23 and failed.
- The quality matrix failed during unit tests because pytest was configured to
  create `.gitea-sandbox/pytest-tmp`, but a clean GitHub runner does not have
  the ignored `.gitea-sandbox` parent directory.
- The Linux Docker integration job passed Docker Compose verification,
  dependency installation, CI `.env` generation, Compose configuration, sandbox
  start, deterministic population, API validation, and snapshot creation before
  restore failed.
- Restore failed because it performs real Playwright browser validation and the
  GitHub-hosted runner did not yet have the Chromium browser binary installed
  for the Python Playwright package.
- GitHub-hosted CI run #3 passed on the corrected pull-request commit.
- Quality jobs passed on Ubuntu and Windows with Python 3.11 and 3.12.
- Linux Docker integration passed.
- The Docker job successfully completed Playwright Chromium installation,
  sandbox start, deterministic population, API validation, snapshot, forced
  restore, integration pytest, and cleanup.
- Raw diagnostics were not uploaded because the successful job did not need
  failure diagnostics.
