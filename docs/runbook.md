# Runbook

## Start

1. Create `.env` from `.env.example`.
2. Install dev dependencies.
3. Run `gitea-sandbox start`.
4. Confirm `gitea-sandbox status` returns zero.

## Populate

Run `gitea-sandbox populate`. It bootstraps the local admin and token as needed,
then uses the Gitea REST API to converge the fixture.

## Validate

Use `gitea-sandbox validate --api-only` for API and database checks, or
`gitea-sandbox validate` for full API plus browser validation.

Browser screenshots are ignored runtime artifacts by default and are written
under `.gitea-sandbox/browser-evidence/`. Use `--no-screenshots` to suppress
them, or `--screenshot-dir <repo-relative-path>` when intentionally creating
public evidence. Screenshot output paths outside the repository are rejected.

## Snapshot

Run `gitea-sandbox snapshot`. The bundle is written under ignored `snapshots/`.
Use the manifest checksums to verify payload integrity.

## Restore

Run `gitea-sandbox restore <snapshot-dir> --force`. Restore refuses without
`--force`, validates bundle safety and checksums first, creates a safety
snapshot when possible, and removes only project-owned volumes.

## Reset

Run `gitea-sandbox reset --force`. Reset refuses without `--force`, creates a
safety snapshot when possible, removes exact owned volumes, starts a fresh stack,
populates, and validates.

## Diagnose

Run `gitea-sandbox diagnose` or `gitea-sandbox diagnose --json`. Diagnostics are
read-only and redact likely secrets.

## Stop

Run `gitea-sandbox stop`. This preserves named volumes.
