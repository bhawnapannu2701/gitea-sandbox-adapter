"""Read-only diagnostics for the sandbox."""

from __future__ import annotations

import json
import platform
import socket
from pathlib import Path
from typing import Any

from gitea_sandbox_adapter import __version__
from gitea_sandbox_adapter.api import ApiClient
from gitea_sandbox_adapter.config import SandboxConfig, load_config, repo_root_from
from gitea_sandbox_adapter.docker import SERVICES, VOLUMES, DockerRunner
from gitea_sandbox_adapter.errors import ConfigError
from gitea_sandbox_adapter.redaction import redact, redact_mapping
from gitea_sandbox_adapter.runtime import run_command
from gitea_sandbox_adapter.validation import validate_api_with_client


def diagnose(*, as_json: bool = False) -> tuple[int, str]:
    root = repo_root_from(Path.cwd())
    try:
        config = load_config(repo_root=root, require_env=False)
        config_error = None
    except ConfigError as exc:
        config = None
        config_error = str(exc)

    checks: dict[str, Any] = {
        "package_version": __version__,
        "python": platform.python_version(),
        "operating_system": platform.platform(),
        "repository_root": "<repo-root>",
        "git": _git_summary(root),
    }

    if config is None:
        checks["configuration"] = {"ok": False, "error": config_error}
        exit_code = 1
    else:
        docker = DockerRunner(config)
        checks.update(_sandbox_checks(root, config, docker, config_error))
        exit_code = _diagnose_exit_code(checks)

    safe_checks = redact_mapping(checks)
    if as_json:
        return exit_code, json.dumps(safe_checks, indent=2)
    return exit_code, _human(safe_checks)


def _sandbox_checks(
    root: Path,
    config: SandboxConfig,
    docker: DockerRunner,
    config_error: str | None,
) -> dict[str, Any]:
    containers = [
        {
            "service": status.service,
            "state": status.state,
            "health": status.health,
            "container": status.container_name,
        }
        for status in docker.all_statuses()
    ]
    return {
        "configuration": {
            "ok": config_error is None,
            "env_present": config.env_file.exists(),
            "required_names": list(config.compose_env().keys()),
            "http_endpoint": config.root_url,
            "ssh_endpoint": f"ssh://localhost:{config.ssh_port}",
        },
        "ports": _port_summary(root, [config.http_port, config.ssh_port]),
        "docker": _docker_summary(docker),
        "images": _image_summary(docker),
        "compose_config": _compose_config_summary(docker),
        "resources": _resource_summary(docker),
        "containers": containers,
        "runtime_readiness": _runtime_readiness(config, docker),
        "api_auth": _api_auth_summary(config),
        "fixture_validation": _fixture_summary(config),
        "snapshots": _snapshot_summary(config.snapshots_dir),
        "logs": _logs_summary(docker),
    }


def _diagnose_exit_code(checks: dict[str, Any]) -> int:
    containers = checks.get("containers", [])
    healthy = all(
        item["state"] == "running" and item["health"] == "healthy"
        for item in containers
    )
    runtime = checks.get("runtime_readiness", {})
    api_auth = checks.get("api_auth", {})
    fixture = checks.get("fixture_validation", {})
    valid = (
        healthy
        and runtime.get("postgres_query") is True
        and runtime.get("gitea_health") is True
        and api_auth.get("ok") is True
        and fixture.get("ok") is True
    )
    checks["summary"] = (
        "sandbox healthy and fixture valid"
        if valid
        else "sandbox stopped or not fully healthy"
        if not healthy
        else "sandbox running but validation failed"
    )
    return 0 if valid else 1


def _git_summary(root: Path) -> dict[str, Any]:
    branch = run_command(["git", "branch", "--show-current"], cwd=root, timeout=20)
    status = run_command(["git", "status", "--short"], cwd=root, timeout=20)
    return {
        "branch": branch.stdout.strip(),
        "clean": status.stdout.strip() == "",
        "status_short": status.stdout.strip(),
    }


def _docker_summary(docker: DockerRunner) -> dict[str, Any]:
    version = docker.docker(["version"], timeout=60)
    compose = docker.docker(["compose", "version"], timeout=60)
    context = docker.docker(["context", "show"], timeout=30)
    return {
        "daemon_reachable": version.returncode == 0,
        "version": redact(f"{version.stdout}\n{version.stderr}".strip()),
        "compose": redact(f"{compose.stdout}\n{compose.stderr}".strip()),
        "context": redact(context.stdout.strip() or context.stderr.strip()),
    }


def _image_summary(docker: DockerRunner) -> dict[str, Any]:
    images: dict[str, Any] = {}
    for name, image in {
        "gitea": docker.config.gitea_image,
        "postgres": docker.config.postgres_image,
    }.items():
        result = docker.docker(
            ["image", "inspect", image, "--format", "{{.Id}}"],
            timeout=60,
        )
        images[name] = {
            "image": image,
            "available": result.returncode == 0,
            "id": result.stdout.strip() if result.returncode == 0 else None,
        }
    return images


def _compose_config_summary(docker: DockerRunner) -> dict[str, Any]:
    result = docker.compose(["config", "--quiet"], timeout=120)
    return {"ok": result.returncode == 0, "stderr": redact(result.stderr)}


