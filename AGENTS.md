# Repository Agent Notes

This repository is now on the Project 2 Phase 2 implementation branch. Phase 1
foundation work has been completed, audited, merged to `main`, and verified.

Phase 2 explicitly permits the complete local sandbox implementation for this
repository, including Docker Compose, Gitea, PostgreSQL, REST API integration,
browser validation, snapshots, restore workflows, guarded reset, diagnostics,
controlled fault injection, tests, documentation, and GitHub Actions workflow
configuration.

- Work only inside this repository and Docker resources owned by this
  repository's Compose project.
- Do not begin Project 3.
- Do not commit, push, merge, publish, deploy, create a release, or create a
  pull request.
- Keep all operational CLI commands honest: return zero only when the real
  required operation completed successfully.
- Never claim a command, test, container, healthcheck, API call, browser check,
  snapshot, restore, CI workflow, or fault-injection scenario passed unless it
  was actually executed and produced the expected result.
- Do not invent test counts, coverage numbers, durations, image digests,
  container states, health results, API responses, database query results,
  browser evidence, or CI execution results.
- A GitHub Actions workflow created locally may only be described as workflow
  configuration created and locally inspected until GitHub actually runs it.
- Store no secrets in Git-tracked files. Never print passwords, access tokens,
  Authorization headers, raw cookies, or credential-bearing URLs.
- Redact likely secrets in logs, diagnostics, JSON output, errors, evidence,
  and documentation.
- Do not inspect unrelated repositories, personal files, browser profiles,
  saved credentials, SSH keys, or Docker credential files.
- Do not use sudo or administrator elevation, privileged containers,
  Docker-in-Docker, or host Docker socket mounts.
- Do not use `shell=True`.
- Do not run broad deletion commands, `docker system prune`,
  `docker volume prune`, or `docker network prune`.
- Do not delete unrelated containers, networks, images, or volumes.
- Project-owned resources may be removed only by guarded restore/reset flows
  after `--force`, Compose ownership-label verification, resource-name
  verification, and recoverable safety snapshot creation when applicable.
- Use the standard `src/` layout with package `gitea_sandbox_adapter`.
- Keep the console command `gitea-sandbox` and standard-library `argparse`.
- Validate changes with pytest, Ruff, mypy, direct CLI smoke checks, and real
  Docker integration checks when available and required.
