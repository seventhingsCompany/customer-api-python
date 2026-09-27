"""I/O-free request description shared by the sync and async clients."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Generic, TypeVar
from urllib.parse import quote

import httpx

from ._version import __version__
from .errors import APIError, DecodeError

T = TypeVar("T")

API_PREFIX = "/customer-api/v1"
USER_AGENT = f"seventhings-customer-api-python/{__version__}"
JSON = "application/json"


class _Unset:
    def __repr__(self) -> str:
        return "UNSET"


UNSET: Any = _Unset()
"""Marks "no request body" (distinct from a JSON ``null`` body)."""


@dataclass(frozen=True, slots=True)
class Response:
    """Raw HTTP response of a successful (status < 400) request."""

    status_code: int
    headers: httpx.Headers
    content: bytes

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    def header(self, name: str) -> str | None:
        """Case-insensitive header lookup; returns the first value or None."""
        value: str | None = self.headers.get(name)
        return value

    def json(self) -> Any:
        """Decode the body as JSON, raising DecodeError on invalid input."""
        try:
            return json.loads(self.content)
        except ValueError as exc:
            raise DecodeError(f"invalid JSON response: {exc}") from exc


@dataclass(frozen=True, slots=True)
class Operation(Generic[T]):
    """Everything needed to perform one API call and decode its result."""

    method: str
    path: str
    parse: Callable[[Response], T]
    query: str = ""
    json: Any = UNSET
    files: Mapping[str, Any] | None = None
    accept: str | None = JSON
    authenticated: bool = True


def segment(value: str | int) -> str:
    """Escape a value for use as a single URL path segment (like Go's url.PathEscape)."""
    return quote(str(value), safe="$&+:=@")


def base_url(instance_url: str) -> str:
    return instance_url.rstrip("/") + API_PREFIX


def build_url(base: str, path: str, query: str = "") -> str:
    url = base
    if path:
        url += "/" + path.lstrip("/")
    if query:
        url += "?" + query
    return url


def encode_json(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def build_request(
    http: httpx.Client | httpx.AsyncClient, base: str, token: str | None, op: Operation[Any]
) -> httpx.Request:
    headers: dict[str, str] = {}
    if op.accept is not None:
        headers["Accept"] = op.accept
    if op.authenticated and token:
        headers["Authorization"] = "Bearer " + token

    content: bytes | None = None
    if op.json is not UNSET:
        content = encode_json(op.json)
        headers["Content-Type"] = JSON

    return http.build_request(
        op.method,
        build_url(base, op.path, op.query),
        headers=headers,
        content=content,
        files=op.files,
    )


def to_response(resp: httpx.Response) -> Response:
    """Convert an httpx response, raising APIError for status >= 400."""
    if resp.status_code >= 400:
        status = f"{resp.status_code} {resp.reason_phrase}".strip()
        raise APIError(resp.status_code, status, resp.text)
    return Response(resp.status_code, resp.headers, resp.content)


def default_headers() -> dict[str, str]:
    return {"User-Agent": USER_AGENT}
