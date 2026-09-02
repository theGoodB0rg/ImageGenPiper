"""Token-Bucket Rate Limiter with randomized human jitter delay."""

import asyncio
import random
import time
from typing import Tuple


class TokenBucketRateLimiter:
    """
    Token-bucket rate limiter ensuring compliance with Gemini request thresholds
    and mimicking human browsing patterns with jitter.
    """

    def __init__(
        self,
        rate_limit_rpm: float = 6.0,
        burst_capacity: float = 2.0,
        jitter_range: Tuple[float, float] = (1.0, 3.0),
    ):
        """
        :param rate_limit_rpm: Allowed requests per minute
        :param burst_capacity: Maximum tokens that can accumulate in the bucket
        :param jitter_range: (min_seconds, max_seconds) added jitter per acquisition
        """
        self.rate_limit_rpm = max(0.1, rate_limit_rpm)
        self.burst_capacity = max(1.0, burst_capacity)
        self.jitter_range = jitter_range

        self._tokens = float(self.burst_capacity)
        self._refill_rate = self.rate_limit_rpm / 60.0  # tokens per second
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """
        Wait until a token is available, consume it, and apply randomized human jitter.
        """
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._tokens = min(self.burst_capacity, self._tokens + (elapsed * self._refill_rate))
                self._last_refill = now

                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    break

                # Calculate wait time until 1 token is available
                needed = 1.0 - self._tokens
                wait_seconds = needed / self._refill_rate
                await asyncio.sleep(wait_seconds)

        # Apply human jitter delay
        min_jitter, max_jitter = self.jitter_range
        if max_jitter > 0 and max_jitter >= min_jitter:
            jitter_delay = random.uniform(min_jitter, max_jitter)
            if jitter_delay > 0:
                await asyncio.sleep(jitter_delay)
