# gitea-sandbox-adapter

`gitea-sandbox-adapter` manages a reproducible local Gitea sandbox backed by
PostgreSQL. It is intended as public, recruiter-verifiable engineering evidence:
real Docker containers, real Gitea REST API population, validation, snapshots,
restore, guarded reset, diagnostics, and controlled fault injection.

## Phase 2 Capabilities

- Docker Compose sandbox with pinned Gitea and PostgreSQL images
- Rootless Gitea configuration with PostgreSQL storage
- Deterministic, idempotent Gitea REST API population
- Runtime, API, PostgreSQL, and isolated Playwright browser validation
- Portable snapshot bundles with checksums and safe manifests
- Guarded restore and reset workflows requiring `--force`
- Read-only diagnostics with human and JSON output
- Controlled fault-injection runner
- Fast unit tests and separable real integration tests
- GitHub Actions workflow configuration

## Pinned Images

- `docker.gitea.com/gitea:1.27.0-rootless`
- `docker.io/library/postgres:16.14-bookworm`

Do not replace these with `latest`, rolling tags, release candidates, nightly
images, or development images.

## Prerequisites

- Python 3.11 or newer
- Docker Desktop on Windows, or Docker Engine with Docker Compose V2 on Linux
- Git
- Playwright Chromium for browser validation

Windows Docker Desktop: start Docker Desktop first and use the Docker context
that can reach the Linux engine. Linux Docker Engine: ensure your user can run
`docker version` and `docker compose version` without `sudo`.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m playwright install chromium
copy .env.example .env
```

Generate real local secrets for `.env`. The repository ignores `.env`; never
commit it.

## CLI

The console command is:

```powershell
gitea-sandbox
```

Commands:

- `start`: validate configuration, start the real stack, and wait for health
- `stop`: stop containers while preserving named volumes
- `status`: report required service state and health; zero only when healthy
- `populate`: create or converge the deterministic fixture through REST APIs
- `validate`: run runtime, PostgreSQL, API, and browser validation
- `validate --api-only`: skip browser validation
- `validate --browser-only`: run only real browser validation
- `validate --no-screenshots`: run browser validation without screenshot output
- `validate --screenshot-dir <path>`: intentionally write screenshots to a
  repository-local directory
- `snapshot`: create an ignored portable snapshot bundle
- `restore <bundle> --force`: restore a verified snapshot
- `reset --force`: rebuild the sandbox from owned resources only
- `diagnose`: read-only human diagnostics
- `diagnose --json`: sanitized machine-readable diagnostics

Exit-code rule: zero means the real requested operation completed and verified.
Stopped, missing, partial, starting, unhealthy, refused, or invalid states return
non-zero.

## Deterministic Fixture

The tracked fixture manifest is `fixtures/gitea_seed.json`. It defines:

- organization `sandbox-labs`
- team `developers`
- repository `adapter-demo`
- branch `main`
- two repository files
- two labels
- one milestone
- one issue
- one release

Population is idempotent: existing fixture resources are compared and updated
where safe; unrelated user data is not deleted.

## Snapshots

Snapshots are ignored under `snapshots/`. A bundle contains:

- PostgreSQL custom-format dump
- Gitea data archive
- Gitea configuration archive
- JSON manifest with schema, UTC timestamp, image references, fixture hash, and
  SHA-256 checksums

Snapshots contain no plaintext passwords or access tokens by design.

## Restore And Reset Safeguards

`restore` and `reset` require `--force`. They verify Compose ownership labels
before removing volumes, target exact project-owned resources only, avoid broad
Docker prune operations, and create safety snapshots by default when the current
state is recoverable.

## Validation

API validation checks authenticated user, organization, team, repository,
default branch, exact file hashes, labels, milestone, issue, release, health,
version, and duplicate counts.

Browser validation uses Playwright Chromium in an isolated context. It logs in
with local ignored credentials, verifies the rendered dashboard, organization,
repository README, issue list, and release page. By default, screenshots are
runtime artifacts under ignored `.gitea-sandbox/browser-evidence/` directories.
Tracked public evidence under `docs/evidence/` is created only when an explicit
repository-local `--screenshot-dir` is requested.

## Local Verification

```powershell
python -m pip install -e ".[dev]"
pytest -m "not integration"
ruff check src tests scripts
mypy
docker compose --env-file .env -f compose.yaml -p gitea_sandbox_adapter config --quiet
gitea-sandbox start
gitea-sandbox populate
gitea-sandbox validate
gitea-sandbox snapshot
python scripts/run_fault_injection.py
gitea-sandbox stop
```

Real integration tests are separable:

```powershell
$env:GITEA_SANDBOX_RUN_INTEGRATION = "1"
pytest -m integration
```

## CI Status

The first GitHub-hosted CI executions for pull request #2 ran on 2026-07-23 and
failed because pytest assumed an ignored `.gitea-sandbox/pytest-tmp` parent
directory in a clean checkout, and the Linux Docker integration runner lacked
the Playwright Chromium browser binary before restore-time browser validation.

Targeted local fixes have been added, but the corrected hosted rerun remains
pending until this correction is committed and pushed. This repository does not
claim GitHub-hosted CI passing status yet.

## Security Limits

This is a local development sandbox, not a hardened production deployment. It
redacts likely secrets, stores tokens only in ignored runtime state, does not
mount the Docker socket, does not use privileged containers, and does not expose
PostgreSQL to the host by default.

See `docs/runbook.md`, `docs/threat-model.md`, and `docs/failure-catalog.md` for
operational details.
