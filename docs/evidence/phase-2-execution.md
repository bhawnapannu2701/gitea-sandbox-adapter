# Phase 2 Execution Evidence

This file records sanitized evidence from the current Phase 2 implementation
run only. It must not contain passwords, access tokens, Authorization headers,
cookies, personal absolute filesystem paths, or unverified claims.

## Preflight Gate

Date: 2026-07-23

Sanitized working directory: `<repo-root>`

Current branch before Phase 2 branch creation: `main`

Git status before Phase 2 branch creation: clean

Configured Git remote:

- `origin https://github.com/bhawnapannu2701/gitea-sandbox-adapter.git`

Latest commits:

- `278221f` Merge pull request #1 from `bhawnapannu2701/feat/phase-1-foundation`
- `d051dee` feat: add Phase 1 Python CLI foundation
- `d1f1455` Initial commit

Tool versions:

- Python: `3.12.13` from the project virtual environment
- Git: `2.51.0.windows.1`
- Docker client: `28.3.3`
- Docker server: Docker Desktop `4.45.0`, Engine `28.3.3`
- Docker Compose: `v2.39.2-desktop.1`
- Docker context: `desktop-linux`

Docker daemon reachability:

- A sandboxed Docker daemon check could not access the Docker named pipe.
- The approved Docker reachability check outside the sandbox succeeded.

Port checks:

- Host TCP port `3000`: no listener found.
- Host TCP port `2222`: no listener found.

Pinned image availability:

- `docker.gitea.com/gitea:1.27.0-rootless`
  - Pull result: succeeded
  - Image ID: `sha256:414ba5b2b1163480e9ed4213a989cd798579cfa88582a2359303273009b2b852`
  - Repository digest:
    `docker.gitea.com/gitea@sha256:414ba5b2b1163480e9ed4213a989cd798579cfa88582a2359303273009b2b852`
- `docker.io/library/postgres:16.14-bookworm`
  - Pull result: succeeded
  - Image ID: `sha256:92620daddcd947f8d5ab5ba66e848702fe443d87fed30c4cea8e389fd78dfc55`
  - Repository digest:
    `postgres@sha256:92620daddcd947f8d5ab5ba66e848702fe443d87fed30c4cea8e389fd78dfc55`

Branch created for implementation:

- `feat/phase-2-complete`

## Configuration and Compose Gate

Files created or updated:

- `compose.yaml`
- `.env.example`
- `.gitignore`
- `fixtures/gitea_seed.json`
- Core runtime modules under `src/gitea_sandbox_adapter/`

Gitea image healthcheck command inspection:

- Command inspection of the pinned rootless image found:
  - `/usr/bin/curl`
  - `/usr/bin/wget`
  - `/bin/busybox`
  - `/usr/local/bin/gitea`
- `compose.yaml` uses `curl -fsS http://localhost:3000/api/healthz` for the
  Gitea healthcheck.

Ignored local runtime configuration:

- `.env` generated with Python `secrets` module.
- Generated secret values were not printed.
- `git check-ignore .env` returned `.env`.
- `git status --short -- .env` returned no output.

Compose validation:

- `docker compose --env-file .env -f compose.yaml -p gitea_sandbox_adapter config --quiet`
  exit code: `0`

Focused secret-pattern scan:

- Command: `rg -n -i "(authorization:\\s*(bearer|token|basic)\\s+[A-Za-z0-9+/._=-]{12,}|(password|passwd|token|secret|key)\\s*=\\s*[A-Za-z0-9_~.-]{24,})" .`
- Exit code: `1`
- Result: no matches found in non-ignored files.

## Runtime Command Gate

Stopped diagnostic before stack creation:

- First attempt failed with a real implementation bug in recursive redaction.
- Fix applied: redaction now preserves dictionaries nested in lists.
- Retry command: `gitea-sandbox diagnose`
- Exit code: `1`
- Summary: `postgres` and `gitea` were both `missing`; stopped-state result
  was reported without traceback.

Start command:

- Command: `gitea-sandbox start`
- Exit code: `0`
- PostgreSQL: `state=running`, `health=healthy`
- Gitea: `state=running`, `health=healthy`
- HTTP endpoint: `http://localhost:3000/`
- SSH endpoint: `ssh://localhost:2222`

