# Repository Agent Notes

This repository is in Phase 1 foundation work.

- Work only inside this repository.
- Do not start Docker, Gitea, PostgreSQL, REST API integration, snapshots,
  restore workflows, browser automation, CI, or fault-injection work during
  Phase 1.
- Keep operational CLI commands honest: unimplemented commands must exit
  non-zero and must not print success messages.
- Use the standard `src/` layout with package `gitea_sandbox_adapter`.
- Use standard-library `argparse` for the CLI.
- Validate changes with pytest, Ruff, mypy, and direct CLI smoke checks when
  possible.
