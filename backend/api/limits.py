"""In-memory rate limits, so a shared or leaked link can't burn the minutes.

Per process: fine for the single server this runs as. Several replicas
would need a shared store instead.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable


class RateLimiter:
    """At most `limit` events per key in any `window` seconds."""

    def __init__(self, limit: int, window: float, clock: Callable[[], float] = time.monotonic):
        self.limit, self.window, self._clock = limit, window, clock
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._next_sweep = 0.0

    def allow(self, key: str) -> bool:
        now = self._clock()
        if now >= self._next_sweep:
            self._sweep(now)
        events = self._events[key]
        while events and events[0] <= now - self.window:
            events.popleft()
        if len(events) >= self.limit:
            return False
        events.append(now)
        return True

    def _sweep(self, now: float) -> None:
        """Forget keys with nothing in the window, so memory doesn't grow with
        every IP ever seen."""
        for key in [k for k, ev in self._events.items() if not ev or ev[-1] <= now - self.window]:
            del self._events[key]
        self._next_sweep = now + self.window
