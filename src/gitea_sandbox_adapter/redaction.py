"""Centralized redaction helpers for logs, errors, and diagnostics."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

SECRET_NAME_PARTS = (
    "PASSWORD",
    "PASSWD",
    "TOKEN",
    "SECRET",
    "KEY",
    "AUTH",
)

_REDACTED = "<redacted>"

_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(authorization:\s*)(bearer|token|basic)\s+[^\s]+"),
    re.compile(r"(?i)(\bbearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(
        r"(?i)((?:[A-Z0-9_]*"
        r"(?:PASSWORD|PASSWD|TOKEN|SECRET|KEY|AUTH)"
        r"[A-Z0-9_]*|password|passwd|token|secret|key|auth)"
        r"\s*[:=]\s*)[^\s,;]+"
    ),
    re.compile(r"(?i)(--(?:password|token|secret|key)\s+)[^\s]+"),
    re.compile(r"(?i)(//[^:/\s]+:)[^@\s]+(@)"),
    re.compile(r"(?i)(postgres(?:ql)?://[^:/\s]+:)[^@\s]+(@)"),
)


def is_secret_name(name: str) -> bool:
    upper_name = name.upper()
    return any(part in upper_name for part in SECRET_NAME_PARTS)


def redact(text: object) -> str:
    value = str(text)
    for pattern in _PATTERNS:
        value = pattern.sub(lambda match: f"{match.group(1)}{_REDACTED}", value)
    return value


def redact_args(args: list[str] | tuple[str, ...]) -> list[str]:
    redacted: list[str] = []
    hide_next = False
    for arg in args:
        if hide_next:
            redacted.append(_REDACTED)
            hide_next = False
            continue
        redacted.append(redact(arg))
        lower = arg.lower()
        if lower in {"--password", "--token", "--secret", "--key"}:
            hide_next = True
    return redacted


def redact_mapping(values: Mapping[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in values.items():
        if is_secret_name(key):
            safe[key] = _REDACTED if value not in (None, "") else value
        elif isinstance(value, Mapping):
            safe[key] = redact_mapping(value)
        elif isinstance(value, list):
            safe[key] = [
                redact_mapping(item)
                if isinstance(item, Mapping)
                else redact(item)
                if isinstance(item, str)
                else item
                for item in value
            ]
        elif isinstance(value, str):
            safe[key] = redact(value)
        else:
            safe[key] = value
    return safe
