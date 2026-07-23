"""CI diagnostic log redaction helpers."""

from __future__ import annotations

from pathlib import Path

from gitea_sandbox_adapter.redaction import redact


def redact_ci_log(text: str) -> str:
    """Return CI log text with likely credential material masked."""
    return redact(text)


def redact_ci_log_file(input_path: Path, output_path: Path) -> None:
    raw = input_path.read_text(encoding="utf-8", errors="replace")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(redact_ci_log(raw), encoding="utf-8")
