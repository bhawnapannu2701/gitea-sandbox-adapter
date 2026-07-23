from __future__ import annotations

import json
from pathlib import Path

import pytest

from gitea_sandbox_adapter.config import SandboxConfig
from gitea_sandbox_adapter.docker import DockerRunner
from gitea_sandbox_adapter.errors import DockerError
from gitea_sandbox_adapter.models import CommandResult


def fake_config(tmp_path: Path) -> SandboxConfig:
    return SandboxConfig(
        repo_root=tmp_path,
        env_file=tmp_path / ".env",
        compose_file=tmp_path / "compose.yaml",
        project_name="gitea_sandbox_adapter",
        gitea_image="docker.gitea.com/gitea:1.27.0-rootless",
        postgres_image="docker.io/library/postgres:16.14-bookworm",
        http_port=3000,
        ssh_port=2222,
        postgres_db="gitea",
        postgres_user="gitea",
        postgres_password="secret",
        admin_user="sandbox-admin",
        admin_password="secret",
        admin_email="sandbox-admin@example.invalid",
        token_name="token",
        start_timeout=1,
        stop_timeout=1,
        poll_interval=0.01,
        http_timeout=1,
        http_retries=1,
        browser_timeout_ms=1000,
    )


def test_service_status_missing_when_compose_has_no_container(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    docker = DockerRunner(fake_config(tmp_path))
    monkeypatch.setattr(
        docker,
        "compose",
        lambda *args, **kwargs: CommandResult((), 0, "", ""),
    )

    status = docker.service_status("gitea")

    assert status.state == "missing"
    assert not status.is_healthy


def test_service_status_healthy_from_inspect(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    docker = DockerRunner(fake_config(tmp_path))

    def fake_compose(*args: object, **kwargs: object) -> CommandResult:
        return CommandResult((), 0, "abc123\n", "")

    def fake_docker(*args: object, **kwargs: object) -> CommandResult:
        return CommandResult(
            (),
            0,
            json.dumps(
                [
                    {
                        "Name": "/project-gitea-1",
                        "State": {"Status": "running", "Health": {"Status": "healthy"}},
                    }
                ]
            ),
            "",
        )

    monkeypatch.setattr(docker, "compose", fake_compose)
    monkeypatch.setattr(docker, "docker", fake_docker)

    status = docker.service_status("gitea")

    assert status.is_healthy


def test_unowned_volume_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    docker = DockerRunner(fake_config(tmp_path))
    monkeypatch.setattr(
        docker,
        "inspect_volume",
        lambda _name: {"Labels": {"com.docker.compose.project": "other"}},
    )

    with pytest.raises(DockerError):
        docker.assert_owned_volume("gitea_data")
