"""In-memory sliding-window rate limiter shared by every endpoint that needs a request limit.

Counters live in the API process, so they reset on restart and are not shared between several
API workers. That is enough for the MVP (one container); a shared store can replace it later
behind the same interface.
"""

import math
import time
from collections import deque
from threading import Lock

from fastapi import HTTPException, Request, status

TOO_MANY_ATTEMPTS = "Too many attempts. Please wait a moment and try again."


class RateLimiter:
    """Counts hits per key and blocks a key once it reaches `limit` hits inside `window` seconds.

    Only keys with hits inside their window are kept: asking about a key never stores it, and a
    sweep every SWEEP_INTERVAL seconds drops keys whose newest hit is older than their window, so
    many different keys (e.g. one per e-mail tried at login) cannot grow memory without bound.
    """

    SWEEP_INTERVAL = 60.0

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        # The window each key was last hit with, so the sweep knows when the key has expired
        self._windows: dict[str, float] = {}
        self._lock = Lock()
        self._next_sweep = time.monotonic() + self.SWEEP_INTERVAL

    def retry_after(self, key: str, limit: int, window: float) -> int | None:
        """Seconds until the key may try again, or None when it is under the limit."""
        now = time.monotonic()
        with self._lock:
            hits = self._prune(key, now, window)
            if len(hits) < limit:
                return None
            return max(1, math.ceil(hits[0] + window - now))

    def hit(self, key: str, window: float) -> None:
        now = time.monotonic()
        with self._lock:
            self._sweep(now)
            hits = self._prune(key, now, window)
            hits.append(now)
            self._hits[key] = hits
            self._windows[key] = window

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)
            self._windows.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()
            self._windows.clear()

    def __len__(self) -> int:
        """Keys currently stored (for tests and monitoring)."""
        with self._lock:
            return len(self._hits)

    def _prune(self, key: str, now: float, window: float) -> deque[float]:
        """The key's hits inside the window. A key left without hits is removed, not stored."""
        hits = self._hits.get(key)
        if hits is None:
            return deque()
        while hits and hits[0] <= now - window:
            hits.popleft()
        if not hits:
            del self._hits[key]
            self._windows.pop(key, None)
        return hits

    def _sweep(self, now: float) -> None:
        """Drop every key whose newest hit is outside its window; runs at most once per interval."""
        if now < self._next_sweep:
            return
        self._next_sweep = now + self.SWEEP_INTERVAL
        expired = [key for key, hits in self._hits.items() if hits[-1] <= now - self._windows[key]]
        for key in expired:
            del self._hits[key]
            del self._windows[key]


def raise_if_limited(
    limiter: RateLimiter, key: str, limit: int, window: float, detail: str = TOO_MANY_ATTEMPTS
) -> None:
    """Answer 429 with a Retry-After header when the key has used up its attempts."""
    retry_after = limiter.retry_after(key, limit, window)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={"Retry-After": str(retry_after)},
        )


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
