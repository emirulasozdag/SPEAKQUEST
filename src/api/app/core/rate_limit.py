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
    """Counts hits per key and blocks a key once it reaches `limit` hits inside `window` seconds."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()

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
            self._prune(key, now, window).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()

    def _prune(self, key: str, now: float, window: float) -> deque[float]:
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= now - window:
            hits.popleft()
        return hits


def raise_if_limited(limiter: RateLimiter, key: str, limit: int, window: float) -> None:
    """Answer 429 with a Retry-After header when the key has used up its attempts."""
    retry_after = limiter.retry_after(key, limit, window)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=TOO_MANY_ATTEMPTS,
            headers={"Retry-After": str(retry_after)},
        )


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
