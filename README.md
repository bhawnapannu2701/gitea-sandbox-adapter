# gitea-sandbox-adapter

`gitea-sandbox-adapter` is planned as a production-style Python adapter for
managing Gitea and PostgreSQL inside a reproducible sandbox.

## Project Goal

The long-term goal is to provide a dependable local engineering sandbox around
Gitea, PostgreSQL, repository population, validation, snapshots, restore flows,
diagnostics, and reset workflows.

## Current Phase 1 Scope

Phase 1 is foundation-only. It establishes the Python project structure,
package metadata, console entry point, command registry, and tests for the CLI
contract.

Operational behavior is intentionally not implemented in Phase 1. Running any
registered operational command exits with a non-zero status and prints:

```text
Command '<command-name>' is not implemented in Phase 1.
```

The command must not report false success.

## Local Development Setup

This project requires Python 3.11 or newer.

Create and activate a local virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the project in editable mode with development tools:

```powershell
python -m pip install -e ".[dev]"
```

Run checks:

```powershell
pytest
ruff check .
mypy
```

## CLI Commands

The console command is:

```powershell
gitea-sandbox
```

Registered Phase 1 commands:

- `start`
- `stop`
- `status`
- `populate`
- `validate`
- `snapshot`
- `restore`
- `reset`
- `diagnose`

Use `gitea-sandbox --help` for top-level help and
`gitea-sandbox <command> --help` for command-specific help.

## Not Implemented Yet

The following are not implemented in Phase 1:

- Docker sandbox orchestration
- Gitea integration
- PostgreSQL integration
- REST API integration
- Snapshot workflows
- Restore workflows
- Browser validation
- Continuous integration