Docker Compose state:

- `docker compose ps` showed:
  - `gitea_sandbox_adapter-postgres-1`: `Up`, `healthy`
  - `gitea_sandbox_adapter-gitea-1`: `Up`, `healthy`
- PostgreSQL safe inspect result: `running healthy`
- Gitea safe inspect result: `running healthy`
- Compose ownership labels matched project `gitea_sandbox_adapter`.

Runtime service checks:

- Host health endpoint `http://localhost:3000/api/healthz` returned
  `status=pass`.
- PostgreSQL `SELECT version();` returned:
  `PostgreSQL 16.14 (Debian 16.14-1.pgdg12+1) on x86_64-pc-linux-gnu`
- `gitea-sandbox status` while healthy exit code: `0`

Stop verification:

- Command: `gitea-sandbox stop`
- Exit code: `0`
- `docker compose ps -a` listed no project containers after stop.
- Preserved named volumes:
  - `gitea_sandbox_adapter_gitea_config`
  - `gitea_sandbox_adapter_gitea_data`
  - `gitea_sandbox_adapter_postgres_data`
- Stopped `gitea-sandbox status` exit code: `1`
- Stack was started again for the population gate; start exit code: `0`

## Deterministic REST API Population Gate

Fixture manifest:

- `fixtures/gitea_seed.json`
- Schema version: `1`
- Organization: `sandbox-labs`
- Team: `developers`
- Repository: `sandbox-labs/adapter-demo`
- Default branch: `main`
- Files:
  - `README.md`
  - `docs/phase-2-notes.md`
- Labels:
  - `kind/api`
  - `kind/browser`
- Milestone: `Phase 2 Deterministic Baseline`
- Issue: `Validate deterministic sandbox population`
- Release: `v0.1.0-phase-2`

First population:

- Command: `gitea-sandbox populate`
- Exit code: `0`
- File hashes:
  - `README.md`:
    `beefd4e6566b7f7c8768915be577cf34bb64820a5aa979c88f44eb7ecb979035`
  - `docs/phase-2-notes.md`:
    `10b40f7052a182be8f60c4dc055d6cadda693b91834d4c98c1fa97d281977593`

Second population:

- Initial second run exit code: `1`
- Actual failure: Gitea returned `201` for issue `PATCH`; the client expected
  only `200`.
- Fix applied: issue update now accepts actual successful Gitea responses
  `200` and `201`.
- Retried second population exit code: `0`
- Retried second population returned the same deterministic resource summary
  and file hashes.

Token handling:

- Local administrator bootstrap was performed by Gitea's administration CLI.
- API token was created/reused without printing token value.
- Token is stored only in the ignored local runtime directory.

## API and Real-Browser Validation Gate

Correction note after independent audit: normal browser validation now writes
screenshots under ignored `.gitea-sandbox/browser-evidence/` runtime
directories. The tracked screenshots in `docs/evidence/` are public evidence
artifacts and are not overwritten by ordinary `validate`, `restore --force`, or
`reset --force` commands.

API-only validation:

- Command: `gitea-sandbox validate --api-only`
- Exit code: `0`
- Gitea API version: `1.27.0`
- Authenticated user: `sandbox-admin`
- Duplicate checks:
  - labels: `2`
  - milestones: `1`
  - issues: `1`
  - releases: `1`

Browser validation:

- First browser run exit code: `1`
- Actual failure: login submit selector expected `button[type="submit"]`, but
  Gitea rendered a submit button without a `type` attribute.
- Fix applied: click the rendered `Sign In` button by role/name.
- Second browser run exit code: `1`
- Actual failure: `networkidle` wait was not reliable for Gitea's frontend.
- Fix applied: use `load` and URL-based waits.
- Third browser run exit code: `1`
- Actual failure: the first `sandbox-admin` text node was hidden in a
  mobile-only span.
- Fix applied: dashboard login assertion moved to page title.
- Additional Windows console fix: Playwright diagnostics can contain Unicode
  glyphs; CLI error output now escapes non-ASCII safely.
