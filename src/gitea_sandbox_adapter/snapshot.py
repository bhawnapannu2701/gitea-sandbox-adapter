"""Snapshot and restore support."""

from __future__ import annotations

import json
import tarfile
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from gitea_sandbox_adapter.config import SandboxConfig
from gitea_sandbox_adapter.docker import VOLUMES, DockerRunner
from gitea_sandbox_adapter.errors import SnapshotError
from gitea_sandbox_adapter.population import fixture_hash
from gitea_sandbox_adapter.validation import (
    validate_api,
    validate_postgres,
    validate_runtime,
)

POSTGRES_DUMP = "postgres.dump"
GITEA_DATA_ARCHIVE = "gitea-data.tar.gz"
GITEA_CONFIG_ARCHIVE = "gitea-config.tar.gz"
MANIFEST = "manifest.json"


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_snapshot(
    config: SandboxConfig,
    docker: DockerRunner,
    *,
    output: Path | None = None,
) -> Path:
    validate_runtime(config, docker)
    snapshot_dir = _snapshot_dir(config, output)
    if snapshot_dir.exists():
        raise SnapshotError(f"Snapshot output already exists: {snapshot_dir}")
    snapshot_dir.mkdir(parents=True)
    postgres_dump = snapshot_dir / POSTGRES_DUMP
    data_archive = snapshot_dir / GITEA_DATA_ARCHIVE
    config_archive = snapshot_dir / GITEA_CONFIG_ARCHIVE

    gitea_was_stopped = False
    try:
        gitea_id = docker.container_id("gitea")
        if not gitea_id:
            raise SnapshotError("Gitea container is missing.")
        docker.stop_service("gitea")
        gitea_was_stopped = True
        dump_result = docker.exec(
            "postgres",
            [
                "pg_dump",
                "-U",
                config.postgres_user,
                "-d",
                config.postgres_db,
                "-F",
                "c",
                "--no-owner",
                "--no-privileges",
            ],
            timeout=300,
            stdout_path=postgres_dump,
        )
        if dump_result.returncode != 0:
            raise SnapshotError(f"pg_dump failed: {dump_result.stderr}")
        _archive_from_container(docker, gitea_id, "/var/lib/gitea", data_archive)
        _archive_from_container(docker, gitea_id, "/etc/gitea", config_archive)
    finally:
        if gitea_was_stopped:
            docker.start_service("gitea")
            docker.wait_for_healthy(("gitea",))

    payloads = [postgres_dump, data_archive, config_archive]
    manifest = {
        "schema_version": 1,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "package": "gitea-sandbox-adapter",
        "compose_project": config.project_name,
        "images": {
            "gitea": config.gitea_image,
            "postgres": config.postgres_image,
        },
        "database": {
            "name": config.postgres_db,
            "user": config.postgres_user,
        },
        "fixture_manifest_sha256": fixture_hash(config),
        "payloads": {
            payload.name: {
                "sha256": sha256_file(payload),
                "bytes": payload.stat().st_size,
            }
            for payload in payloads
        },
    }
    (snapshot_dir / MANIFEST).write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    validate_bundle(snapshot_dir)
    return snapshot_dir


def validate_bundle(path: Path) -> dict[str, Any]:
    bundle = path.resolve()
    manifest_path = bundle / MANIFEST
    if not bundle.is_dir() or not manifest_path.is_file():
        raise SnapshotError(
            "Snapshot bundle must be a directory containing manifest.json."
        )
    loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise SnapshotError("Snapshot manifest must be a JSON object.")
    manifest = cast(dict[str, Any], loaded)
    if manifest.get("schema_version") != 1:
        raise SnapshotError("Unsupported snapshot schema_version.")
    payloads = manifest.get("payloads")
    if not isinstance(payloads, dict):
        raise SnapshotError("Snapshot manifest payloads must be an object.")
    for name, metadata in payloads.items():
        if Path(name).name != name:
            raise SnapshotError(f"Unsafe snapshot payload name: {name}")
        payload_path = bundle / name
        if not payload_path.is_file():
            raise SnapshotError(f"Missing snapshot payload: {name}")
        if sha256_file(payload_path) != metadata.get("sha256"):
            raise SnapshotError(f"Checksum mismatch for snapshot payload: {name}")
        if name.endswith(".tar.gz"):
            validate_tar_archive(payload_path)
    for required in (POSTGRES_DUMP, GITEA_DATA_ARCHIVE, GITEA_CONFIG_ARCHIVE):
        if required not in payloads:
            raise SnapshotError(f"Missing required snapshot payload: {required}")
    return manifest


