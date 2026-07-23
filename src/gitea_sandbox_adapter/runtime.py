"""Bounded subprocess execution helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path

from gitea_sandbox_adapter.errors import CommandError
from gitea_sandbox_adapter.models import CommandResult
from gitea_sandbox_adapter.redaction import redact, redact_args


def run_command(
    args: list[str],
    *,
    cwd: Path,
    timeout: int,
    input_bytes: bytes | None = None,
    stdout_path: Path | None = None,
    check: bool = False,
) -> CommandResult:
    if not args:
        raise ValueError("args must not be empty")

    try:
        if stdout_path is None:
            completed = subprocess.run(
                args,
                cwd=cwd,
                input=input_bytes,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
            stdout_text = completed.stdout.decode("utf-8", errors="replace")
        else:
            stdout_path.parent.mkdir(parents=True, exist_ok=True)
            with stdout_path.open("wb") as stdout_file:
                completed = subprocess.run(
                    args,
                    cwd=cwd,
                    input=input_bytes,
                    stdout=stdout_file,
                    stderr=subprocess.PIPE,
                    timeout=timeout,
                    check=False,
                )
            stdout_text = ""
        stderr_text = completed.stderr.decode("utf-8", errors="replace")
    except FileNotFoundError as exc:
        safe_args = " ".join(redact_args(args))
        raise CommandError(f"Command not found: {safe_args}") from exc
    except subprocess.TimeoutExpired as exc:
        safe_args = " ".join(redact_args(args))
        raise CommandError(f"Command timed out after {timeout}s: {safe_args}") from exc

    result = CommandResult(
        args=tuple(args),
        returncode=completed.returncode,
        stdout=stdout_text,
        stderr=stderr_text,
    )
    if check and result.returncode != 0:
        safe_args = " ".join(redact_args(args))
        output = redact(f"{result.stdout}\n{result.stderr}".strip())
        raise CommandError(
            f"Command failed ({result.returncode}): {safe_args}\n{output}"
        )
    return result
