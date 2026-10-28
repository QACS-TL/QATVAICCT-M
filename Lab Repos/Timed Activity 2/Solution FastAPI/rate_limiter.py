from threading import RLock
from time import time
from typing import MutableMapping


class RateLimiter:
    def __init__(
        self,
        max_requests: int = 100,
        window_seconds: int = 10,
    ) -> None:
        if max_requests < 1:
            raise ValueError("max_requests must be at least 1")
        if window_seconds < 1:
            raise ValueError("window_seconds must be at least 1")

        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: MutableMapping[str, tuple[float, int]] = {}
        self._lock = RLock()
        self._last_cleanup = 0.0

    def allow_request(self, user_id: str) -> bool:
        now = time()
        with self._lock:
            if now - self._last_cleanup >= self.window_seconds:
                self._remove_expired_requests(now)
                self._last_cleanup = now

            window_start, count = self.requests.get(user_id, (now, 0))
            if now - window_start >= self.window_seconds:
                window_start, count = now, 0

            if count >= self.max_requests:
                return False

            self.requests[user_id] = (window_start, count + 1)
            return True

    def retry_after(self, user_id: str) -> int:
        with self._lock:
            entry = self.requests.get(user_id)
            if entry is None:
                return 0

            window_start, _ = entry
            remaining = window_start + self.window_seconds - time()
            return max(1, int(remaining + 0.999))

    def _remove_expired_requests(self, now: float) -> None:
        expired_users = [
            user_id
            for user_id, (window_start, _) in self.requests.items()
            if now - window_start >= self.window_seconds
        ]
        for user_id in expired_users:
            del self.requests[user_id]
