"""
Caching utilities — two unrelated patterns share this file:

1. Distributed locks (Redis-backed via Django's cache framework).
   Used to prevent two Celery workers from running the same collector
   for the same practice at the same time.

2. Two-level knowledge cache (in-process dict, no Redis hit).
   Used for slow-changing data (scoring weights, ICP config) that a
   single Celery worker should re-fetch at most once per N seconds.
"""

import time
from contextlib import contextmanager
from typing import Any, Callable

from django.core.cache import cache


# ---------- Distributed locks ----------

def acquire_lock(lock_key: str, timeout: int = 300) -> bool:
    """Try to acquire a distributed lock. Returns True if acquired, False if already held.

    `cache.add` is atomic: it sets the key ONLY if the key doesn't already exist.
    This makes it safe across multiple processes — two workers calling acquire_lock
    on the same key at the same time will see exactly one True and one False.
    """
    return cache.add(lock_key, 'locked', timeout=timeout)


def release_lock(lock_key: str) -> None:
    """Release a previously acquired lock."""
    cache.delete(lock_key)


@contextmanager
def distributed_lock(lock_key: str, timeout: int = 300):
    """Context manager wrapping acquire/release in try/finally.

    Yields True if the lock was acquired, False if another worker holds it.
    Caller decides what to do when the lock is unavailable.

    Example:
        with distributed_lock(f'sova:lock:google_places:{npi}') as got:
            if not got:
                logger.info("Another worker is already collecting this practice")
                return
            # ... do work ...
    """
    acquired = acquire_lock(lock_key, timeout=timeout)
    try:
        yield acquired
    finally:
        if acquired:
            release_lock(lock_key)


# ---------- Two-level knowledge cache ----------

# Module-level dict — one copy per Celery worker process.
# Keys: arbitrary strings. Values: (value, expires_at_unix_timestamp).
_KNOWLEDGE_CACHE: dict[str, tuple[Any, float]] = {}


def get_or_fill_cache(key: str, fetch_fn: Callable[[], Any], ttl_seconds: int = 900) -> Any:
    """Return a cached value if fresh, otherwise call `fetch_fn` and cache its result.

    Avoids hitting Redis/Postgres for data that won't change within a single
    Celery worker's lifetime (default 15-minute freshness).

    Example:
        weights = get_or_fill_cache('scoring_weights', load_weights_from_db)
    """
    now = time.time()
    cached = _KNOWLEDGE_CACHE.get(key)
    if cached is not None:
        value, expires_at = cached
        if expires_at > now:
            return value

    value = fetch_fn()
    _KNOWLEDGE_CACHE[key] = (value, now + ttl_seconds)
    return value
