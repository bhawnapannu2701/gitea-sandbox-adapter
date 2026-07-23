from __future__ import annotations

from pathlib import Path

import pytest

from gitea_sandbox_adapter.config import (
    PINNED_GITEA_IMAGE,
    PINNED_POSTGRES_IMAGE,
    load_config,
    parse_env_file,
)
from gitea_sandbox_adapter.errors import ConfigError


def write_project(tmp_path: Path, env_text: str) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (tmp_path / ".env").write_text(env_text, encoding="utf-8")
    return tmp_path


def complete_env(**overrides: str) -> str:
    values = {
        "COMPOSE_PROJECT_NAME": "gitea_sandbox_adapter",
        "GITEA_IMAGE": PINNED_GITEA_IMAGE,
        "POSTGRES_IMAGE": PINNED_POSTGRES_IMAGE,
        "GITEA_HTTP_PORT": "3000",
        "GITEA_SSH_PORT": "2222",
        "POSTGRES_DB": "gitea",
        "POSTGRES_USER": "gitea",
        "POSTGRES_PASSWORD": "local-postgres-password",
        "GITEA_ADMIN_USER": "sandbox-admin",
        "GITEA_ADMIN_PASSWORD": "local-admin-password",
        "GITEA_ADMIN_EMAIL": "sandbox-admin@example.invalid",
        "GITEA_TOKEN_NAME": "gitea-sandbox-phase-2",
    }
    values.update(overrides)
    return "".join(f"{key}={value}\n" for key, value in values.items())


def test_parse_env_file_handles_quotes_and_comments(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("A=one\n# comment\nB=\"two words\"\n", encoding="utf-8")

    assert parse_env_file(env_file) == {"A": "one", "B": "two words"}


def test_load_config_requires_missing_secret(tmp_path: Path) -> None:
    root = write_project(tmp_path, complete_env(POSTGRES_PASSWORD=""))

    with pytest.raises(ConfigError, match="POSTGRES_PASSWORD"):
        load_config(repo_root=root, environ={}, require_env=True)


def test_load_config_rejects_unpinned_images(tmp_path: Path) -> None:
    root = write_project(tmp_path, complete_env(GITEA_IMAGE="gitea/gitea:latest"))

    with pytest.raises(ConfigError, match="GITEA_IMAGE must be pinned"):
        load_config(repo_root=root, environ={}, require_env=True)


def test_load_config_builds_urls(tmp_path: Path) -> None:
    root = write_project(tmp_path, complete_env(GITEA_HTTP_PORT="3100"))

    config = load_config(repo_root=root, environ={}, require_env=True)

    assert config.root_url == "http://localhost:3100/"
    assert config.api_base_url == "http://localhost:3100/api/v1"
