"""API and PostgreSQL validation for the deterministic fixture."""

from __future__ import annotations

from hashlib import sha256
from typing import Any, cast

from gitea_sandbox_adapter.api import ApiClient, quote_path
from gitea_sandbox_adapter.config import SandboxConfig
from gitea_sandbox_adapter.docker import DockerRunner
from gitea_sandbox_adapter.errors import ValidationError
from gitea_sandbox_adapter.population import authenticated_client, load_fixture


def validate_runtime(config: SandboxConfig, docker: DockerRunner) -> dict[str, Any]:
    statuses = docker.all_statuses()
    failures = [status for status in statuses if not status.is_healthy]
    if failures:
        summary = ", ".join(
            f"{status.service} state={status.state} health={status.health}"
            for status in failures
        )
        raise ValidationError(f"Required services are not healthy: {summary}")
    return {
        status.service: {"state": status.state, "health": status.health}
        for status in statuses
    }


def validate_postgres(config: SandboxConfig, docker: DockerRunner) -> str:
    result = docker.exec(
        "postgres",
        [
            "psql",
            "-U",
            config.postgres_user,
            "-d",
            config.postgres_db,
            "-tAc",
            "SELECT version();",
        ],
        timeout=60,
    )
    if result.returncode != 0:
        raise ValidationError(f"PostgreSQL validation query failed: {result.stderr}")
    version = result.stdout.strip()
    if not version:
        raise ValidationError("PostgreSQL version query returned no output.")
    return version


def validate_api(config: SandboxConfig, docker: DockerRunner) -> dict[str, Any]:
    client = authenticated_client(config, docker)
    return validate_api_with_client(config, client)


def validate_api_with_client(
    config: SandboxConfig,
    client: ApiClient,
) -> dict[str, Any]:
    fixture = load_fixture(config)
    health = _health(config)
    user = client.get("user")
    if not isinstance(user, dict) or user.get("login") != config.admin_user:
        raise ValidationError("Authenticated API user did not match configured admin.")

    org = _expect_object(
        client.get(f"orgs/{quote_path(fixture['organization']['name'])}")
    )
    repo = _expect_object(
        client.get(
            "repos/"
            f"{quote_path(fixture['organization']['name'])}/"
            f"{quote_path(fixture['repository']['name'])}"
        )
    )
    if repo.get("default_branch") != fixture["repository"]["default_branch"]:
        raise ValidationError("Repository default branch mismatch.")

    team = _validate_team(client, fixture)
    files = _validate_files(client, fixture)
    labels = _validate_labels(client, fixture)
    milestone = _validate_milestone(client, fixture)
    issue = _validate_issue(client, fixture, labels, milestone)
    release = _validate_release(client, fixture)
    duplicates = _validate_no_duplicates(client, fixture)
    version = client.get("version")

    return {
        "health": health,
        "api_version": version,
        "user": user.get("login"),
        "organization": org.get("username") or org.get("name"),
        "repository": repo.get("full_name"),
        "team": team.get("name"),
        "files": files,
        "labels": sorted(labels),
        "milestone": milestone.get("title"),
        "issue": issue.get("title"),
        "release": release.get("tag_name"),
        "duplicates": duplicates,
    }


def _health(config: SandboxConfig) -> dict[str, Any]:
    client = ApiClient(
        config.root_url.rstrip("/"),
        timeout=config.http_timeout,
        retries=config.http_retries,
    )
    response = client.get("api/healthz")
    if not isinstance(response, dict):
        raise ValidationError("Health endpoint did not return a JSON object.")
    return response


