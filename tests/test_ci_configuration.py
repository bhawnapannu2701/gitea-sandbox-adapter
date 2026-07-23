from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def test_pytest_uses_default_temp_directory_behavior() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    addopts = config["tool"]["pytest"]["ini_options"]["addopts"]
    joined = "\n".join(addopts)

    assert not any(option.startswith("--basetemp") for option in addopts)
    assert ".gitea-sandbox/pytest-tmp" not in joined


def test_ci_workflow_installs_playwright_chromium_before_restore() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    dependencies = workflow.index("- name: Install dev dependencies")
    browser_install = workflow.index("- name: Install Playwright Chromium")
    restore = workflow.index("- name: Restore snapshot")

    assert dependencies < browser_install < restore
    assert "python -m playwright install --with-deps chromium" in workflow

    restore_step = workflow.split("- name: Restore snapshot", 1)[1].split(
        "- name: Integration pytest", 1
    )[0]
    assert "gitea-sandbox restore" in restore_step
    assert "--api-only" not in restore_step
    assert "--browser-only" not in restore_step


def test_ci_workflow_runs_on_pull_requests_and_main_pushes_only() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    trigger_block = workflow.split("permissions:", 1)[0]

    assert "pull_request:" in trigger_block
    assert "push:" in trigger_block
    assert "- main" in trigger_block
    assert "feat/" not in trigger_block
    assert "concurrency:" in workflow
    assert "cancel-in-progress: true" in workflow


def test_ci_artifact_upload_paths_exclude_sensitive_runtime_files() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    upload_step = workflow.split("- name: Upload sanitized diagnostics", 1)[1].split(
        "- name: Stop sandbox", 1
    )[0]

    assert "diagnostics/diagnose.json" in upload_step
    assert "diagnostics/compose.redacted.log" in upload_step
    assert "diagnostics/compose.raw.log" not in upload_step

    exclusions = [
        "!diagnostics/*.raw.log",
        "!.env",
        "!.gitea-sandbox/**",
        "!snapshots/**",
        "!**/*.dump",
        "!**/*.tar.gz",
        "!**/*token*",
        "!**/*cookie*",
        "!**/storage-state*.json",
    ]
    for exclusion in exclusions:
        assert exclusion in upload_step
