"""Docker and Docker Compose integration."""

from __future__ import annotations

import json
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

from gitea_sandbox_adapter.config import SandboxConfig
from gitea_sandbox_adapter.errors import DockerError
from gitea_sandbox_adapter.models import CommandResult, ServiceStatus
from gitea_sandbox_adapter.redaction import redact
from gitea_sandbox_adapter.runtime import run_command

SERVICES = ("postgres", "gitea")
VOLUMES = ("postgres_data", "gitea_data", "gitea_config")
NETWORK = "sandbox"


class DockerRunner:
    def __init__(self, config: SandboxConfig) -> None:
        self.config = config

    def docker(
        self, args: list[str], *, timeout: int = 60, check: bool = False
    ) -> CommandResult:
        return run_command(
            ["docker", *args],
            cwd=self.config.repo_root,
            timeout=timeout,
            check=check,
        )

    def compose(
        self,
        args: list[str],
        *,
        timeout: int = 120,
        check: bool = False,
        input_bytes: bytes | None = None,
        stdout_path: Path | None = None,
    ) -> CommandResult:
        base = [
            "docker",
            "compose",
            "--env-file",
            str(self.config.env_file),
            "-f",
            str(self.config.compose_file),
            "-p",
            self.config.project_name,
        ]
        return run_command(
            [*base, *args],
            cwd=self.config.repo_root,
            timeout=timeout,
            check=check,
            input_bytes=input_bytes,
            stdout_path=stdout_path,
        )

    def check_docker_available(self) -> None:
        result = self.docker(["version"], timeout=60)
        if result.returncode != 0:
            raise DockerError(redact(f"Docker daemon is unavailable:\n{result.stderr}"))
        compose = self.docker(["compose", "version"], timeout=60)
        if compose.returncode != 0 or "Docker Compose version v2" not in compose.stdout:
            raise DockerError(
                redact(f"Docker Compose V2 is unavailable:\n{compose.stderr}")
            )

    def compose_config(self) -> CommandResult:
        result = self.compose(["config"], timeout=120)
        if result.returncode != 0:
            raise DockerError(redact(f"docker compose config failed:\n{result.stderr}"))
        return result

    def ensure_images(self) -> list[CommandResult]:
        results: list[CommandResult] = []
        for image in (self.config.gitea_image, self.config.postgres_image):
            inspect = self.docker(["image", "inspect", image], timeout=60)
            if inspect.returncode == 0:
                results.append(inspect)
                continue
            pull = self.docker(["pull", image], timeout=600)
            if pull.returncode != 0:
                raise DockerError(redact(f"Failed to pull {image}:\n{pull.stderr}"))
            results.append(pull)
        return results

    def up(self) -> None:
        result = self.compose(["up", "-d"], timeout=600)
        if result.returncode != 0:
            raise DockerError(redact(f"docker compose up failed:\n{result.stderr}"))

    def down_preserve_volumes(self) -> None:
        result = self.compose(["down"], timeout=self.config.stop_timeout)
        if result.returncode != 0:
            raise DockerError(redact(f"docker compose down failed:\n{result.stderr}"))

    def stop_service(self, service: str) -> None:
        result = self.compose(["stop", service], timeout=self.config.stop_timeout)
        if result.returncode != 0:
            raise DockerError(redact(f"Failed to stop {service}:\n{result.stderr}"))

    def start_service(self, service: str) -> None:
        result = self.compose(["start", service], timeout=self.config.start_timeout)
        if result.returncode != 0:
            raise DockerError(redact(f"Failed to start {service}:\n{result.stderr}"))

    def exec(
        self,
        service: str,
        command: list[str],
        *,
        timeout: int = 120,
        check: bool = False,
        input_bytes: bytes | None = None,
        stdout_path: Path | None = None,
    ) -> CommandResult:
        return self.compose(
            ["exec", "-T", service, *command],
            timeout=timeout,
            check=check,
            input_bytes=input_bytes,
            stdout_path=stdout_path,
        )

    def run_container(
        self,
        args: list[str],
        *,
        timeout: int = 120,
        check: bool = False,
        input_bytes: bytes | None = None,
        stdout_path: Path | None = None,
    ) -> CommandResult:
        return run_command(
            ["docker", "run", *args],
            cwd=self.config.repo_root,
            timeout=timeout,
            check=check,
            input_bytes=input_bytes,
            stdout_path=stdout_path,
        )

    def container_id(self, service: str) -> str | None:
        result = self.compose(["ps", "-q", service], timeout=60)
        if result.returncode != 0:
            return None
        value = result.stdout.strip()
        return value or None

    def inspect_container(self, container_id: str) -> dict[str, Any] | None:
        result = self.docker(["inspect", container_id], timeout=60)
        if result.returncode != 0:
            return None
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, list) or not data:
            return None
        if not isinstance(data[0], dict):
            return None
        return cast(dict[str, Any], data[0])

    def service_status(self, service: str) -> ServiceStatus:
        cid = self.container_id(service)
        if cid is None:
            return ServiceStatus(service, None, None, "missing", None)
        data = self.inspect_container(cid)
        if data is None:
            return ServiceStatus(service, cid, None, "unknown", None)
        state = data.get("State", {})
        health = state.get("Health", {}).get("Status")
        return ServiceStatus(
            service=service,
            container_id=cid,
            container_name=str(data.get("Name", "")).lstrip("/") or None,
            state=str(state.get("Status", "unknown")),
            health=str(health) if health is not None else None,
        )

    def all_statuses(self) -> list[ServiceStatus]:
        return [self.service_status(service) for service in SERVICES]

    def wait_for_healthy(
        self, services: Iterable[str] = SERVICES
    ) -> list[ServiceStatus]:
        deadline = time.monotonic() + self.config.start_timeout
        service_tuple = tuple(services)
        last_statuses: list[ServiceStatus] = []
        while time.monotonic() < deadline:
            last_statuses = [self.service_status(service) for service in service_tuple]
            if all(status.is_healthy for status in last_statuses):
                return last_statuses
            time.sleep(self.config.poll_interval)
        summary = ", ".join(
            f"{status.service} state={status.state} health={status.health}"
            for status in last_statuses
        )
        raise DockerError(f"Timed out waiting for healthy services: {summary}")

    def compose_resource_name(self, resource: str) -> str:
        return f"{self.config.project_name}_{resource}"

    def volume_name(self, volume: str) -> str:
        return self.compose_resource_name(volume)

    def network_name(self) -> str:
        return self.compose_resource_name(NETWORK)

    def inspect_volume(self, volume_name: str) -> dict[str, Any] | None:
        result = self.docker(["volume", "inspect", volume_name], timeout=60)
        if result.returncode != 0:
            return None
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            return None
        return cast(dict[str, Any], data[0])

    def inspect_network(self, network_name: str) -> dict[str, Any] | None:
        result = self.docker(["network", "inspect", network_name], timeout=60)
        if result.returncode != 0:
            return None
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            return None
        return cast(dict[str, Any], data[0])

    def assert_owned_volume(self, volume: str) -> None:
        name = self.volume_name(volume)
        data = self.inspect_volume(name)
        if data is None:
            return
        labels = data.get("Labels") or {}
        if labels.get("com.docker.compose.project") != self.config.project_name:
            raise DockerError(f"Refusing to use unowned Docker volume: {name}")
        if labels.get("com.docker.compose.volume") != volume:
            raise DockerError(f"Refusing to use unexpected Docker volume: {name}")

    def assert_owned_network(self) -> None:
        name = self.network_name()
        data = self.inspect_network(name)
        if data is None:
            return
        labels = data.get("Labels") or {}
        if labels.get("com.docker.compose.project") != self.config.project_name:
            raise DockerError(f"Refusing to use unowned Docker network: {name}")
        if labels.get("com.docker.compose.network") != NETWORK:
            raise DockerError(f"Refusing to use unexpected Docker network: {name}")

    def remove_owned_volumes(self) -> list[str]:
        removed: list[str] = []
        for volume in VOLUMES:
            self.assert_owned_volume(volume)
            name = self.volume_name(volume)
            if self.inspect_volume(name) is None:
                continue
            result = self.docker(["volume", "rm", name], timeout=90)
            if result.returncode != 0:
                raise DockerError(redact(f"Failed to remove {name}:\n{result.stderr}"))
            removed.append(name)
        return removed