def restore_snapshot(
    config: SandboxConfig,
    docker: DockerRunner,
    bundle: Path,
    *,
    force: bool,
    safety_snapshot: bool = True,
) -> dict[str, Any]:
    if not force:
        raise SnapshotError("restore requires --force and made no changes.")
    manifest = validate_bundle(bundle)
    if manifest.get("compose_project") != config.project_name:
        raise SnapshotError(
            "Snapshot compose project does not match this configuration."
        )

    pre_restore: Path | None = None
    if safety_snapshot and all(status.is_healthy for status in docker.all_statuses()):
        pre_restore = create_snapshot(config, docker)

    for volume in VOLUMES:
        docker.assert_owned_volume(volume)
    docker.assert_owned_network()
    docker.down_preserve_volumes()
    removed = docker.remove_owned_volumes()

    for volume in VOLUMES:
        name = docker.volume_name(volume)
        result = docker.docker(
            [
                "volume",
                "create",
                "--label",
                f"com.docker.compose.project={config.project_name}",
                "--label",
                f"com.docker.compose.volume={volume}",
                name,
            ],
            timeout=60,
        )
        if result.returncode != 0:
            raise SnapshotError(f"Failed to recreate volume {name}: {result.stderr}")

    _restore_tar_to_volume(
        config,
        docker,
        bundle / GITEA_DATA_ARCHIVE,
        docker.volume_name("gitea_data"),
        "/var/lib/gitea",
    )
    _restore_tar_to_volume(
        config,
        docker,
        bundle / GITEA_CONFIG_ARCHIVE,
        docker.volume_name("gitea_config"),
        "/etc/gitea",
    )

    docker.compose(["up", "-d", "postgres"], timeout=config.start_timeout, check=True)
    docker.wait_for_healthy(("postgres",))
    dump_bytes = (bundle / POSTGRES_DUMP).read_bytes()
    restore_result = docker.exec(
        "postgres",
        [
            "pg_restore",
            "-U",
            config.postgres_user,
            "-d",
            config.postgres_db,
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
        ],
        timeout=300,
        input_bytes=dump_bytes,
    )
    if restore_result.returncode != 0:
        raise SnapshotError(f"pg_restore failed: {restore_result.stderr}")

    docker.up()
    docker.wait_for_healthy()
    validate_runtime(config, docker)
    validate_postgres(config, docker)
    validate_api(config, docker)
    from gitea_sandbox_adapter.browser_validation import validate_browser

    validate_browser(config)
    return {
        "removed_volumes": removed,
        "pre_restore_safety_snapshot": _relative_snapshot(config, pre_restore),
    }


def reset_sandbox(
    config: SandboxConfig,
    docker: DockerRunner,
    *,
    force: bool,
    safety_snapshot: bool = True,
) -> dict[str, Any]:
    if not force:
        raise SnapshotError("reset requires --force and made no changes.")
    pre_reset: Path | None = None
    if safety_snapshot and all(status.is_healthy for status in docker.all_statuses()):
        pre_reset = create_snapshot(config, docker)
    for volume in VOLUMES:
        docker.assert_owned_volume(volume)
    docker.assert_owned_network()
    docker.down_preserve_volumes()
    removed = docker.remove_owned_volumes()
    docker.up()
    docker.wait_for_healthy()
    from gitea_sandbox_adapter.population import populate

    population = populate(config, docker)
    validate_runtime(config, docker)
    validate_postgres(config, docker)
    validate_api(config, docker)
    from gitea_sandbox_adapter.browser_validation import validate_browser

    validate_browser(config)
    return {
        "removed_volumes": removed,
        "pre_reset_safety_snapshot": _relative_snapshot(config, pre_reset),
        "population": population,
    }


def validate_tar_archive(path: Path) -> None:
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            member_path = Path(member.name)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise SnapshotError(f"Unsafe archive member path: {member.name}")
            if member.issym() or member.islnk():
                raise SnapshotError(
                    f"Archive contains rejected link member: {member.name}"
                )


def _snapshot_dir(config: SandboxConfig, output: Path | None) -> Path:
    if output is not None:
        return output.resolve()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return config.snapshots_dir / f"phase2-{stamp}"


def _relative_snapshot(config: SandboxConfig, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.relative_to(config.repo_root))
    except ValueError:
        return "<external-snapshot-path>"


def _archive_from_container(
    docker: DockerRunner,
    container_id: str,
    source: str,
    output: Path,
) -> None:
    result = docker.run_container(
        [
            "--rm",
            "--volumes-from",
            container_id,
            "--entrypoint",
            "tar",
            docker.config.gitea_image,
            "-czf",
            "-",
            "-C",
            source,
            ".",
        ],
        timeout=300,
        stdout_path=output,
    )
    if result.returncode != 0:
        raise SnapshotError(f"Failed to archive {source}: {result.stderr}")
    validate_tar_archive(output)


def _restore_tar_to_volume(
    config: SandboxConfig,
    docker: DockerRunner,
    archive: Path,
    volume: str,
    target: str,
) -> None:
    validate_tar_archive(archive)
    result = docker.run_container(
        [
            "--rm",
            "-i",
            "-v",
            f"{volume}:{target}",
            "--entrypoint",
            "tar",
            config.gitea_image,
            "-xzf",
            "-",
            "-C",
            target,
        ],
        timeout=300,
        input_bytes=archive.read_bytes(),
    )
    if result.returncode != 0:
        raise SnapshotError(f"Failed to restore archive into {volume}: {result.stderr}")
