from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional

from app.config import settings

import structlog

log = structlog.get_logger()

_redis_client = None
_redis_checked = False


def _get_redis():
    """
    Return the Redis client, or None if Redis is not configured/available.

    Checks once on first call — if Redis is unavailable, returns None
    for all subsequent calls without re-checking.
    """
    global _redis_client, _redis_checked

    if _redis_checked:
        return _redis_client

    _redis_checked = True

    if not settings.REDIS_URL:
        log.info("redis_disabled", reason="REDIS_URL not configured")
        return None

    try:
        import redis

        _redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=2,
            socket_connect_timeout=2,
        )
        # Test connection
        _redis_client.ping()
        log.info("redis_connected", url=settings.REDIS_URL[:30])
        return _redis_client

    except Exception as e:
        log.warning("redis_connection_failed", error=str(e))
        _redis_client = None
        return None


def _build_cache_key(query: str, user: Dict) -> str:
    """
    Build a deterministic cache key from query + RBAC context.

    Key components:
    - query text
    - user department, role_level, clearance_level
    - embedding model name (invalidates on model switch)
    - RBAC version (invalidates on RBAC rule changes)
    """
    # Normalize query: lowercase + strip whitespace
    # Catches "What is PTO?" vs "what is PTO?" → same cache key
    query_normalized = query.strip().lower()
    raw = (
        f"{query_normalized}|"
        f"{user.get('department', '')}|"
        f"{user.get('role_level', '')}|"
        f"{user.get('clearance_level', '')}|"
        f"{settings.EMBEDDING_MODEL}|"
        f"{settings.RBAC_VERSION}"
    )
    return f"sentinel:query:{hashlib.sha256(raw.encode()).hexdigest()}"


def get_cached_response(query: str, user: Dict) -> Optional[Dict]:
    """
    Check if a cached response exists for this query + RBAC context.

    Returns the cached response dict, or None if not found/unavailable.
    """
    client = _get_redis()
    if client is None:
        return None

    try:
        key = _build_cache_key(query, user)
        cached = client.get(key)
        if cached:
            log.info("cache_hit", query=query[:80])
            return json.loads(cached)
        return None

    except Exception as e:
        log.warning("cache_get_failed", error=str(e))
        return None


def cache_response(
    query: str,
    user: Dict,
    response: Any,
    ttl: int = 3600,
) -> None:
    """
    Cache a response for this query + RBAC context.

    Args:
        query: The user's query text.
        user: User dict with RBAC fields.
        response: The response dict to cache.
        ttl: Time-to-live in seconds (default: 1 hour).
    """
    client = _get_redis()
    if client is None:
        return

    try:
        key = _build_cache_key(query, user)
        client.setex(key, ttl, json.dumps(response))
        log.info("cache_set", query=query[:80], ttl=ttl)

    except Exception as e:
        log.warning("cache_set_failed", error=str(e))
