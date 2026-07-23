"""Small Gitea REST API client using the Python standard library."""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Mapping
from typing import Any

from gitea_sandbox_adapter.errors import ApiError
from gitea_sandbox_adapter.redaction import redact

JSON = dict[str, Any] | list[Any] | str | int | float | bool | None
MAX_BODY_BYTES = 5 * 1024 * 1024
TRANSIENT_STATUSES = {500, 502, 503, 504}
DEFAULT_MAX_PAGES = 100
DEFAULT_PAGINATION_DEADLINE_SECONDS = 60.0


class ApiClient:
    def __init__(
        self,
        base_url: str,
        *,
        token: str | None = None,
        basic_auth: tuple[str, str] | None = None,
        timeout: int = 20,
        retries: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.basic_auth = basic_auth
        self.timeout = timeout
        self.retries = retries

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: JSON = None,
        expected: Iterable[int] = (200,),
    ) -> Any:
        data, _headers = self.request_with_headers(
            method,
            path,
            json_body=json_body,
            expected=expected,
        )
        return data

    def request_with_headers(
        self,
        method: str,
        path: str,
        *,
        json_body: JSON = None,
        expected: Iterable[int] = (200,),
    ) -> tuple[Any, Mapping[str, str]]:
        expected_set = set(expected)
        body: bytes | None = None
        headers = {
            "Accept": "application/json",
            "User-Agent": "gitea-sandbox-adapter/0.1.0",
        }
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        if self.basic_auth:
            user, password = self.basic_auth
            raw = f"{user}:{password}".encode()
            headers["Authorization"] = f"Basic {base64.b64encode(raw).decode('ascii')}"

        url = f"{self.base_url}/{path.lstrip('/')}"
        attempts = max(1, self.retries)
        last_error: str | None = None
        for attempt in range(1, attempts + 1):
            request = urllib.request.Request(
                url, data=body, method=method, headers=headers
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    status = response.status
                    response_body = response.read(MAX_BODY_BYTES + 1)
                    if len(response_body) > MAX_BODY_BYTES:
                        raise ApiError(f"Response body too large for {method} {path}")
                    if status not in expected_set:
                        text = response_body.decode("utf-8", errors="replace")
                        raise ApiError(
                            redact(
                                "Unexpected API status "
                                f"{status} for {method} {path}: {text}"
                            )
                        )
                    return _decode_response(response_body), _headers(response.headers)
            except urllib.error.HTTPError as exc:
                response_body = exc.read(MAX_BODY_BYTES)
                text = response_body.decode("utf-8", errors="replace")
                if exc.code in expected_set:
                    return _decode_response(response_body), _headers(exc.headers)
                if exc.code in TRANSIENT_STATUSES and attempt < attempts:
                    last_error = redact(f"HTTP {exc.code}: {text}")
                    time.sleep(attempt)
                    continue
                raise ApiError(
                    redact(
                        "API request failed with HTTP "
                        f"{exc.code} for {method} {path}: {text}"
                    )
                ) from exc
            except urllib.error.URLError as exc:
                if attempt < attempts:
                    last_error = redact(str(exc))
                    time.sleep(attempt)
                    continue
                raise ApiError(
                    redact(f"API request failed for {method} {path}: {exc}")
                ) from exc
        raise ApiError(redact(f"API request failed for {method} {path}: {last_error}"))

    def get(self, path: str, *, expected: Iterable[int] = (200,)) -> Any:
        return self.request("GET", path, expected=expected)

    def post(
        self,
        path: str,
        body: JSON,
        *,
        expected: Iterable[int] = (200, 201),
    ) -> Any:
        return self.request("POST", path, json_body=body, expected=expected)

    def patch(
        self,
        path: str,
        body: JSON,
        *,
        expected: Iterable[int] = (200,),
    ) -> Any:
        return self.request("PATCH", path, json_body=body, expected=expected)

    def put(
        self,
        path: str,
        body: JSON = None,
        *,
        expected: Iterable[int] = (200, 201, 204),
    ) -> Any:
        return self.request("PUT", path, json_body=body, expected=expected)

    def delete(self, path: str, *, expected: Iterable[int] = (204,)) -> Any:
        return self.request("DELETE", path, expected=expected)

    def list_paginated(
        self,
        path: str,
        *,
        limit: int = 50,
        max_pages: int = DEFAULT_MAX_PAGES,
        deadline_seconds: float = DEFAULT_PAGINATION_DEADLINE_SECONDS,
    ) -> list[Any]:
        if max_pages < 1:
            raise ApiError("Pagination max_pages must be at least 1.")
        if deadline_seconds <= 0:
            raise ApiError("Pagination deadline_seconds must be positive.")
        items: list[Any] = []
        page = 1
        joiner = "&" if "?" in path else "?"
        deadline = time.monotonic() + deadline_seconds
        while page <= max_pages:
            if time.monotonic() > deadline:
                raise ApiError(f"Pagination deadline exceeded for {path}.")
            page_path = f"{path}{joiner}page={page}&limit={limit}"
            data, headers = self.request_with_headers("GET", page_path)
            if time.monotonic() > deadline:
                raise ApiError(f"Pagination deadline exceeded for {path}.")
            if not isinstance(data, list):
                raise ApiError(f"Expected list response for {path}")
            items.extend(data)
            link_header = headers.get("link", "")
            if link_header and not _link_has_next(link_header):
                return items
            if not link_header and len(data) < limit:
                return items
            page += 1
        raise ApiError(f"Pagination exceeded maximum pages ({max_pages}) for {path}.")


def quote_path(value: str) -> str:
    return urllib.parse.quote(value, safe="")


def _decode_response(body: bytes) -> Any:
    if not body:
        return None
    text = body.decode("utf-8", errors="replace")
    if not text.strip():
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ApiError(redact(f"Malformed JSON response: {text[:500]}")) from exc


def _headers(values: Any) -> Mapping[str, str]:
    if values is None:
        return {}
    return {str(key).lower(): str(value) for key, value in values.items()}


def _link_has_next(header: str) -> bool:
    return any(
        'rel="next"' in part.lower() or "rel=next" in part.lower()
        for part in header.split(",")
    )
