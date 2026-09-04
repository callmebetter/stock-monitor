"""30s TTL memory cache with last-good (stale) fallback (PRD §7.2 / §10).

Only manual refresh triggers fetches; the cache simply avoids hammering
upstream when several tabs refresh at once.
"""
import logging
import threading
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)

try:
    from cachetools import TTLCache as _TTLCache
except ImportError:  # pragma: no cover - fallback when dep not installed
    _TTLCache = None


class _SimpleTTL:
    def __init__(self, maxsize: int = 32, ttl: int = 30):
        self.maxsize = maxsize
        self.ttl = ttl
        self._store: dict[str, tuple[float, Any]] = {}

    def __contains__(self, key: str) -> bool:
        if key not in self._store:
            return False
        exp, _ = self._store[key]
        if exp < time.time():
            del self._store[key]
            return False
        return True

    def __getitem__(self, key: str) -> Any:
        return self._store[key][1]

    def __setitem__(self, key: str, value: Any) -> None:
        if len(self._store) >= self.maxsize:
            oldest = min(self._store, key=lambda k: self._store[k][0])
            del self._store[oldest]
        self._store[key] = (time.time() + self.ttl, value)

    def clear(self) -> None:
        self._store.clear()


class GoldCache:
    def __init__(self, maxsize: int = 32, ttl: int = 30):
        self._lock = threading.Lock()
        if _TTLCache is not None:
            self._cache = _TTLCache(maxsize=maxsize, ttl=ttl)
        else:
            self._cache = _SimpleTTL(maxsize=maxsize, ttl=ttl)
        self._last_good: dict[str, Any] = {}

    def get_or_fetch(self, key: str, fetcher: Callable[[], Any]) -> tuple[Any, bool]:
        """Return (data, stale). stale=True means last-good fallback was served."""
        with self._lock:
            if key in self._cache:
                return self._cache[key], False
        try:
            data = fetcher()
        except Exception as e:
            logger.warning("gold cache fetch failed for %s: %s", key, e)
            with self._lock:
                if key in self._last_good:
                    return self._last_good[key], True
            raise
        with self._lock:
            self._cache[key] = data
            self._last_good[key] = data
        return data, False

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


_cache = GoldCache(ttl=30)


def get_cache() -> GoldCache:
    return _cache
