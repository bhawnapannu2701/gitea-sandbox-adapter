"""Real isolated browser validation using Playwright."""

from __future__ import annotations

import importlib
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from gitea_sandbox_adapter.config import SandboxConfig
from gitea_sandbox_adapter.errors import ValidationError
from gitea_sandbox_adapter.population import load_fixture

SCREENSHOT_NAMES = ("browser-repository.png", "browser-release.png")


def validate_browser(
    config: SandboxConfig,
    *,
    save_screenshots: bool = True,
    screenshot_dir: Path | None = None,
) -> dict[str, Any]:
    try:
        sync_api = importlib.import_module("playwright.sync_api")
    except ImportError as exc:
        raise ValidationError(
            "Playwright is not installed. Install the dev extras."
        ) from exc
    playwright_error = sync_api.Error
    sync_playwright = sync_api.sync_playwright

    fixture = load_fixture(config)
    org = fixture["organization"]["name"]
    repo = fixture["repository"]["name"]
    issue_title = fixture["issue"]["title"]
    release_text = fixture["release"]["name"]
    readme_text = "This repository is populated deterministically"
    resolved_screenshot_dir = (
        _resolve_screenshot_dir(config, screenshot_dir)
        if save_screenshots
        else None
    )
    screenshots: list[str] = []
    pages_verified: list[str] = []

    try:
        config.runtime_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="gitea-browser-",
            dir=config.runtime_dir,
        ):
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(
                    storage_state=None,
                    locale="en-US",
                    record_video_dir=None,
                )
                context.set_default_timeout(config.browser_timeout_ms)
                page = context.new_page()
                page.goto(f"{config.root_url}user/login", wait_until="load")
                page.fill('input[name="user_name"]', config.admin_user)
                page.fill('input[name="password"]', config.admin_password)
                page.get_by_role("button", name="Sign In").click()
                page.wait_for_url(config.root_url, wait_until="load")
                if "Dashboard" not in page.title():
                    raise ValidationError(
                        "Authenticated dashboard title was not rendered."
                    )
                pages_verified.append("authenticated dashboard")

                page.goto(f"{config.root_url}{org}", wait_until="load")
                _expect_visible_text(page, "Sandbox Labs")
                pages_verified.append("organization page")

                page.goto(f"{config.root_url}{org}/{repo}", wait_until="load")
                _expect_visible_text(page, readme_text)
                pages_verified.append("repository README")
                if resolved_screenshot_dir is not None:
                    _prepare_screenshot_dir(resolved_screenshot_dir)
                    repo_png = resolved_screenshot_dir / SCREENSHOT_NAMES[0]
                    page.screenshot(path=str(repo_png), full_page=True)
                    screenshots.append(str(repo_png.relative_to(config.repo_root)))

                page.goto(f"{config.root_url}{org}/{repo}/issues", wait_until="load")
                _expect_visible_text(page, issue_title)
                pages_verified.append("issue list")

                page.goto(f"{config.root_url}{org}/{repo}/releases", wait_until="load")
                _expect_visible_text(page, release_text)
                pages_verified.append("release page")
                if resolved_screenshot_dir is not None:
                    release_png = resolved_screenshot_dir / SCREENSHOT_NAMES[1]
                    page.screenshot(path=str(release_png), full_page=True)
                    screenshots.append(str(release_png.relative_to(config.repo_root)))

                context.close()
                browser.close()
    except playwright_error as exc:
        raise ValidationError(f"Browser validation failed: {exc}") from exc

    return {"pages_verified": pages_verified, "screenshots": screenshots}


def _resolve_screenshot_dir(
    config: SandboxConfig,
    screenshot_dir: Path | None,
) -> Path:
    if screenshot_dir is None:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        return (
            config.browser_evidence_dir
            / f"run-{stamp}-{uuid4().hex[:8]}"
        ).resolve()

    requested = screenshot_dir
    candidate = requested if requested.is_absolute() else config.repo_root / requested
    resolved = candidate.resolve()
    repo_root = config.repo_root.resolve()
    if repo_root not in (resolved, *resolved.parents):
        raise ValidationError(
            "Screenshot directory must be inside the repository. "
            "Use a repository-relative path or a path under <repo-root>."
        )
    return resolved


def _prepare_screenshot_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for name in SCREENSHOT_NAMES:
        target = path / name
        if target.exists():
            raise ValidationError(
                f"Screenshot output would overwrite existing file: {target}"
            )


def _expect_visible_text(page: Any, text: str) -> None:
    locator = page.get_by_text(text, exact=False).first
    matches = page.get_by_text(text, exact=False)
    elapsed = 0
    while elapsed <= 30_000:
        for index in range(matches.count()):
            if matches.nth(index).is_visible():
                return
        page.wait_for_timeout(250)
        elapsed += 250
    locator.wait_for(state="visible")