def _expect_object(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError("Expected API response object.")
    return value


def _validate_files(client: ApiClient, fixture: dict[str, Any]) -> list[dict[str, str]]:
    org = fixture["organization"]["name"]
    repo = fixture["repository"]["name"]
    branch = fixture["repository"]["default_branch"]
    results: list[dict[str, str]] = []
    for spec in fixture["files"]:
        path = (
            f"repos/{quote_path(org)}/{quote_path(repo)}/contents/"
            f"{quote_path(spec['path'])}?ref={quote_path(branch)}"
        )
        item = _expect_object(client.get(path))
        raw = str(item.get("content", "")).replace("\n", "")
        import base64

        content = base64.b64decode(raw.encode("ascii")).decode("utf-8")
        if content != spec["content"]:
            raise ValidationError(f"Repository file content mismatch: {spec['path']}")
        results.append(
            {
                "path": spec["path"],
                "sha256": sha256(content.encode("utf-8")).hexdigest(),
            }
        )
    return results


def _validate_team(client: ApiClient, fixture: dict[str, Any]) -> dict[str, Any]:
    org = fixture["organization"]["name"]
    spec = fixture["team"]
    teams = client.list_paginated(f"orgs/{quote_path(org)}/teams")
    matches = [item for item in teams if item.get("name") == spec["name"]]
    if len(matches) != 1:
        raise ValidationError("Expected exactly one deterministic team.")
    team = matches[0]
    if not isinstance(team, dict):
        raise ValidationError("Team response was not an object.")
    if team.get("description") != spec["description"]:
        raise ValidationError("Team description mismatch.")
    if team.get("can_create_org_repo") is not True:
        raise ValidationError("Team create-repository flag mismatch.")
    if set(team.get("units", [])) != set(spec["units"]):
        raise ValidationError("Team units mismatch.")
    return cast(dict[str, Any], team)


def _validate_labels(
    client: ApiClient, fixture: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    org = fixture["organization"]["name"]
    repo = fixture["repository"]["name"]
    labels = client.list_paginated(f"repos/{quote_path(org)}/{quote_path(repo)}/labels")
    by_name = {label["name"]: label for label in labels if isinstance(label, dict)}
    for spec in fixture["labels"]:
        label = by_name.get(spec["name"])
        if label is None:
            raise ValidationError(f"Missing label: {spec['name']}")
        if label.get("color", "").lower().lstrip("#") != spec["color"]:
            raise ValidationError(f"Label color mismatch: {spec['name']}")
    return by_name


def _validate_milestone(client: ApiClient, fixture: dict[str, Any]) -> dict[str, Any]:
    org = fixture["organization"]["name"]
    repo = fixture["repository"]["name"]
    spec = fixture["milestone"]
    milestones = client.list_paginated(
        f"repos/{quote_path(org)}/{quote_path(repo)}/milestones?state=all"
    )
    matches = [item for item in milestones if item.get("title") == spec["title"]]
    if len(matches) != 1:
        raise ValidationError("Expected exactly one deterministic milestone.")
    milestone = matches[0]
    if not isinstance(milestone, dict):
        raise ValidationError("Milestone response was not an object.")
    if milestone.get("state") != spec["state"]:
        raise ValidationError("Milestone state mismatch.")
    return cast(dict[str, Any], milestone)


def _validate_issue(
    client: ApiClient,
    fixture: dict[str, Any],
    labels: dict[str, dict[str, Any]],
    milestone: dict[str, Any],
) -> dict[str, Any]:
    org = fixture["organization"]["name"]
    repo = fixture["repository"]["name"]
    spec = fixture["issue"]
    issues = client.list_paginated(
        f"repos/{quote_path(org)}/{quote_path(repo)}/issues?state=all"
    )
    matches = [item for item in issues if item.get("title") == spec["title"]]
    if len(matches) != 1:
        raise ValidationError("Expected exactly one deterministic issue.")
    issue = _expect_object(
        client.get(
            f"repos/{quote_path(org)}/{quote_path(repo)}/issues/{matches[0]['number']}"
        )
    )
    if issue.get("body") != spec["body"] or issue.get("state") != spec["state"]:
        raise ValidationError("Issue body or state mismatch.")
    if issue.get("milestone", {}).get("id") != milestone.get("id"):
        raise ValidationError("Issue milestone mismatch.")
    expected_labels = {label_spec["name"] for label_spec in fixture["labels"]}
    actual_labels = {label.get("name") for label in issue.get("labels", [])}
    if expected_labels - actual_labels:
        raise ValidationError("Issue labels mismatch.")
    return issue


def _validate_release(client: ApiClient, fixture: dict[str, Any]) -> dict[str, Any]:
    org = fixture["organization"]["name"]
    repo = fixture["repository"]["name"]
    spec = fixture["release"]
    release = _expect_object(
        client.get(
            f"repos/{quote_path(org)}/{quote_path(repo)}/releases/tags/"
            f"{quote_path(spec['tag_name'])}"
        )
    )
    for key in ("tag_name", "name", "body", "draft", "prerelease"):
        if release.get(key) != spec[key]:
            raise ValidationError(f"Release {key} mismatch.")
    return release


def _validate_no_duplicates(
    client: ApiClient, fixture: dict[str, Any]
) -> dict[str, int]:
    org = fixture["organization"]["name"]
    repo = fixture["repository"]["name"]
    labels = client.list_paginated(f"repos/{quote_path(org)}/{quote_path(repo)}/labels")
    milestones = client.list_paginated(
        f"repos/{quote_path(org)}/{quote_path(repo)}/milestones?state=all"
    )
    issues = client.list_paginated(
        f"repos/{quote_path(org)}/{quote_path(repo)}/issues?state=all"
    )
    releases = client.list_paginated(
        f"repos/{quote_path(org)}/{quote_path(repo)}/releases"
    )
    teams = client.list_paginated(f"orgs/{quote_path(org)}/teams")
    counts = {
        "teams": sum(
            1 for item in teams if item.get("name") == fixture["team"]["name"]
        ),
        "labels": sum(
            1
            for label in labels
            if label.get("name") in {spec["name"] for spec in fixture["labels"]}
        ),
        "milestones": sum(
            1
            for item in milestones
            if item.get("title") == fixture["milestone"]["title"]
        ),
        "issues": sum(
            1 for item in issues if item.get("title") == fixture["issue"]["title"]
        ),
        "releases": sum(
            1
            for item in releases
            if item.get("tag_name") == fixture["release"]["tag_name"]
        ),
    }
    expected_label_count = len(fixture["labels"])
    if counts["teams"] != 1:
        raise ValidationError("Duplicate or missing deterministic team detected.")
    if counts["labels"] != expected_label_count:
        raise ValidationError("Duplicate or missing deterministic labels detected.")
    for name in ("milestones", "issues", "releases"):
        if counts[name] != 1:
            raise ValidationError(
                f"Duplicate or missing deterministic {name} detected."
            )
    return counts
