"""A small in-memory rate limit: at most N hits per key over a sliding window.

Held by the process: with several workers, each counts on its own, which only makes the
limit a little looser. Used by the read-only demo (app/services/demo.py), keyed by the
visitor's address (uvicorn runs with --proxy-headers behind the proxy).
"""
from __future__ import annotations

from collections import deque
from threading import Lock
from time import monotonic

MAX_KEYS = 20_000


class SlidingWindowLimit:
    def __init__(self, limit: int, seconds: float):
        self.limit = limit
        self.seconds = seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()

    def allow(self, key: str, *, now: float | None = None) -> bool:
        """Count a hit for this key; False when it already reached the limit in the window."""
        now = monotonic() if now is None else now
        with self._lock:
            if len(self._hits) > MAX_KEYS:
                self._forget_idle(now)
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - self.seconds:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def _forget_idle(self, now: float) -> None:
        for key in [key for key, hits in self._hits.items() if not hits or hits[-1] <= now - self.seconds]:
            del self._hits[key]
