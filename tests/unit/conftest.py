"""Test harness that runs every test against both the sync and the async client."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qsl

import httpx
import pytest

from seventhings import AsyncClient, Client

BASE = "https://example.seventhings.com"
PREFIX = "/customer-api/v1"
TOKEN = "test-token"

_UNSET: Any = object()


class Harness:
    """Queues canned responses and records requests for one client flavour."""

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.requests: list[httpx.Request] = []
        self._responses: list[httpx.Response] = []
        self.token: str | None = TOKEN
        self.client_id: str | None = None

    # -- responses ---------------------------------------------------------

    def respond(
        self,
        status: int = 200,
        json_body: Any = _UNSET,
        *,
        content: bytes = b"",
        headers: dict[str, str] | None = None,
    ) -> Harness:
        if json_body is not _UNSET:
            content = json.dumps(json_body).encode()
        self._responses.append(httpx.Response(status, content=content, headers=headers))
        return self

    def _handle(self, request: httpx.Request) -> httpx.Response:
        request.read()
        self.requests.append(request)
        if not self._responses:
            return httpx.Response(204)
        resp = self._responses.pop(0)
        return httpx.Response(resp.status_code, content=resp.content, headers=resp.headers)

    # -- running -----------------------------------------------------------

    def call(self, fn: Callable[[Any], Any]) -> Any:
        """Run fn(client); for the async flavour fn returns an awaitable."""
        transport = httpx.MockTransport(self._handle)
        if self.mode == "sync":
            with Client(
                BASE,
                token=self.token,
                client_id=self.client_id,
                http_client=httpx.Client(transport=transport),
            ) as c:
                return fn(c)

        async def run() -> Any:
            async with AsyncClient(
                BASE,
                token=self.token,
                client_id=self.client_id,
                http_client=httpx.AsyncClient(transport=transport),
            ) as c:
                return await fn(c)

        return asyncio.run(run())

    def collect(self, fn: Callable[[Any], Any]) -> list[Any]:
        """Drain the (async) iterator returned by fn(client) into a list."""
        if self.mode == "sync":
            return self.call(lambda c: list(fn(c)))  # type: ignore[no-any-return]

        async def drain(c: Any) -> list[Any]:
            return [item async for item in fn(c)]

        return self.call(drain)  # type: ignore[no-any-return]

    def with_client(self, fn: Callable[[Any], Any]) -> Any:
        """Like call(), but also returns the client so state (token, client_id) can be read."""
        holder: dict[str, Any] = {}

        def capture(c: Any) -> Any:
            holder["client"] = c
            return fn(c)

        result = self.call(capture)
        return result, holder["client"]

    # -- inspection --------------------------------------------------------

    @property
    def last(self) -> httpx.Request:
        return self.requests[-1]

    def path(self, index: int = -1) -> str:
        raw = self.requests[index].url.raw_path.decode()
        path = raw.split("?", 1)[0]
        assert path.startswith(PREFIX), path
        return path[len(PREFIX) :]

    def query(self, index: int = -1) -> str:
        return self.requests[index].url.query.decode()

    def query_pairs(self, index: int = -1) -> list[tuple[str, str]]:
        return parse_qsl(self.query(index), keep_blank_values=True)

    def body(self, index: int = -1) -> Any:
        return json.loads(self.requests[index].content)


@pytest.fixture(params=["sync", "async"])
def h(request: pytest.FixtureRequest) -> Harness:
    return Harness(request.param)
