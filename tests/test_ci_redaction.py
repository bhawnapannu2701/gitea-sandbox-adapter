from __future__ import annotations

from pathlib import Path

from gitea_sandbox_adapter.ci_redaction import redact_ci_log, redact_ci_log_file


def test_ci_log_redactor_removes_synthetic_secret_values(tmp_path: Path) -> None:
    secrets = [
        "postgres-password-value-1234567890",
        "admin-token-value-1234567890",
        "authorization-token-value-1234567890",
        "bearer-token-value-1234567890",
        "url-password-value-1234567890",
        "database-password-value-1234567890",
        "auth-key-value-1234567890",
    ]
    raw = "\n".join(
        [
            f"POSTGRES_PASSWORD={secrets[0]}",
            f"GITEA_TOKEN_NAME={secrets[1]}",
            f"Authorization: token {secrets[2]}",
            f"Bearer {secrets[3]}",
            f"https://user:{secrets[4]}@example.invalid/repo",
            f"postgres://gitea:{secrets[5]}@postgres:5432/gitea",
            f"API_AUTH_KEY: {secrets[6]}",
        ]
    )

    redacted = redact_ci_log(raw)

    for value in secrets:
        assert value not in redacted
    assert redacted.count("<redacted>") >= len(secrets)


def test_ci_log_redactor_writes_separate_redacted_file(tmp_path: Path) -> None:
    raw = tmp_path / "compose.raw.log"
    redacted = tmp_path / "compose.redacted.log"
    raw.write_text("Authorization: bearer synthetic-token-1234567890", encoding="utf-8")

    redact_ci_log_file(raw, redacted)

    output = redacted.read_text(encoding="utf-8")
    assert "synthetic-token-1234567890" not in output
    assert "<redacted>" in output
    assert raw.exists()
