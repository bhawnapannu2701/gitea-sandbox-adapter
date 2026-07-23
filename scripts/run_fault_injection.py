"""Run controlled Phase 2 fault-injection checks against project resources."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from gitea_sandbox_adapter.config import ConfigError, load_config
from gitea_sandbox_adapter.docker import DockerRunner
from gitea_sandbox_adapter.errors import SnapshotError
from gitea_sandbox_adapter.ports import select_ports
from gitea_sandbox_adapter.runtime import run_command
from gitea_sandbox_adapter.snapshot import restore_snapshot


def main() -> int:
    config = load_config()
    docker = DockerRunner(config)
    failures: list[str] = []

    _print("fault-injection runner started")
    for name, scenario in (
        ("postgres stopped", lambda: _postgres_stopped(config, docker)),
        ("gitea stopped", lambda: _gitea_stopped(config, docker)),
        ("corrupt snapshot", lambda: _corrupt_snapshot(config, docker)),
        ("missing configuration", _missing_configuration),
        ("occupied port selection", _occupied_port_selection),
    ):
        try:
            _print(f"scenario: {name}")
            scenario()
            _print(f"scenario passed: {name}")
        except Exception as exc:  # noqa: BLE001 - runner reports all failures.
            failures.append(f"{name}: {exc}")
            _print(f"scenario failed: {name}: {exc}")
            _recover(config, docker)

    _recover(config, docker)
    if failures:
        _print("fault-injection runner failed")
        for failure in failures:
            _print(f"- {failure}")
        return 1
    _print("fault-injection runner passed")
    return 0


def _postgres_stopped(config: object, docker: DockerRunner) -> None:
    docker.stop_service("postgres")
    status = _cli("status")
    diagnose = _cli("diagnose")
    _expect_nonzero(status.returncode, "status should fail when PostgreSQL is stopped")
    _expect_nonzero(
        diagnose.returncode,
        "diagnose should fail when PostgreSQL is stopped",
    )
    _recover(config, docker)
    _expect_zero(_cli("validate", "--api-only").returncode, "API validation recovery")


def _gitea_stopped(config: object, docker: DockerRunner) -> None:
    docker.stop_service("gitea")
    status = _cli("status")
    diagnose = _cli("diagnose")
    _expect_nonzero(status.returncode, "status should fail when Gitea is stopped")
    _expect_nonzero(diagnose.returncode, "diagnose should fail when Gitea is stopped")
    _recover(config, docker)
    _expect_zero(_cli("validate", "--api-only").returncode, "API validation recovery")


def _corrupt_snapshot(config: object, docker: DockerRunner) -> None:
    typed_config = load_config()
    source = _latest_snapshot(typed_config.snapshots_dir)
    temp_root = typed_config.runtime_dir / "fault-injection"
    corrupt = temp_root / "corrupt-snapshot"
    _safe_rmtree(temp_root, typed_config.runtime_dir)
    shutil.copytree(source, corrupt)
    manifest = corrupt / "manifest.json"
    text = manifest.read_text(encoding="utf-8")
    manifest.write_text(text.replace('"sha256": "', '"sha256": "0'), encoding="utf-8")
    try:
        restore_snapshot(
            typed_config,
            docker,
            corrupt,
            force=True,
            safety_snapshot=False,
        )
    except SnapshotError:
        pass
    else:
        raise AssertionError("restore accepted a corrupt snapshot")
    _expect_zero(
        _cli("validate", "--api-only").returncode,
        "live state after corrupt snapshot",
    )
    _safe_rmtree(temp_root, typed_config.runtime_dir)


def _missing_configuration() -> None:
    config = load_config(require_env=False)
    temp_root = config.runtime_dir / "fault-injection" / "missing-config"
    _safe_rmtree(temp_root, config.runtime_dir)
    (temp_root / "src").mkdir(parents=True)
    (temp_root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    try:
        load_config(repo_root=temp_root, require_env=True, environ={})
    except ConfigError:
        pass
    else:
        raise AssertionError("missing .env configuration was accepted")
    _safe_rmtree(temp_root, config.runtime_dir)


def _occupied_port_selection() -> None:
    unavailable = {3000, 2222}
    selected_http, selected_ssh = select_ports(
        3000,
        2222,
        is_available=lambda port: port not in unavailable,
    )
    if selected_http == 3000 or selected_ssh == 2222:
        raise AssertionError("occupied preferred ports were selected")
    if selected_http == selected_ssh:
        raise AssertionError("HTTP and SSH ports collided")


def _recover(config: object, docker: DockerRunner) -> None:
    del config
    docker.compose(["up", "-d"], timeout=600, check=True)
    docker.wait_for_healthy()


def _cli(*args: str):
    return run_command(
        [sys.executable, "-m", "gitea_sandbox_adapter", *args],
        cwd=Path.cwd(),
        timeout=300,
    )


def _latest_snapshot(path: Path) -> Path:
    snapshots = sorted(
        child for child in path.iterdir() if (child / "manifest.json").exists()
    )
    if not snapshots:
        raise AssertionError(
            "no snapshot bundle available for corrupt snapshot scenario"
        )
    return snapshots[-1]


def _safe_rmtree(path: Path, root: Path) -> None:
    resolved = path.resolve()
    root_resolved = root.resolve()
    if root_resolved not in (resolved, *resolved.parents):
        raise AssertionError(f"refusing to remove path outside runtime root: {path}")
    if path.exists():
        shutil.rmtree(path)


def _expect_zero(exit_code: int, message: str) -> None:
    _print(f"{message}: exit_code={exit_code}")
    if exit_code != 0:
        raise AssertionError(message)


def _expect_nonzero(exit_code: int, message: str) -> None:
    _print(f"{message}: exit_code={exit_code}")
    if exit_code == 0:
        raise AssertionError(message)


def _print(message: str) -> None:
    print(message, flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
