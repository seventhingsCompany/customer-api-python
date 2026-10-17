"""Per-client request pacing shared by every request a client sends.

Requests are evenly spaced (``60 / requests_per_minute`` seconds apart) without
bursts; the first request is immediate. Separate clients do not share a limit.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Awaitable, Callable

DEFAULT_REQUESTS_PER_MINUTE = 200


def interval(requests_per_minute: int | None) -> float | None:
    """Seconds between requests, or None when throttling is disabled (None or <= 0)."""
    if requests_per_minute is None or requests_per_minute <= 0:
        return None
    return 60.0 / requests_per_minute


class RateLimiter:
    """Thread-safe pacing for the sync client.

    Callers are admitted one at a time: the lock is held while sleeping and the
    next slot is set from the clock at admission, so a caller that wakes late
    can never be admitted right after another one.
    """

    def __init__(
        self,
        requests_per_minute: int | None,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._interval = interval(requests_per_minute)
        self._clock = clock
        self._sleep = sleep
        self._next: float | None = None
        self._lock = threading.Lock()

    def wait(self) -> None:
        if self._interval is None:
            return
        with self._lock:
            while self._next is not None and (delay := self._next - self._clock()) > 0:
                self._sleep(delay)
            self._next = self._clock() + self._interval


class AsyncRateLimiter:
    """Pacing for the async client.

    Waiters queue on an ``asyncio.Lock`` (FIFO) and only the head sleeps for the
    next slot, so a cancelled waiter is removed without consuming a slot.
    """

    def __init__(
        self,
        requests_per_minute: int | None,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._interval = interval(requests_per_minute)
        self._clock = clock
        self._sleep = sleep
        self._next: float | None = None
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        if self._interval is None:
            return
        async with self._lock:
            while self._next is not None and (delay := self._next - self._clock()) > 0:
                await self._sleep(delay)
            self._next = self._clock() + self._interval
