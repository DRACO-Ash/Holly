"""In-process rate limiting, in two tiers (api-and-integration).

The coarse tier counts every request except the platform probes and the dashboard's static
files, per client address; it protects the process. The fine tier counts sign-in attempts per
client address, failed sign-ins per username and assistant calls per user; it protects the
routes that cost money or invite password guessing. Both answer 429 with Retry-After.

The counters live in this process, so they reset when the container restarts. Holly runs one
worker (app/gunicorn_conf.py), so every request meets the same counters.
"""

import math
import time
from collections import deque
from collections.abc import Callable

from fastapi import HTTPException, status

# A bound on how many keys a limiter remembers, so a flood of distinct keys (random usernames,
# say) cannot grow memory without limit. When it is reached, the stalest key is forgotten.
MAX_TRACKED_KEYS = 10_000


class RateLimiter:
    """A sliding-window limiter: at most `limit` hits per key in any `window_seconds`."""

    def __init__(
        self,
        limit: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}

    def _current(self, key: str, now: float) -> deque[float]:
        # Pop and re-insert, so the dict stays in least-recently-used order: the first key is
        # always the stalest, and the one dropped when the bound is reached.
        hits = self._hits.pop(key, None) or deque()
        while hits and hits[0] <= now - self.window_seconds:
            hits.popleft()
        self._hits[key] = hits
        if len(self._hits) > MAX_TRACKED_KEYS:
            del self._hits[next(iter(self._hits))]
        return hits

    def wait_time(self, key: str) -> int:
        """0 when `key` is under the limit, else the seconds until it will be. Records nothing."""
        now = self._clock()
        hits = self._current(key, now)
        if len(hits) >= self.limit:
            return max(1, math.ceil(hits[0] + self.window_seconds - now))
        return 0

    def record(self, key: str) -> None:
        now = self._clock()
        self._current(key, now).append(now)

    def forget(self, key: str) -> None:
        self._hits.pop(key, None)

    def retry_after(self, key: str) -> int:
        """Like wait_time, but an allowed call is recorded as a hit."""
        wait = self.wait_time(key)
        if not wait:
            self.record(key)
        return wait

    def check(self, key: str) -> None:
        """Record a hit for `key`, raising 429 with Retry-After when it is over the limit."""
        wait = self.retry_after(key)
        if wait:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many requests. Try again in {wait} seconds.",
                headers={"Retry-After": str(wait)},
            )

    def reset(self) -> None:
        self._hits.clear()


# Coarse tier: per client address, every request except probes and static files.
GLOBAL_LIMIT = RateLimiter(limit=600, window_seconds=60)
# Fine tier: failed sign-ins per username (a success clears them), every sign-in attempt per
# client address (counted before its password is checked), and assistant calls per user.
LOGIN_LIMIT = RateLimiter(limit=10, window_seconds=15 * 60)
LOGIN_ADDRESS_LIMIT = RateLimiter(limit=30, window_seconds=60)
ASSISTANT_LIMIT = RateLimiter(limit=30, window_seconds=10 * 60)


def reset_all() -> None:
    """Forget every counter (used by tests)."""
    for limiter in (GLOBAL_LIMIT, LOGIN_LIMIT, LOGIN_ADDRESS_LIMIT, ASSISTANT_LIMIT):
        limiter.reset()
