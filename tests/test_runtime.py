from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from gitea_sandbox_adapter.errors import CommandError
from gitea_sandbox_adapter.runtime import run_command


def test_run_command_uses_argument_list_without_shell(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        calls.append({"args": args, "kwargs": kwargs})
        return subprocess.CompletedProcess(args[0], 0, b"ok", b"")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_command(["tool", "arg"], cwd=tmp_path, timeout=5)

    assert result.stdout == "ok"
    assert calls[0]["args"][0] == ["tool", "arg"]
    assert "shell" not in calls[0]["kwargs"]
    assert calls[0]["kwargs"]["cwd"] == tmp_path
    assert calls[0]["kwargs"]["timeout"] == 5


def test_run_command_redacts_failed_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(args[0], 1, b"", b"password=secret-value")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(CommandError) as exc_info:
        run_command(["tool"], cwd=tmp_path, timeout=5, check=True)

    assert "secret-value" not in str(exc_info.value)
    assert "<redacted>" in str(exc_info.value)
