from __future__ import annotations

import urllib.error
import urllib.request
from email.message import Message
from io import BytesIO
from typing import Any

import pytest

from gitea_sandbox_adapter.api import ApiClient
from gitea_sandbox_adapter.errors import ApiError


class FakeResponse:
    def __init__(
        self,
        status: int,
        body: bytes,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self._body = body
        self.headers = headers or {}

    def read(self, _size: int = -1) -> bytes:
        return self._body

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def http_error(status: int, body: bytes = b"{}") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "http://example.invalid",
        status,
        "error",
        Message(),
        BytesIO(body),
    )


def test_transient_http_error_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def fake_urlopen(*args: Any, **kwargs: Any) -> FakeResponse:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise http_error(503, b'{"error":"temporary"}')
        return FakeResponse(200, b'{"ok":true}')

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    result = ApiClient("http://example.invalid", retries=2).get("health")

    assert result == {"ok": True}
    assert calls == 2


def test_permanent_http_error_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def fake_urlopen(*args: Any, **kwargs: Any) -> FakeResponse:
        nonlocal calls
        calls += 1
        raise http_error(404, b'{"message":"missing"}')

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(ApiError, match="HTTP 404"):
        ApiClient("http://example.invalid", retries=3).get("missing")
    assert calls == 1


def test_malformed_json_raises_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(*args: Any, **kwargs: Any) -> FakeResponse:
        return FakeResponse(200, b"not-json")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(ApiError, match="Malformed JSON"):
        ApiClient("http://example.invalid").get("bad")


def test_paginated_single_short_page(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(*args: Any, **kwargs: Any) -> FakeResponse:
        return FakeResponse(200, b'[{"id":1}]')

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    assert ApiClient("http://example.invalid").list_paginated("items") == [{"id": 1}]


def test_paginated_multiple_pages_until_short_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bodies = [b'[{"id":1},{"id":2}]', b'[{"id":3}]']

    def fake_urlopen(*args: Any, **kwargs: Any) -> FakeResponse:
        return FakeResponse(200, bodies.pop(0))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    result = ApiClient("http://example.invalid").list_paginated("items", limit=2)

    assert result == [{"id": 1}, {"id": 2}, {"id": 3}]


def test_paginated_link_header_termination(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [
        FakeResponse(
            200,
            b'[{"id":1},{"id":2}]',
            {"Link": '<http://example.invalid/items?page=2>; rel="next"'},
        ),
        FakeResponse(
            200,
            b'[{"id":3},{"id":4}]',
            {"Link": '<http://example.invalid/items?page=2>; rel="last"'},
        ),
    ]

    def fake_urlopen(*args: Any, **kwargs: Any) -> FakeResponse:
        return responses.pop(0)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    result = ApiClient("http://example.invalid").list_paginated("items", limit=2)

    assert result == [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}]
    assert responses == []


def test_paginated_max_page_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(*args: Any, **kwargs: Any) -> FakeResponse:
        return FakeResponse(200, b'[{"id":1}]')

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(ApiError, match="maximum pages"):
        ApiClient("http://example.invalid").list_paginated(
            "items", limit=1, max_pages=2
        )


def test_paginated_deadline_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    times = iter([0.0, 2.0])

    def fake_urlopen(*args: Any, **kwargs: Any) -> FakeResponse:
        return FakeResponse(200, b'[{"id":1}]')

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr("gitea_sandbox_adapter.api.time.monotonic", lambda: next(times))

    with pytest.raises(ApiError, match="deadline exceeded"):
        ApiClient("http://example.invalid").list_paginated(
            "items", deadline_seconds=1.0
        )


def test_paginated_malformed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(*args: Any, **kwargs: Any) -> FakeResponse:
        return FakeResponse(200, b"not-json")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(ApiError, match="Malformed JSON"):
        ApiClient("http://example.invalid").list_paginated("items")


def test_paginated_permanent_http_failure_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_urlopen(*args: Any, **kwargs: Any) -> FakeResponse:
        nonlocal calls
        calls += 1
        raise http_error(403, b'{"message":"forbidden"}')

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(ApiError, match="HTTP 403"):
        ApiClient("http://example.invalid", retries=3).list_paginated("items")
    assert calls == 1
