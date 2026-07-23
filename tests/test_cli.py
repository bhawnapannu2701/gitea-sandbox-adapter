from __future__ import annotations

import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

import pytest

import gitea_sandbox_adapter
import gitea_sandbox_adapter.cli as cli_module
from gitea_sandbox_adapter import __version__
from gitea_sandbox_adapter.cli import COMMANDS

CLI_TIMEOUT_SECONDS = 15

EXPECTED_COMMANDS = (
    "start",
    "stop",
    "status",
    "populate",
    "validate",
    "snapshot",
    "restore",
    "reset",
    "diagnose",
)


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, "-m", "gitea_sandbox_adapter", *args]
    try:
        return subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=CLI_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = _completed_text(exc.stdout)
        stderr = _completed_text(exc.stderr)
        pytest.fail(
            "CLI command timed out after "
            f"{CLI_TIMEOUT_SECONDS}s: {' '.join(command)}\n"
            f"stdout:\n{stdout}\nstderr:\n{stderr}"
        )


def _completed_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def test_package_import() -> None:
    assert gitea_sandbox_adapter.__version__ == __version__


def test_package_metadata_version_matches_package() -> None:
    assert metadata.version("gitea-sandbox-adapter") == __version__


def test_version_output() -> None:
    result = run_cli("--version")

    assert result.returncode == 0
    assert result.stdout.strip() == f"gitea-sandbox {__version__}"
    assert result.stderr == ""


def test_run_cli_uses_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(kwargs)
        return subprocess.CompletedProcess(args[0], 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_cli("--version")

    assert result.returncode == 0
    assert calls[0]["timeout"] == CLI_TIMEOUT_SECONDS


def test_registered_commands_are_exact() -> None:
    assert COMMANDS == EXPECTED_COMMANDS


def test_top_level_help_lists_all_commands() -> None:
    result = run_cli("--help")

    assert result.returncode == 0
    assert "usage: gitea-sandbox" in result.stdout
    for command_name in EXPECTED_COMMANDS:
        assert command_name in result.stdout
    assert "not implemented in Phase 1" not in result.stdout
    assert result.stderr == ""


def test_validate_modes_are_mutually_exclusive() -> None:
    result = run_cli("validate", "--api-only", "--browser-only")

    assert result.returncode != 0
    assert "not allowed with argument" in result.stderr


def test_restore_requires_bundle_argument_before_runtime() -> None:
    result = run_cli("restore")

    assert result.returncode != 0
    assert "the following arguments are required: bundle" in result.stderr


def test_browser_only_validation_uses_default_runtime_screenshot_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(cli_module, "_config_and_docker", lambda: (object(), object()))

    def fake_validate_browser(
        config: object,
        *,
        save_screenshots: bool = True,
        screenshot_dir: object = None,
    ) -> dict[str, object]:
        del config
        captured["save_screenshots"] = save_screenshots
        captured["screenshot_dir"] = screenshot_dir
        return {"screenshots": [".gitea-sandbox/browser-evidence/run/x.png"]}

    monkeypatch.setattr(cli_module, "validate_browser", fake_validate_browser)

    assert cli_module.run(["validate", "--browser-only"]) == 0
    assert captured == {"save_screenshots": True, "screenshot_dir": None}


def test_complete_validation_uses_default_runtime_screenshot_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(cli_module, "_config_and_docker", lambda: (object(), object()))
    monkeypatch.setattr(cli_module, "validate_runtime", lambda *_args: {})
    monkeypatch.setattr(cli_module, "validate_postgres", lambda *_args: "postgres")
    monkeypatch.setattr(cli_module, "validate_api", lambda *_args: {})

    def fake_validate_browser(
        config: object,
        *,
        save_screenshots: bool = True,
        screenshot_dir: object = None,
    ) -> dict[str, object]:
        del config
        captured["save_screenshots"] = save_screenshots
        captured["screenshot_dir"] = screenshot_dir
        return {"screenshots": [".gitea-sandbox/browser-evidence/run/x.png"]}

    monkeypatch.setattr(cli_module, "validate_browser", fake_validate_browser)

    assert cli_module.run(["validate"]) == 0
    assert captured == {"save_screenshots": True, "screenshot_dir": None}


def test_validate_no_screenshots(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(cli_module, "_config_and_docker", lambda: (object(), object()))

    def fake_validate_browser(
        config: object,
        *,
        save_screenshots: bool = True,
        screenshot_dir: object = None,
    ) -> dict[str, object]:
        del config
        captured["save_screenshots"] = save_screenshots
        captured["screenshot_dir"] = screenshot_dir
        return {"screenshots": []}

    monkeypatch.setattr(cli_module, "validate_browser", fake_validate_browser)

    assert cli_module.run(["validate", "--browser-only", "--no-screenshots"]) == 0
    assert captured == {"save_screenshots": False, "screenshot_dir": None}


def test_validate_explicit_screenshot_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(cli_module, "_config_and_docker", lambda: (object(), object()))

    def fake_validate_browser(
        config: object,
        *,
        save_screenshots: bool = True,
        screenshot_dir: object = None,
    ) -> dict[str, object]:
        del config
        captured["save_screenshots"] = save_screenshots
        captured["screenshot_dir"] = screenshot_dir
        return {"screenshots": ["docs/evidence/manual/browser-repository.png"]}

    monkeypatch.setattr(cli_module, "validate_browser", fake_validate_browser)

    assert (
        cli_module.run(
            ["validate", "--browser-only", "--screenshot-dir", "docs/evidence/manual"]
        )
        == 0
    )
    assert captured == {
        "save_screenshots": True,
        "screenshot_dir": Path("docs/evidence/manual"),
    }