- Final browser-only command: `gitea-sandbox validate --browser-only`
- Final browser-only exit code: `0`
- Pages verified:
  - authenticated dashboard
  - organization page
  - repository README
  - issue list
  - release page
- Screenshots created and visually inspected:
  - `docs/evidence/browser-repository.png`
  - `docs/evidence/browser-release.png`
- Screenshot secret review: no passwords, tokens, cookies, Authorization data,
  or credential-bearing URLs visible.

Complete validation:

- Command: `gitea-sandbox validate`
- Exit code: `0`
- Included runtime, PostgreSQL, REST API, and real browser validation.

## Snapshot Gate

Baseline snapshot:

- Command: `gitea-sandbox snapshot`
- Exit code: `0`
- Ignored bundle path: `snapshots/phase2-20260723T101840Z`
- Bundle payloads:
  - `postgres.dump`
  - `gitea-data.tar.gz`
  - `gitea-config.tar.gz`
  - `manifest.json`
- Independent bundle validation exit code: `0`
- Stack health after snapshot: `postgres` and `gitea` both healthy.
- Sanitized manifest copy:
  `docs/evidence/snapshot-manifest-example.json`

Snapshot manifest checksums:

- `postgres.dump`:
  `e78b18b4898c79390155d3fae0d4a0ae1023c0304eeb246001c78db6c28460de`
- `gitea-data.tar.gz`:
  `8f3414237782a410ed5a31460e9afc5105fca72a4b941e2e41b8772d4d612d83`
- `gitea-config.tar.gz`:
  `3b2f3c68012ced7435a9e6cf834f9bda929598e1eca05251f10f4171859c324a`

## Restore Gate

First restore proof:

- Marker created after snapshot:
  `post-snapshot-marker-20260723T1019Z`
- Marker verification before restore: `marker_exists True`
- Command: `gitea-sandbox restore snapshots/phase2-20260723T101840Z --force`
- Exit code: `0`
- Removed volumes:
  - `gitea_sandbox_adapter_postgres_data`
  - `gitea_sandbox_adapter_gitea_data`
  - `gitea_sandbox_adapter_gitea_config`
- Pre-restore safety snapshot created.
- Marker verification after restore: `marker_exists False`
- Fixture issue count after restore: `1`
- Complete validation after restore exit code: `0`

Patched restore proof:

- Reason for rerun: restore was patched to return relative safety snapshot
  paths and to run browser validation inside the restore workflow.
- Second marker:
  `post-snapshot-marker-20260723T1022Z`
- Marker verification before patched restore: `marker_exists True`
- Command: `gitea-sandbox restore snapshots/phase2-20260723T101840Z --force`
- Exit code: `0`
- Pre-restore safety snapshot: `snapshots/phase2-20260723T102157Z`
- Marker verification after patched restore: `marker_exists False`
- Fixture issue count after patched restore: `1`
- Runtime health after patched restore: `postgres` and `gitea` both healthy.

## Reset Gate

Reset refusal:

- Command: `gitea-sandbox reset`
- Exit code: `1`
- Result: refused with `reset requires --force and made no changes.`

Guarded reset proof:

- Marker created before reset: `reset-marker-20260723T1023Z`
- Marker verification before reset: `marker_exists True`
- Command: `gitea-sandbox reset --force`
- Exit code: `0`
- Pre-reset safety snapshot: `snapshots/phase2-20260723T102346Z`
- Removed volumes:
  - `gitea_sandbox_adapter_postgres_data`
  - `gitea_sandbox_adapter_gitea_data`
  - `gitea_sandbox_adapter_gitea_config`
- Deterministic population after reset:
  - organization: `sandbox-labs`
  - repository: `sandbox-labs/adapter-demo`
  - team: `developers`
  - labels: `kind/api`, `kind/browser`
  - milestone: `Phase 2 Deterministic Baseline`
  - issue: `Validate deterministic sandbox population`
  - release: `v0.1.0-phase-2`
