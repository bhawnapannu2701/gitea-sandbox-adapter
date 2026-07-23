from __future__ import annotations

import subprocess
import sys

import pytest

import gitea_sandbox_adapter
from gitea_sandbox_adapter import __version__
from gitea_sandbox_adapter.cli import COMMANDS

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

FALSE_SUCCESS_TERMS = (
    "success",
    "succeeded",
    "successful",
    "complete",
    "completed",
)


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "gitea_sandbox_adapter", *args],
        capture_output=True,
        check=False,
        text=True,
    )


def test_package_import() -> None:
    assert gitea_sandbox_adapter.__version__ == __version__


def test_version_output() -> None:
    result = run_cli("--version")

    assert result.returncode == 0
    assert result.stdout.strip() == f"gitea-sandbox {__version__}"
    assert result.stderr == ""


def test_registered_commands_are_exact() -> None:
    assert COMMANDS == EXPECTED_COMMANDS
    assert len(COMMANDS) == 9


def test_top_level_help_lists_all_commands() -> None:
    result = run_cli("--help")

    assert result.returncode == 0
    assert "usage: gitea-sandbox" in result.stdout
    for command_name in EXPECTED_COMMANDS:
        assert command_name in result.stdout
    assert result.stderr == ""


@pytest.mark.parametrize("command_name", EXPECTED_COMMANDS)
def test_command_help(command_name: str) -> None:
    result = run_cli(command_name, "--help")

    assert result.returncode == 0
    assert f"usage: gitea-sandbox {command_name}" in result.stdout
    assert "not implemented in Phase 1" in result.stdout
    assert result.stderr == ""


@pytest.mark.parametrize("command_name", EXPECTED_COMMANDS)
def test_unimplemented_commands_exit_non_zero(command_name: str) -> None:
    result = run_cli(command_name)

    assert result.returncode != 0
    assert (
        result.stdout.strip()
        == f"Command '{command_name}' is not implemented in Phase 1."
    )
    assert result.stderr == ""


@pytest.mark.parametrize("command_name", EXPECTED_COMMANDS)
def test_unimplemented_commands_do_not_claim_success(command_name: str) -> None:
    result = run_cli(command_name)
    output = f"{result.stdout}\n{result.stderr}".lower()

    for false_success_term in FALSE_SUCCESS_TERMS:
        assert false_success_term not in output
