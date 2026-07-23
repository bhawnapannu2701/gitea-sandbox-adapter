from __future__ import annotations

import json
import tarfile
from pathlib import Path
from typing import Any, cast

import pytest

import gitea_sandbox_adapter.browser_validation as browser_validation_module
import gitea_sandbox_adapter.population as population_module
import gitea_sandbox_adapter.snapshot as snapshot_module
from gitea_sandbox_adapter.docker import DockerRunner
from gitea_sandbox_adapter.errors import SnapshotError
from gitea_sandbox_adapter.models import CommandResult, ServiceStatus
from gitea_sandbox_adapter.snapshot import (
    POSTGRES_DUMP,
    reset_sandbox,
    restore_snapshot,
    validate_bundle,
    validate_tar_archive,
)
from tests.test_docker import fake_config


def test_validate_tar_rejects_path_traversal(tmp_path: Path) -> None:
    archive_path = tmp_path / "bad.tar.gz"
    payload = tmp_path / "payload.txt"
    payload.write_text("x", encoding="utf-8")
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(payload, arcname="../payload.txt")

    with pytest.raises(SnapshotError, match="Unsafe archive member"):
        validate_tar_archive(archive_path)


def test_validate_bundle_rejects_checksum_mismatch(tmp_path: Path) -> None:
    bundle = tmp_path / "snapshot"
    bundle.mkdir()
    payload = bundle / "postgres.dump"
    payload.write_bytes(b"real")
    (bundle / "gitea-data.tar.gz").write_bytes(b"not-a-tar")
    (bundle / "gitea-config.tar.gz").write_bytes(b"not-a-tar")
    manifest = {
        "schema_version": 1,
        "payloads": {
            "postgres.dump": {"sha256": "0" * 64, "bytes": 4},
            "gitea-data.tar.gz": {"sha256": "0" * 64, "bytes": 9},
            "gitea-config.tar.gz": {"sha256": "0" * 64, "bytes": 9},
        },
    }
    (bundle / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotError, match="Checksum mismatch"):
        validate_bundle(bundle)


def test_restore_uses_default_runtime_browser_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = fake_config(tmp_path)
    bundle = tmp_path / "snapshot"
    bundle.mkdir()
    (bundle / POSTGRES_DUMP).write_bytes(b"dump")
    docker = FakeSnapshotDocker(config.project_name)
    captured: dict[str, Any] = {}

    monkeypatch.setattr(
        snapshot_module,
        "validate_bundle",
        lambda _bundle: {"compose_project": config.project_name},
    )
    monkeypatch.setattr(snapshot_module, "create_snapshot", lambda *_args: None)
    monkeypatch.setattr(snapshot_module, "_restore_tar_to_volume", lambda *_args: None)
    monkeypatch.setattr(snapshot_module, "validate_runtime", lambda *_args: {})
    monkeypatch.setattr(snapshot_module, "validate_postgres", lambda *_args: "postgres")
    monkeypatch.setattr(snapshot_module, "validate_api", lambda *_args: {})

    def fake_validate_browser(config_arg: object, **kwargs: Any) -> dict[str, Any]:
        del config_arg
        captured.update(kwargs)
        return {}

    monkeypatch.setattr(
        browser_validation_module,
        "validate_browser",
        fake_validate_browser,
    )

    restore_snapshot(
        config,
        cast(DockerRunner, docker),
        bundle,
        force=True,
        safety_snapshot=False,
    )

    assert captured == {}


def test_reset_uses_default_runtime_browser_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = fake_config(tmp_path)
    docker = FakeSnapshotDocker(config.project_name)
    captured: dict[str, Any] = {}

    monkeypatch.setattr(snapshot_module, "create_snapshot", lambda *_args: None)
    monkeypatch.setattr(snapshot_module, "validate_runtime", lambda *_args: {})
    monkeypatch.setattr(snapshot_module, "validate_postgres", lambda *_args: "postgres")
    monkeypatch.setattr(snapshot_module, "validate_api", lambda *_args: {})
    monkeypatch.setattr(population_module, "populate", lambda *_args: {})

    def fake_validate_browser(config_arg: object, **kwargs: Any) -> dict[str, Any]:
        del config_arg
        captured.update(kwargs)
        return {}

    monkeypatch.setattr(
        browser_validation_module,
        "validate_browser",
        fake_validate_browser,
    )

    reset_sandbox(
        config,
        cast(DockerRunner, docker),
        force=True,
        safety_snapshot=False,
    )

    assert captured == {}


class FakeSnapshotDocker:
    def __init__(self, project_name: str) -> None:
        self.project_name = project_name

    def all_statuses(self) -> list[ServiceStatus]:
        return [
            ServiceStatus("postgres", "postgres-id", "postgres", "running", "healthy"),
            ServiceStatus("gitea", "gitea-id", "gitea", "running", "healthy"),
        ]

    def assert_owned_volume(self, _volume: str) -> None:
        return None

    def assert_owned_network(self) -> None:
        return None

    def down_preserve_volumes(self) -> None:
        return None

    def remove_owned_volumes(self) -> list[str]:
        return [
            f"{self.project_name}_postgres_data",
            f"{self.project_name}_gitea_data",
            f"{self.project_name}_gitea_config",
        ]

    def volume_name(self, volume: str) -> str:
        return f"{self.project_name}_{volume}"

    def docker(
        self,
        _args: list[str],
        *,
        timeout: int = 60,
    ) -> CommandResult:
        del timeout
        return CommandResult((), 0, "", "")

    def compose(
        self,
        _args: list[str],
        *,
        timeout: int = 120,
        check: bool = False,
    ) -> CommandResult:
        del timeout, check
        return CommandResult((), 0, "", "")

    def wait_for_healthy(
        self,
        _services: tuple[str, ...] = ("postgres", "gitea"),
    ) -> list[ServiceStatus]:
        return self.all_statuses()

    def exec(
        self,
        _service: str,
        _command: list[str],
        *,
        timeout: int = 120,
        input_bytes: bytes | None = None,
    ) -> CommandResult:
        del timeout, input_bytes
        return CommandResult((), 0, "", "")

    def up(self) -> None:
        return None
