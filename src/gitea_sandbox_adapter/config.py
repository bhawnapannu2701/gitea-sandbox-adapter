"""Configuration loading for the local Gitea sandbox."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from gitea_sandbox_adapter.errors import ConfigError

PINNED_GITEA_IMAGE = "docker.gitea.com/gitea:1.27.0-rootless"
PINNED_POSTGRES_IMAGE = "docker.io/library/postgres:16.14-bookworm"

DEFAULTS: dict[str, str] = {
    "COMPOSE_PROJECT_NAME": "gitea_sandbox_adapter",
    "GITEA_IMAGE": PINNED_GITEA_IMAGE,
    "POSTGRES_IMAGE": PINNED_POSTGRES_IMAGE,
    "GITEA_HTTP_PORT": "3000",
    "GITEA_SSH_PORT": "2222",
    "POSTGRES_DB": "gitea",
    "POSTGRES_USER": "gitea",
    "GITEA_ADMIN_USER": "sandbox-admin",
    "GITEA_ADMIN_EMAIL": "sandbox-admin@example.invalid",
    "GITEA_TOKEN_NAME": "gitea-sandbox-phase-2",
    "GITEA_START_TIMEOUT": "240",
    "GITEA_STOP_TIMEOUT": "90",
    "GITEA_HEALTH_POLL_INTERVAL": "3",
    "GITEA_HTTP_TIMEOUT": "20",
    "GITEA_HTTP_RETRIES": "3",
    "GITEA_BROWSER_TIMEOUT": "30000",
}

REQUIRED = (
    "COMPOSE_PROJECT_NAME",
    "GITEA_IMAGE",
    "POSTGRES_IMAGE",
    "GITEA_HTTP_PORT",
    "GITEA_SSH_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "GITEA_ADMIN_USER",
    "GITEA_ADMIN_PASSWORD",
    "GITEA_ADMIN_EMAIL",
    "GITEA_TOKEN_NAME",
)


@dataclass(frozen=True)
class SandboxConfig:
    repo_root: Path
    env_file: Path
    compose_file: Path
    project_name: str
    gitea_image: str
    postgres_image: str
    http_port: int
    ssh_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str
    admin_user: str
    admin_password: str
    admin_email: str
    token_name: str
    start_timeout: int
    stop_timeout: int
    poll_interval: float
    http_timeout: int
    http_retries: int
    browser_timeout_ms: int

    @property
    def root_url(self) -> str:
        return f"http://localhost:{self.http_port}/"

    @property
    def api_base_url(self) -> str:
        return f"{self.root_url.rstrip('/')}/api/v1"

    @property
    def health_url(self) -> str:
        return f"{self.root_url.rstrip('/')}/api/healthz"

    @property
    def runtime_dir(self) -> Path:
        return self.repo_root / ".gitea-sandbox"

    @property
    def browser_evidence_dir(self) -> Path:
        return self.runtime_dir / "browser-evidence"

    @property
    def token_file(self) -> Path:
        return self.runtime_dir / "token.json"

    @property
    def snapshots_dir(self) -> Path:
        return self.repo_root / "snapshots"

    @property
    def fixture_file(self) -> Path:
        return self.repo_root / "fixtures" / "gitea_seed.json"

    def compose_env(self) -> dict[str, str]:
        return {
            "COMPOSE_PROJECT_NAME": self.project_name,
            "GITEA_IMAGE": self.gitea_image,
            "POSTGRES_IMAGE": self.postgres_image,
            "GITEA_HTTP_PORT": str(self.http_port),
            "GITEA_SSH_PORT": str(self.ssh_port),
            "POSTGRES_DB": self.postgres_db,
            "POSTGRES_USER": self.postgres_user,
            "POSTGRES_PASSWORD": self.postgres_password,
            "GITEA_ADMIN_USER": self.admin_user,
            "GITEA_ADMIN_PASSWORD": self.admin_password,
            "GITEA_ADMIN_EMAIL": self.admin_email,
            "GITEA_TOKEN_NAME": self.token_name,
        }


def repo_root_from(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").exists() and (candidate / "src").exists():
            return candidate
    raise ConfigError("Could not locate repository root.")


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ConfigError(f"Invalid .env line {line_number}: expected NAME=value")
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not name:
            raise ConfigError(f"Invalid .env line {line_number}: missing variable name")
        if len(value) >= 2 and value[0] == value[-1] and value.startswith(("'", '"')):
            value = value[1:-1]
        values[name] = value
    return values


def _as_int(values: dict[str, str], name: str) -> int:
    try:
        return int(values[name])
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer.") from exc


def load_config(
    *,
    repo_root: Path | None = None,
    require_env: bool = True,
    environ: dict[str, str] | None = None,
) -> SandboxConfig:
    root = repo_root_from(repo_root)
    env_file = root / ".env"
    env_values = parse_env_file(env_file)
    if require_env and not env_file.exists():
        raise ConfigError(
            ".env is required for runtime commands. Copy .env.example first."
        )

    merged = dict(DEFAULTS)
    merged.update(env_values)
    merged.update(os.environ if environ is None else environ)

    missing = [name for name in REQUIRED if not merged.get(name)]
    if require_env and missing:
        joined = ", ".join(missing)
        raise ConfigError(f"Missing required configuration: {joined}")

    if merged["GITEA_IMAGE"] != PINNED_GITEA_IMAGE:
        raise ConfigError(f"GITEA_IMAGE must be pinned to {PINNED_GITEA_IMAGE}")
    if merged["POSTGRES_IMAGE"] != PINNED_POSTGRES_IMAGE:
        raise ConfigError(f"POSTGRES_IMAGE must be pinned to {PINNED_POSTGRES_IMAGE}")

    return SandboxConfig(
        repo_root=root,
        env_file=env_file,
        compose_file=root / "compose.yaml",
        project_name=merged["COMPOSE_PROJECT_NAME"],
        gitea_image=merged["GITEA_IMAGE"],
        postgres_image=merged["POSTGRES_IMAGE"],
        http_port=_as_int(merged, "GITEA_HTTP_PORT"),
        ssh_port=_as_int(merged, "GITEA_SSH_PORT"),
        postgres_db=merged.get("POSTGRES_DB", ""),
        postgres_user=merged.get("POSTGRES_USER", ""),
        postgres_password=merged.get("POSTGRES_PASSWORD", ""),
        admin_user=merged.get("GITEA_ADMIN_USER", ""),
        admin_password=merged.get("GITEA_ADMIN_PASSWORD", ""),
        admin_email=merged.get("GITEA_ADMIN_EMAIL", ""),
        token_name=merged.get("GITEA_TOKEN_NAME", ""),
        start_timeout=_as_int(merged, "GITEA_START_TIMEOUT"),
        stop_timeout=_as_int(merged, "GITEA_STOP_TIMEOUT"),
        poll_interval=float(merged["GITEA_HEALTH_POLL_INTERVAL"]),
        http_timeout=_as_int(merged, "GITEA_HTTP_TIMEOUT"),
        http_retries=_as_int(merged, "GITEA_HTTP_RETRIES"),
        browser_timeout_ms=_as_int(merged, "GITEA_BROWSER_TIMEOUT"),
    )