- Reset marker after reset: `False`
- Fixture issue count after reset: `1`
- Fixture label count after reset: `2`
- Project named volumes after reset:
  - `gitea_sandbox_adapter_gitea_config`
  - `gitea_sandbox_adapter_gitea_data`
  - `gitea_sandbox_adapter_postgres_data`
- Project containers after reset: both `Up` and `healthy`.
- Unrelated Docker resources modified: no evidence of unrelated resource
  modification; reset code targets exact project-owned resources only.

## Diagnose Gate

Healthy human diagnostic:

- Command: `gitea-sandbox diagnose`
- Exit code: `0`
- Summary: `sandbox healthy and fixture valid`
- Reported:
  - Python version
  - package version
  - operating system
  - sanitized repository root
  - Git branch and clean/dirty state
  - Docker daemon, Compose, and context
  - pinned image availability
  - Compose configuration validity
  - `.env` presence without values
  - HTTP and SSH endpoints
  - port listener summary
  - project network and volumes
  - container states and health
  - Gitea health endpoint
  - PostgreSQL readiness query
  - API authentication summary
  - fixture validation summary
  - snapshot directory summary
  - recent redacted service logs

Healthy JSON diagnostic:

- Command: `gitea-sandbox diagnose --json`
- Exit code: `0`
- Summary: `sandbox healthy and fixture valid`
- Focused JSON secret-value scan exit code: `1`
- Result: no secret-looking values matched.

## Fault-Injection Gate

Runner:

- File: `scripts/run_fault_injection.py`
- Command: `python scripts/run_fault_injection.py`
- Exit code: `0`

Scenarios:

- PostgreSQL stopped:
  - Injected fault: stopped only project PostgreSQL service.
  - `status` exit code: `1`
  - `diagnose` exit code: `1`
  - Recovery: `docker compose up -d`, bounded health wait.
  - API validation after recovery exit code: `0`
- Gitea stopped:
  - Injected fault: stopped only project Gitea service.
  - `status` exit code: `1`
  - `diagnose` exit code: `1`
  - Recovery: `docker compose up -d`, bounded health wait.
  - API validation after recovery exit code: `0`
- Corrupt snapshot:
  - Injected fault: copied a real snapshot to ignored runtime state and
    corrupted a manifest checksum.
  - Expected detection: restore raised `SnapshotError` before destructive
    changes.
  - Live API validation after refusal exit code: `0`
- Missing required configuration:
  - Injected fault: isolated temporary project root without `.env`.
  - Expected detection: `ConfigError`.
  - Real `.env` was not modified.
- Occupied-port handling:
  - Injected fault: unit port selector treated default HTTP and SSH ports as
    unavailable.
  - Expected detection: selected alternative ports without collision.

Final recovery validation after all fault scenarios:

- Command: `gitea-sandbox validate`
- Exit code: `0`
- Runtime, PostgreSQL, API, and browser validation all passed.

## GitHub Actions CI Gate

Workflow:

- File: `.github/workflows/ci.yml`
- Local structural inspection command verified required sections and action
  versions before the first hosted run.
- Initially configured:
  - `actions/checkout@v6`
  - `actions/setup-python@v6`
  - least-privilege `contents: read`
  - Ubuntu and Windows quality matrix for Python `3.11` and `3.12`
  - Linux Docker integration job
  - concurrency cancellation
  - sanitized failure artifact upload only
- First GitHub-hosted CI execution for pull request #2: run.
- First hosted CI result: failed.
- Quality matrix root cause: pytest was configured with
  `--basetemp=.gitea-sandbox/pytest-tmp`; clean GitHub runners had no ignored
  `.gitea-sandbox` parent directory.
- Linux Docker integration progress before failure:
  - Docker Compose verification passed.
  - Python dependency installation passed.
  - CI `.env` generation passed.
  - Compose configuration passed.
  - Sandbox start passed.
  - Deterministic population passed.
  - API validation passed.
  - Snapshot creation passed.
- Linux Docker integration root cause: restore performs real browser
  validation, but the GitHub-hosted runner did not have the Chromium executable
  installed for the Python Playwright package.
