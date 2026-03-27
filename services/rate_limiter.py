"""
services/rate_limiter.py
In-memory rate limiter (token bucket).
In production: use Redis for distributed rate limiting.
"""

import time
from collections import defaultdict
from threading import Lock


class RateLimiter:
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self._store = defaultdict(list)
        self._lock = Lock()

    def is_allowed(self, identifier: str) -> tuple[bool, dict]:
        now = time.time()
        with self._lock:
            requests = self._store[identifier]
            # Remove timestamps outside the window
            self._store[identifier] = [t for t in requests if now - t < self.window]
            count = len(self._store[identifier])

            if count >= self.max_requests:
                reset_in = self.window - (now - self._store[identifier][0])
                return False, {
                    "allowed": False,
                    "limit": self.max_requests,
                    "remaining": 0,
                    "reset_in_seconds": round(reset_in, 1),
                }

            self._store[identifier].append(now)
            return True, {
                "allowed": True,
                "limit": self.max_requests,
                "remaining": self.max_requests - count - 1,
                "reset_in_seconds": self.window,
            }
