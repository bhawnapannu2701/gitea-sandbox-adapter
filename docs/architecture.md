# Architecture

The adapter keeps a standard Python `src/` layout with package
`gitea_sandbox_adapter` and console command `gitea-sandbox`.

Runtime modules:

- `config.py`: `.env` parsing, pinned image enforcement, timeout settings
- `runtime.py`: bounded subprocess execution with argument lists
- `docker.py`: Docker and Compose orchestration plus ownership checks
- `api.py`: standard-library HTTP client for Gitea REST API calls
- `population.py`: deterministic fixture convergence and token bootstrap
- `validation.py`: runtime, PostgreSQL, and API validation
- `browser_validation.py`: isolated Playwright browser validation
- `snapshot.py`: snapshot, restore, and reset workflows
- `diagnostics.py`: read-only human and JSON diagnostics
- `redaction.py`: centralized secret redaction
- `ports.py`: host port detection and alternative selection helpers

Browser validation writes screenshots to ignored runtime directories under
`.gitea-sandbox/browser-evidence/` by default. Tracked public evidence paths are
used only when a repository-local screenshot directory is explicitly requested.

Compose services:

- `postgres`: pinned PostgreSQL image, one named data volume, private project
  network, `pg_isready` healthcheck
- `gitea`: pinned rootless Gitea image, data and config named volumes,
  PostgreSQL database configuration, locked installation, disabled public
  registration, rootless SSH, and `/api/healthz` healthcheck

Named volumes:

- `postgres_data`
- `gitea_data`
- `gitea_config`

The adapter never uses fixed container names. Compose project labels are used to
verify ownership before destructive restore or reset work.
