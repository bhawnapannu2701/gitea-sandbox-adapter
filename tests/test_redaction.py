from __future__ import annotations

from gitea_sandbox_adapter.redaction import redact, redact_args, redact_mapping


def test_redacts_authorization_and_passwords() -> None:
    text = "Authorization: token abcdef1234567890\npassword=super-secret"

    safe = redact(text)

    assert "abcdef" not in safe
    assert "super-secret" not in safe
    assert "<redacted>" in safe


def test_redacts_command_args_after_password_flag() -> None:
    args = ["gitea", "--username", "admin", "--password", "secret-value"]

    assert redact_args(args)[-1] == "<redacted>"


def test_redacts_secret_mapping_values() -> None:
    result = redact_mapping({"POSTGRES_PASSWORD": "secret", "GITEA_HTTP_PORT": "3000"})

    assert result["POSTGRES_PASSWORD"] == "<redacted>"
    assert result["GITEA_HTTP_PORT"] == "3000"
