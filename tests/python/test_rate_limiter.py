import asyncio
import time
import pytest
from core.rate_limiter import TokenBucketRateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_immediate_acquisition():
    # Capacity 2 tokens, 60 RPM
    limiter = TokenBucketRateLimiter(rate_limit_rpm=60, burst_capacity=2, jitter_range=(0.0, 0.0))
    
    t0 = time.monotonic()
    await limiter.acquire()
    await limiter.acquire()
    t1 = time.monotonic()

    # Both tokens consumed immediately without delay
    assert (t1 - t0) < 0.1


@pytest.mark.asyncio
async def test_rate_limiter_throttling():
    # Capacity 1 token, 120 RPM (0.5s refill)
    limiter = TokenBucketRateLimiter(rate_limit_rpm=120, burst_capacity=1, jitter_range=(0.0, 0.0))

    await limiter.acquire()  # Consumes initial token
    t0 = time.monotonic()
    await limiter.acquire()  # Must wait for refill (~0.5s)
    t1 = time.monotonic()

    elapsed = t1 - t0
    assert 0.4 <= elapsed <= 0.8


@pytest.mark.asyncio
async def test_rate_limiter_jitter_application():
    limiter = TokenBucketRateLimiter(rate_limit_rpm=600, burst_capacity=10, jitter_range=(0.1, 0.15))
    
    t0 = time.monotonic()
    await limiter.acquire()
    t1 = time.monotonic()

    elapsed = t1 - t0
    assert 0.09 <= elapsed <= 0.25
