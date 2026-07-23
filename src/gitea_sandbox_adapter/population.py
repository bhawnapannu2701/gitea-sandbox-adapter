"""Deterministic Gitea population through the REST API."""

from __future__ import annotations

import base64
import json
import os
from hashlib import sha256
from typing import Any, cast

from gitea_sandbox_adapter.api import ApiClient, quote_path
from gitea_sandbox_adapter.config import SandboxConfig
from gitea_sandbox_adapter.docker import DockerRunner
from gitea_sandbox_adapter.errors import ApiError, PopulationError
from gitea_sandbox_adapter.redaction import redact


def load_fixture(config: SandboxConfig) -> dict[str, Any]:
    try:
        data = json.loads(config.fixture_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PopulationError(f"Fixture manifest is malformed: {exc}") from exc
    if not isinstance(data, dict):
        raise PopulationError("Fixture manifest must be a JSON object.")
    if data.get("schema_version") != 1:
        raise PopulationError("Unsupported fixture manifest schema_version.")
    return cast(dict[str, Any], data)


def fixture_hash(config: SandboxConfig) -> str:
    return sha256(config.fixture_file.read_bytes()).hexdigest()


def ensure_admin(config: SandboxConfig, docker: DockerRunner) -> None:
    command = [
        "gitea",
        "admin",
        "user",
        "create",
        "--config",
        "/etc/gitea/app.ini",
        "--username",
        config.admin_user,
        "--password",
        config.admin_password,
        "--email",
        config.admin_email,
        "--admin",
        "--must-change-password=false",
    ]
    result = docker.exec("gitea", command, timeout=120)
    combined = f"{result.stdout}\n{result.stderr}"
    if result.returncode == 0:
        return
    if (
        "already exists" in combined.lower()
        or "user already exists" in combined.lower()
    ):
        return
    raise PopulationError(redact(f"Failed to bootstrap Gitea admin:\n{combined}"))


def _token_file_payload(config: SandboxConfig) -> dict[str, Any] | None:
    if not config.token_file.exists():
        return None
    try:
        data = json.loads(config.token_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("base_url") != config.api_base_url:
        return None
    if data.get("admin_user") != config.admin_user:
        return None
    token = data.get("token")
    if not isinstance(token, str) or not token:
        return None
    return cast(dict[str, Any], data)


def _write_token(config: SandboxConfig, token: str) -> None:
    config.runtime_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "base_url": config.api_base_url,
        "admin_user": config.admin_user,
        "token_name": config.token_name,
        "token": token,
    }
    config.token_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    try:
        os.chmod(config.token_file, 0o600)
    except OSError:
        pass


def _stored_token_is_valid(config: SandboxConfig, token: str) -> bool:
    client = ApiClient(
        config.api_base_url,
        token=token,
        timeout=config.http_timeout,
        retries=1,
    )
    try:
        user = client.get("user")
    except ApiError:
        return False
    return isinstance(user, dict) and user.get("login") == config.admin_user


def ensure_token(config: SandboxConfig, docker: DockerRunner) -> str:
    stored = _token_file_payload(config)
    if stored is not None:
        token = str(stored["token"])
        if _stored_token_is_valid(config, token):
            return token

    basic = ApiClient(
        config.api_base_url,
        basic_auth=(config.admin_user, config.admin_password),
        timeout=config.http_timeout,
        retries=config.http_retries,
    )
    try:
        basic.delete(
            f"users/{quote_path(config.admin_user)}/tokens/{quote_path(config.token_name)}",
            expected=(204, 404),
        )
        created = basic.post(
            f"users/{quote_path(config.admin_user)}/tokens",
            {"name": config.token_name, "scopes": ["all"]},
            expected=(200, 201),
        )
        created_token = created.get("sha1") if isinstance(created, dict) else None
        if isinstance(created_token, str) and created_token:
            _write_token(config, created_token)
            return created_token
    except ApiError:
        pass

    result = docker.exec(
        "gitea",
        [
            "gitea",
            "admin",
            "user",
            "generate-access-token",
            "--config",
            "/etc/gitea/app.ini",
            "--username",
            config.admin_user,
            "--token-name",
            config.token_name,
            "--scopes",
            "all",
            "--raw",
        ],
        timeout=120,
    )
    if result.returncode != 0:
        raise PopulationError(redact(f"Failed to generate API token:\n{result.stderr}"))
    token = result.stdout.strip().splitlines()[-1].strip()
    if not token:
        raise PopulationError("Gitea token generation returned an empty token.")
    _write_token(config, token)
    return token


def authenticated_client(config: SandboxConfig, docker: DockerRunner) -> ApiClient:
    ensure_admin(config, docker)
    token = ensure_token(config, docker)
    return ApiClient(
        config.api_base_url,
        token=token,
        timeout=config.http_timeout,
        retries=config.http_retries,
    )


def populate(config: SandboxConfig, docker: DockerRunner) -> dict[str, Any]:
    fixture = load_fixture(config)
    client = authenticated_client(config, docker)
    org = _ensure_org(client, fixture)
    repo = _ensure_repo(client, fixture)
    team = _ensure_team(client, fixture, repo)
    files = _ensure_files(client, fixture)
    labels = _ensure_labels(client, fixture)
    milestone = _ensure_milestone(client, fixture)
    issue = _ensure_issue(client, fixture, labels, milestone)
    release = _ensure_release(client, fixture)
    return {
        "organization": org.get("username") or org.get("name"),
        "repository": repo.get("full_name"),
        "team": team.get("name"),
        "files": files,
        "labels": sorted(labels),
        "milestone": milestone.get("title"),
        "issue": issue.get("title"),
        "release": release.get("tag_name"),
    }


def _get_or_none(client: ApiClient, path: str) -> Any:
    try:
        return client.get(path)
    except ApiError as exc:
        if "HTTP 404" in str(exc):
            return None
        raise


def _ensure_org(client: ApiClient, fixture: dict[str, Any]) -> dict[str, Any]:
    spec = fixture["organization"]
    org_name = spec["name"]
    existing = _get_or_none(client, f"orgs/{quote_path(org_name)}")
    body = {
        "username": org_name,
        "full_name": spec["full_name"],
        "description": spec["description"],
        "visibility": spec["visibility"],
    }
    if existing is None:
        created = client.post("orgs", body, expected=(201,))
        if not isinstance(created, dict):
            raise PopulationError("Organization create response was not an object.")
        return created
    patch_body = {
        "full_name": spec["full_name"],
        "description": spec["description"],
        "visibility": spec["visibility"],
    }
    updated = client.patch(f"orgs/{quote_path(org_name)}", patch_body)
    return updated if isinstance(updated, dict) else existing


def _ensure_repo(client: ApiClient, fixture: dict[str, Any]) -> dict[str, Any]:
    org_name = fixture["organization"]["name"]
    spec = fixture["repository"]
    repo_name = spec["name"]
    path = f"repos/{quote_path(org_name)}/{quote_path(repo_name)}"
    existing = _get_or_none(client, path)
    if existing is None:
        created = client.post(
            f"orgs/{quote_path(org_name)}/repos",
            {
                "name": repo_name,
                "description": spec["description"],
                "private": spec["private"],
                "auto_init": True,
                "default_branch": spec["default_branch"],
            },
            expected=(201,),
        )
        if not isinstance(created, dict):
            raise PopulationError("Repository create response was not an object.")
        return created
    updated = client.patch(
        path,
        {
            "description": spec["description"],
            "private": spec["private"],
            "default_branch": spec["default_branch"],
        },
    )
    return updated if isinstance(updated, dict) else existing


def _ensure_team(
    client: ApiClient,
    fixture: dict[str, Any],
    repo: dict[str, Any],
) -> dict[str, Any]:
    org_name = fixture["organization"]["name"]
    spec = fixture["team"]
    teams = client.list_paginated(f"orgs/{quote_path(org_name)}/teams")
    existing = next((team for team in teams if team.get("name") == spec["name"]), None)
    body = {
        "name": spec["name"],
        "description": spec["description"],
        "permission": spec["permission"],
        "units": spec["units"],
        "can_create_org_repo": True,
        "includes_all_repositories": False,
    }
    if existing is None:
        team = client.post(f"orgs/{quote_path(org_name)}/teams", body, expected=(201,))
    else:
        team = client.patch(f"teams/{existing['id']}", body)
    if not isinstance(team, dict):
        raise PopulationError("Team response was not an object.")
    repo_name = repo["name"]
    client.put(
        f"teams/{team['id']}/repos/{quote_path(org_name)}/{quote_path(repo_name)}",
        {},
        expected=(204,),
    )
    return team


def _ensure_files(client: ApiClient, fixture: dict[str, Any]) -> list[dict[str, str]]:
    org_name = fixture["organization"]["name"]
    repo = fixture["repository"]
    repo_name = repo["name"]
    branch = repo["default_branch"]
    results: list[dict[str, str]] = []
    for file_spec in fixture["files"]:
        encoded_path = quote_path(file_spec["path"])
        repo_path = f"repos/{quote_path(org_name)}/{quote_path(repo_name)}"
        path = f"{repo_path}/contents/{encoded_path}"
        existing = _get_or_none(client, f"{path}?ref={quote_path(branch)}")
        body: dict[str, Any] = {
            "branch": branch,
            "message": file_spec["message"],
            "content": base64.b64encode(file_spec["content"].encode("utf-8")).decode(
                "ascii"
            ),
        }
        if isinstance(existing, dict) and existing.get("sha"):
            current = _decode_content(existing)
            if current == file_spec["content"]:
                results.append(
                    {
                        "path": file_spec["path"],
                        "sha256": sha256(current.encode("utf-8")).hexdigest(),
                    }
                )
                continue
            body["sha"] = existing["sha"]
        client.put(path, body, expected=(200, 201))
        results.append(
            {
                "path": file_spec["path"],
                "sha256": sha256(file_spec["content"].encode("utf-8")).hexdigest(),
            }
        )
    return results


def _decode_content(content_response: dict[str, Any]) -> str:
    raw = str(content_response.get("content", "")).replace("\n", "")
    return base64.b64decode(raw.encode("ascii")).decode("utf-8")


def _ensure_labels(client: ApiClient, fixture: dict[str, Any]) -> dict[str, int]:
    org_name = fixture["organization"]["name"]
    repo_name = fixture["repository"]["name"]
    base = f"repos/{quote_path(org_name)}/{quote_path(repo_name)}"
    existing = client.list_paginated(f"{base}/labels")
    by_name = {label["name"]: label for label in existing if isinstance(label, dict)}
    labels: dict[str, int] = {}
    for spec in fixture["labels"]:
        body = {
            "name": spec["name"],
            "color": spec["color"],
            "description": spec["description"],
        }
        current = by_name.get(spec["name"])
        if current is None:
            label = client.post(f"{base}/labels", body, expected=(201,))
        else:
            label = client.patch(f"{base}/labels/{current['id']}", body)
        if not isinstance(label, dict):
            raise PopulationError("Label response was not an object.")
        labels[spec["name"]] = int(label["id"])
    return labels


def _ensure_milestone(client: ApiClient, fixture: dict[str, Any]) -> dict[str, Any]:
    org_name = fixture["organization"]["name"]
    repo_name = fixture["repository"]["name"]
    base = f"repos/{quote_path(org_name)}/{quote_path(repo_name)}"
    spec = fixture["milestone"]
    milestones = client.list_paginated(f"{base}/milestones?state=all")
    existing = next(
        (item for item in milestones if item.get("title") == spec["title"]), None
    )
    body = {
        "title": spec["title"],
        "description": spec["description"],
        "state": spec["state"],
    }
    if existing is None:
        milestone = client.post(f"{base}/milestones", body, expected=(201,))
    else:
        milestone = client.patch(f"{base}/milestones/{existing['id']}", body)
    if not isinstance(milestone, dict):
        raise PopulationError("Milestone response was not an object.")
    return milestone


def _ensure_issue(
    client: ApiClient,
    fixture: dict[str, Any],
    labels: dict[str, int],
    milestone: dict[str, Any],
) -> dict[str, Any]:
    org_name = fixture["organization"]["name"]
    repo_name = fixture["repository"]["name"]
    base = f"repos/{quote_path(org_name)}/{quote_path(repo_name)}"
    spec = fixture["issue"]
    issues = client.list_paginated(f"{base}/issues?state=all")
    existing = next(
        (item for item in issues if item.get("title") == spec["title"]), None
    )
    label_ids = [labels[label_spec["name"]] for label_spec in fixture["labels"]]
    body = {
        "title": spec["title"],
        "body": spec["body"],
        "state": spec["state"],
        "labels": label_ids,
        "milestone": milestone["id"],
    }
    if existing is None:
        issue = client.post(f"{base}/issues", body, expected=(201,))
    else:
        issue = client.patch(
            f"{base}/issues/{existing['number']}",
            body,
            expected=(200, 201),
        )
    if not isinstance(issue, dict):
        raise PopulationError("Issue response was not an object.")
    return issue


def _ensure_release(client: ApiClient, fixture: dict[str, Any]) -> dict[str, Any]:
    org_name = fixture["organization"]["name"]
    repo_name = fixture["repository"]["name"]
    base = f"repos/{quote_path(org_name)}/{quote_path(repo_name)}"
    spec = fixture["release"]
    existing = _get_or_none(
        client, f"{base}/releases/tags/{quote_path(spec['tag_name'])}"
    )
    body = {
        "tag_name": spec["tag_name"],
        "target_commitish": spec["target_commitish"],
        "name": spec["name"],
        "body": spec["body"],
        "draft": spec["draft"],
        "prerelease": spec["prerelease"],
    }
    if existing is None:
        release = client.post(f"{base}/releases", body, expected=(201,))
    else:
        release = client.patch(f"{base}/releases/{existing['id']}", body)
    if not isinstance(release, dict):
        raise PopulationError("Release response was not an object.")
    return release
