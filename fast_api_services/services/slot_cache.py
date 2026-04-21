"""
Redis client singleton.

Used by:
  - routers/agent.py: get_redis_client() → conversation memory (session:{user_id}, TTL 30 min)
  - main.py lifespan: close connection on shutdown

Slot availability is read directly from the DB (centers_examslot.reserved_count).
Concurrency on writes is handled by Django's select_for_update() inside a transaction.
"""
import redis.asyncio as aioredis
from fast_api_services.config import get_settings

_redis_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = aioredis.from_url(
            settings.redis_url, encoding="utf-8", decode_responses=True
        )
    return _redis_client


async def get_redis_client() -> aioredis.Redis:
    """Async-compatible alias used by routers."""
    return get_redis()
