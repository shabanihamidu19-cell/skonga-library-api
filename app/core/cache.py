"""
SKONGA Library API — Cache Layer
==================================
Redis-backed caching with a transparent fallback: if REDIS_URL is not
set (or Redis is unreachable), every cache call is a no-op and the
service continues working — just without caching. This means you can
deploy Phase 1 without Redis and add it later with zero code changes.
"""
import json
import logging
from typing import Any, Optional

from app.config import settings

_log = logging.getLogger("skonga_library.cache")
_redis_client = None


def _get_client():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    if not settings.REDIS_URL:
        return None
    try:
        import redis  # type: ignore

        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        _redis_client.ping()
        _log.info("Redis connection established")
    except Exception as exc:
        _log.warning(f"Redis unavailable — caching disabled: {exc}")
        _redis_client = None
    return _redis_client


def cache_get(key: str) -> Optional[Any]:
    client = _get_client()
    if client is None:
        return None
    try:
        raw = client.get(key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            _log.warning("Cache key %s contained non-JSON data", key)
            return None
    except Exception as exc:
        _log.debug("Redis get failed for key %s: %s", key, exc)
        return None


def cache_set(key: str, value: Any, ttl: int) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        client.setex(key, ttl, json.dumps(value, ensure_ascii=False))
    except Exception as exc:
        _log.debug("Redis set failed for key %s: %s", key, exc)
        pass  # cache failures are silent — data still served from DB


def cache_delete(key: str) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        client.delete(key)
    except Exception as exc:
        _log.debug("Redis delete failed for key %s: %s", key, exc)
        pass