def _resource_summary(docker: DockerRunner) -> dict[str, Any]:
    return {
        "network": docker.inspect_network(docker.network_name()) is not None,
        "volumes": {
            volume: docker.inspect_volume(docker.volume_name(volume)) is not None
            for volume in VOLUMES
        },
    }


def _port_summary(root: Path, ports: list[int]) -> dict[str, Any]:
    netstat = _netstat(root)
    summary: dict[str, Any] = {}
    for port in ports:
        summary[str(port)] = {
            "localhost_connect": _can_connect(port),
            "netstat_listeners": [
                line.strip()
                for line in netstat.splitlines()
                if f":{port} " in line or f":{port}\t" in line
            ],
        }
    return summary


def _can_connect(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def _netstat(root: Path) -> str:
    command = (
        ["netstat.exe", "-ano", "-p", "tcp"]
        if platform.system() == "Windows"
        else ["ss", "-ltnp"]
    )
    result = run_command(command, cwd=root, timeout=30)
    return redact(f"{result.stdout}\n{result.stderr}")


def _runtime_readiness(
    config: SandboxConfig,
    docker: DockerRunner,
) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    postgres = docker.exec(
        "postgres",
        [
            "psql",
            "-U",
            config.postgres_user,
            "-d",
            config.postgres_db,
            "-tAc",
            "SELECT 1;",
        ],
        timeout=60,
    )
    summary["postgres_query"] = (
        postgres.returncode == 0 and postgres.stdout.strip() == "1"
    )
    try:
        health = ApiClient(
            config.root_url.rstrip("/"),
            timeout=config.http_timeout,
            retries=1,
        ).get("api/healthz")
        summary["gitea_health"] = (
            isinstance(health, dict) and health.get("status") == "pass"
        )
    except Exception as exc:  # noqa: BLE001 - diagnostics must keep going.
        summary["gitea_health"] = False
        summary["gitea_health_error"] = redact(str(exc))
    return summary


def _api_auth_summary(config: SandboxConfig) -> dict[str, Any]:
    token = _read_token(config)
    if token is None:
        return {"ok": False, "reason": "token file missing or invalid"}
    try:
        user = ApiClient(
            config.api_base_url,
            token=token,
            timeout=config.http_timeout,
            retries=1,
        ).get("user")
    except Exception as exc:  # noqa: BLE001 - diagnostics must keep going.
        return {"ok": False, "error": redact(str(exc))}
    return {
        "ok": isinstance(user, dict) and user.get("login") == config.admin_user,
        "user": user.get("login") if isinstance(user, dict) else None,
    }


def _fixture_summary(config: SandboxConfig) -> dict[str, Any]:
    token = _read_token(config)
    if token is None:
        return {"ok": False, "reason": "token file missing or invalid"}
    try:
        result = validate_api_with_client(
            config,
            ApiClient(
                config.api_base_url,
                token=token,
                timeout=config.http_timeout,
                retries=1,
            ),
        )
    except Exception as exc:  # noqa: BLE001 - diagnostics must keep going.
        return {"ok": False, "error": redact(str(exc))}
    return {
        "ok": True,
        "repository": result.get("repository"),
        "duplicates": result.get("duplicates"),
    }


def _read_token(config: SandboxConfig) -> str | None:
    try:
        payload = json.loads(config.token_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    token = payload.get("token") if isinstance(payload, dict) else None
    return token if isinstance(token, str) and token else None


def _snapshot_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "bundles": 0}
    bundles = [child.name for child in path.iterdir() if child.is_dir()]
    return {"exists": True, "bundles": len(bundles), "recent": sorted(bundles)[-5:]}


def _logs_summary(docker: DockerRunner) -> dict[str, str]:
    logs: dict[str, str] = {}
    for service in SERVICES:
        result = docker.compose(
            ["logs", "--no-color", "--tail", "40", service], timeout=60
        )
        logs[service] = redact((result.stdout or result.stderr)[-4000:])
    return logs


def _human(checks: dict[str, Any]) -> str:
    lines = [
        "gitea-sandbox diagnose",
        f"package: {checks.get('package_version')}",
        f"python: {checks.get('python')}",
        f"os: {checks.get('operating_system')}",
    ]
    git = checks.get("git", {})
    if isinstance(git, dict):
        lines.append(f"git branch: {git.get('branch')}")
        lines.append(f"git clean: {git.get('clean')}")
    configuration = checks.get("configuration", {})
    if isinstance(configuration, dict):
        lines.append(f".env present: {configuration.get('env_present')}")
        lines.append(f"http endpoint: {configuration.get('http_endpoint')}")
        lines.append(f"ssh endpoint: {configuration.get('ssh_endpoint')}")
    for container in checks.get("containers", []):
        lines.append(
            "service "
            f"{container.get('service')}: state={container.get('state')} "
            f"health={container.get('health')}"
        )
    runtime = checks.get("runtime_readiness", {})
    if isinstance(runtime, dict):
        lines.append(f"postgres query: {runtime.get('postgres_query')}")
        lines.append(f"gitea health endpoint: {runtime.get('gitea_health')}")
    api_auth = checks.get("api_auth", {})
    if isinstance(api_auth, dict):
        lines.append(f"api authentication: {api_auth.get('ok')}")
    fixture = checks.get("fixture_validation", {})
    if isinstance(fixture, dict):
        lines.append(f"fixture validation: {fixture.get('ok')}")
    lines.append(f"summary: {checks.get('summary', 'configuration unavailable')}")
    return "\n".join(lines)
