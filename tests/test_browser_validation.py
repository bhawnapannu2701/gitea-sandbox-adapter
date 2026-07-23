from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from gitea_sandbox_adapter.browser_validation import validate_browser
from gitea_sandbox_adapter.errors import ValidationError
from tests.test_docker import fake_config


def test_browser_validation_reports_missing_playwright(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = fake_config(tmp_path)
    (tmp_path / "fixtures").mkdir()
    (tmp_path / "fixtures" / "gitea_seed.json").write_text(
        '{"schema_version": 1, "organization": {"name": "sandbox-labs"}, '
        '"repository": {"name": "adapter-demo"}, '
        '"issue": {"title": "issue"}, "release": {"name": "release"}}',
        encoding="utf-8",
    )

    def missing(_name: str) -> object:
        raise ImportError("missing")

    monkeypatch.setattr(importlib, "import_module", missing)

    with pytest.raises(ValidationError, match="Playwright is not installed"):
        validate_browser(config)


def test_default_browser_validation_uses_ignored_runtime_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = fake_config(tmp_path)
    write_browser_fixture(tmp_path)
    install_fake_playwright(monkeypatch)

    result = validate_browser(config)

    screenshots = result["screenshots"]
    assert len(screenshots) == 2
    assert all(
        str(path).replace("\\", "/").startswith(".gitea-sandbox/browser-evidence/")
        for path in screenshots
    )
    assert not (tmp_path / "docs" / "evidence" / "browser-repository.png").exists()
    for relative in screenshots:
        assert (tmp_path / str(relative)).exists()


def test_browser_validation_no_screenshots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = fake_config(tmp_path)
    write_browser_fixture(tmp_path)
    install_fake_playwright(monkeypatch)

    result = validate_browser(config, save_screenshots=False)

    assert result["screenshots"] == []
    assert not config.browser_evidence_dir.exists()


def test_browser_validation_explicit_screenshot_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = fake_config(tmp_path)
    write_browser_fixture(tmp_path)
    install_fake_playwright(monkeypatch)

    result = validate_browser(config, screenshot_dir=Path("public-evidence/manual"))

    screenshots = result["screenshots"]
    assert [str(path).replace("\\", "/") for path in screenshots] == [
        "public-evidence/manual/browser-repository.png",
        "public-evidence/manual/browser-release.png",
    ]
    for relative in screenshots:
        assert (tmp_path / str(relative)).exists()


def test_browser_validation_rejects_unsafe_screenshot_dir(
    tmp_path: Path,
) -> None:
    config = fake_config(tmp_path)
    write_browser_fixture(tmp_path)

    with pytest.raises(ValidationError, match="inside the repository"):
        validate_browser(config, screenshot_dir=tmp_path.parent / "outside")


def write_browser_fixture(root: Path) -> None:
    (root / "fixtures").mkdir()
    (root / "fixtures" / "gitea_seed.json").write_text(
        '{"schema_version": 1, '
        '"organization": {"name": "sandbox-labs"}, '
        '"repository": {"name": "adapter-demo"}, '
        '"issue": {"title": "issue"}, '
        '"release": {"name": "release"}}',
        encoding="utf-8",
    )


class FakeLocator:
    @property
    def first(self) -> FakeLocator:
        return self

    def click(self) -> None:
        return None

    def count(self) -> int:
        return 1

    def nth(self, _index: int) -> FakeLocator:
        return self

    def is_visible(self) -> bool:
        return True

    def wait_for(self, *, state: str) -> None:
        del state


class FakePage:
    def goto(self, _url: str, *, wait_until: str) -> None:
        del wait_until

    def fill(self, _selector: str, _value: str) -> None:
        return None

    def get_by_role(self, _role: str, *, name: str) -> FakeLocator:
        del name
        return FakeLocator()

    def wait_for_url(self, _url: str, *, wait_until: str) -> None:
        del wait_until

    def title(self) -> str:
        return "Dashboard - Gitea"

    def get_by_text(self, _text: str, *, exact: bool) -> FakeLocator:
        del exact
        return FakeLocator()

    def screenshot(self, *, path: str, full_page: bool) -> None:
        del full_page
        Path(path).write_bytes(b"fake-png")

    def wait_for_timeout(self, _milliseconds: int) -> None:
        return None


class FakeContext:
    def set_default_timeout(self, _timeout: int) -> None:
        return None

    def new_page(self) -> FakePage:
        return FakePage()

    def close(self) -> None:
        return None


class FakeBrowser:
    def new_context(self, **kwargs: Any) -> FakeContext:
        assert kwargs["storage_state"] is None
        return FakeContext()

    def close(self) -> None:
        return None


class FakeChromium:
    def launch(self, *, headless: bool) -> FakeBrowser:
        assert headless is True
        return FakeBrowser()


class FakePlaywrightContext:
    def __enter__(self) -> SimpleNamespace:
        return SimpleNamespace(chromium=FakeChromium())

    def __exit__(self, *args: object) -> None:
        return None


def install_fake_playwright(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = SimpleNamespace(
        Error=Exception,
        sync_playwright=lambda: FakePlaywrightContext(),
    )
    monkeypatch.setattr(importlib, "import_module", lambda _name: fake_module)
