"""Request pacing and Retry-After parsing."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from typing import Any

import httpx
import pytest

from seventhings import DEFAULT_REQUESTS_PER_MINUTE, APIError, AsyncClient, Client
from seventhings._rate_limit import AsyncRateLimiter, RateLimiter

from .conftest import Harness


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    async def asleep(self, seconds: float) -> None:
        self.sleep(seconds)


# -- rate limiting -------------------------------------------------------------


def test_default_rate_limit() -> None:
    assert DEFAULT_REQUESTS_PER_MINUTE == 200
    for cls in (Client, AsyncClient):
        client: Any = cls("https://x.example")
        assert client._rate_limiter._interval == pytest.approx(0.3)


@pytest.mark.parametrize(("limit", "gap"), [(200, 0.3), (60, 1.0), (600, 0.1)])
def test_sync_limiter_spacing(limit: int, gap: float) -> None:
    clock = FakeClock()
    limiter = RateLimiter(limit, clock=clock, sleep=clock.sleep)
    for _ in range(3):
        limiter.wait()
    assert clock.sleeps == pytest.approx([gap, gap])


@pytest.mark.parametrize(("limit", "gap"), [(200, 0.3), (60, 1.0), (600, 0.1)])
def test_async_limiter_spacing(limit: int, gap: float) -> None:
    clock = FakeClock()
    limiter = AsyncRateLimiter(limit, clock=clock, sleep=clock.asleep)

    async def run() -> None:
        for _ in range(3):
            await limiter.wait()

    asyncio.run(run())
    assert clock.sleeps == pytest.approx([gap, gap])


@pytest.mark.parametrize("limit", [0, -1, None])
def test_limiter_disabled(limit: int | None) -> None:
    clock = FakeClock()
    limiter = RateLimiter(limit, clock=clock, sleep=clock.sleep)
    alimiter = AsyncRateLimiter(limit, clock=clock, sleep=clock.asleep)
    for _ in range(3):
        limiter.wait()
        asyncio.run(alimiter.wait())
    assert clock.sleeps == []


def test_limiter_no_wait_after_idle() -> None:
    clock = FakeClock()
    limiter = RateLimiter(60, clock=clock, sleep=clock.sleep)
    limiter.wait()
    clock.now += 5
    limiter.wait()
    assert clock.sleeps == []


def test_async_limiter_fifo_and_cancellation() -> None:
    order: list[int] = []

    async def run() -> None:
        limiter = AsyncRateLimiter(600)  # 100 ms apart, real time
        await limiter.wait()

        async def waiter(i: int) -> None:
            await limiter.wait()
            order.append(i)

        tasks = [asyncio.create_task(waiter(i)) for i in range(4)]
        await asyncio.sleep(0)
        tasks[1].cancel()  # a cancelled waiter must not consume a slot
        loop = asyncio.get_running_loop()
        start = loop.time()
        await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = loop.time() - start
        assert 0.25 <= elapsed < 0.45  # three slots, not four

    asyncio.run(run())
    assert order == [0, 2, 3]


def test_client_paces_requests_across_kinds(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = FakeClock()
    monkeypatch.setattr("seventhings._rate_limit.time.monotonic", clock)
    monkeypatch.setattr("seventhings._rate_limit.time.sleep", clock.sleep)
    transport = httpx.MockTransport(
        lambda r: httpx.Response(200, json={"access_token": "t"}, headers={"Location-UUID": "f"})
    )
    with Client("https://x.example", http_client=httpx.Client(transport=transport)) as c:
        c._rate_limiter = RateLimiter(200, clock=clock, sleep=clock.sleep)
        c.objects.list()
        c.files.get_data("f")
        c.files.upload("a.txt", b"data")
        c.auth.login("user", "pw", "client")
        c.auth.login_authorization_code("code", "verifier", "uri", "client")
    assert clock.sleeps == pytest.approx([0.3] * 4)


# -- error headers and Retry-After ------------------------------------------------

NOW = datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)


def _http_date(dt: datetime) -> str:
    return format_datetime(dt, usegmt=True)


@pytest.mark.parametrize(
    ("value", "want"),
    [
        ("120", timedelta(minutes=2)),
        ("0", timedelta(0)),
        (" 42 \t", timedelta(seconds=42)),
        (_http_date(NOW + timedelta(seconds=90)), timedelta(seconds=90)),
        (_http_date(NOW - timedelta(hours=1)), timedelta(0)),
        (_http_date(NOW), timedelta(0)),
        ("", None),
        ("-1", None),
        ("+1", None),
        ("1.5", None),
        ("tomorrow", None),
        ("1, 2", None),
        ("9" * 30, None),
    ],
)
def test_retry_after(value: str, want: timedelta | None) -> None:
    err = APIError(429, "429 Too Many Requests", "", httpx.Headers({"Retry-After": value}))
    assert err.retry_after(NOW) == want


def test_retry_after_missing_or_repeated() -> None:
    assert APIError(429, "429", "").retry_after(NOW) is None
    repeated = httpx.Headers([("Retry-After", "1"), ("Retry-After", "2")])
    assert APIError(429, "429", "", repeated).retry_after(NOW) is None


def test_retry_after_naive_now_is_utc() -> None:
    err = APIError(
        503, "503", "", httpx.Headers({"Retry-After": _http_date(NOW + timedelta(seconds=5))})
    )
    assert err.retry_after(NOW.replace(tzinfo=None)) == timedelta(seconds=5)


def test_error_message_excludes_headers() -> None:
    err = APIError(
        429, "429 Too Many Requests", "slow down", httpx.Headers({"X-Request-ID": "secret-id"})
    )
    assert "secret-id" not in str(err)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.objects.list(),
        lambda c: c.request("POST", "auth_token", json={}, authenticated=False),
        lambda c: c.files.get_data("f"),
        lambda c: c.files.upload("a.txt", b"data"),
    ],
    ids=["authenticated", "unauthenticated", "download", "upload"],
)
def test_error_headers_and_no_automatic_retry(h: Harness, call: Any) -> None:
    h.respond(
        429,
        content=b"Too Many Requests",
        headers={"Retry-After": "120", "X-Request-ID": "request-id"},
    )
    with pytest.raises(APIError) as info:
        h.call(call)
    err = info.value
    assert err.is_rate_limited and err.body == "Too Many Requests"
    assert err.headers["X-Request-ID"] == "request-id"
    assert err.retry_after() == timedelta(minutes=2)
    assert len(h.requests) == 1