- Targeted local corrections:
  - removed the pytest temp-directory override so clean checkouts use pytest's
    normal portable temp handling;
  - added `python -m playwright install --with-deps chromium` after Python
    dependency installation and before restore/browser validation;
  - restricted workflow `push` triggers to `main` while preserving
    `pull_request` and concurrency cancellation.
- Corrected GitHub-hosted rerun: run #3 passed on the corrected pull-request
  commit.
- Quality jobs: passed on Ubuntu and Windows with Python 3.11 and 3.12.
- Linux Docker integration: passed.
- Docker job completed: Playwright Chromium installation, sandbox start,
  deterministic population, API validation, snapshot, forced restore,
  integration pytest, and cleanup.
- Raw diagnostics uploaded: no; the successful job did not need failure
  diagnostics.

## Final End-to-End Verification

Final branch:

- `feat/phase-2-complete`

Ignored `.env`:

- `git check-ignore .env` returned `.env`.
- `git status --short -- .env` returned no output.

Quality:

- Editable install: exit code `0`
- Unit pytest: `26 passed, 1 deselected`, exit code `0`
- Real integration pytest: `1 passed, 26 deselected`, exit code `0`
- Full pytest: `26 passed, 1 skipped`, exit code `0`
- Ruff: exit code `0`
- mypy: exit code `0`
- Package build:
  - First attempt exit code: `1`
  - Failure: sandboxed build isolation could not download `setuptools>=68`
    due `WinError 10013`.
  - Approved retry exit code: `0`
  - Built sdist and wheel.
  - Warning: setuptools reported `project.license` table deprecation.
- `git diff --check`: exit code `0`
  - Warning only: Git reported LF-to-CRLF normalization notices on Windows.
- Focused tracked-file secret scan: exit code `0`

Final runtime sequence:

- `docker compose config --quiet`: exit code `0`
- `gitea-sandbox stop`: exit code `0`
- stopped `gitea-sandbox diagnose`: exit code `1`, expected stopped-state
  result
- `gitea-sandbox start`: exit code `0`
- Docker Compose ps: both services `Up` and `healthy`
- Host health endpoint: `status=pass`
- PostgreSQL version query:
  `PostgreSQL 16.14 (Debian 16.14-1.pgdg12+1)`
- first final `gitea-sandbox populate`: exit code `0`
- second final `gitea-sandbox populate`: exit code `0`
- API-only validation: exit code `0`
- browser-only validation: exit code `0`
- complete validation: exit code `0`

Final snapshot/restore:

- Final baseline snapshot:
  `snapshots/phase2-20260723T104055Z`
- Snapshot manifest/checksum validation: exit code `0`
- Final restore marker:
  `final-restore-marker-20260723T1041Z`
- Marker before restore: `True`
- Final restore command: `gitea-sandbox restore snapshots/phase2-20260723T104055Z --force`
- Restore exit code: `0`
- Pre-restore safety snapshot:
  `snapshots/phase2-20260723T104140Z`
- Marker after restore: `False`
- Fixture issue count after restore: `1`
- Complete validation after restore: exit code `0`

Final fault injection:

- Command: `python scripts/run_fault_injection.py`
- Exit code: `0`
- Complete validation after recovery: exit code `0`

Final reset:

- Final reset marker: `final-reset-marker-20260723T1045Z`
- Marker before reset: `True`
- Command: `gitea-sandbox reset --force`
- Exit code: `0`
- Pre-reset safety snapshot: `snapshots/phase2-20260723T104512Z`
- Marker after reset: `False`
- Fixture issue count: `1`
- Fixture label count: `2`
- Fixture release count: `1`
- Complete validation after reset: exit code `0`

Final diagnostics:

- `gitea-sandbox diagnose --json`: exit code `0`
- Summary: `sandbox healthy and fixture valid`
- Secret-value scan of JSON diagnostics: exit code `1`, no matches

Final stopped state:

- `gitea-sandbox stop`: exit code `0`
- `docker compose ps -a`: no project containers listed
- Preserved volumes:
  - `gitea_sandbox_adapter_gitea_config`
  - `gitea_sandbox_adapter_gitea_data`
  - `gitea_sandbox_adapter_postgres_data`
- stopped `gitea-sandbox status`: exit code `1`
