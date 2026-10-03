"""
Redis client singleton + MOCK slot-hold gate.

Used by:
  - routers/agent.py: get_redis_client() → conversation memory (session:{user_id}, TTL 30 min)
  - main.py lifespan: close connection on shutdown

Slot availability is read directly from the DB (centers_examslot.reserved_count).
Concurrency on writes is handled by Django's select_for_update() inside a transaction.

``hold_slot`` / ``release_slot`` are a lightweight TTL reservation used while a
user is still deciding (multi-turn AI confirmation), so the seat is not taken by
someone else before the transactional Django write happens.
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


# ── slot hold (TTL reservation) ───────────────────────────────────────────────


def _hold_key(slot_id: int) -> str:
    return f"hold:{slot_id}"


async def hold_slot(
    redis: aioredis.Redis,
    slot_id: int,
    user_id: int,
    ttl_seconds: int | None = None,
) -> bool:
    """
    Try to reserve *slot_id* for *user_id*.

    Returns True if the caller owns the hold (freshly acquired or already held
    by the same user), False if someone else holds it.
    """
    if ttl_seconds is None:
        ttl_seconds = get_settings().slot_hold_ttl_seconds
    key = _hold_key(slot_id)
    acquired = await redis.set(key, str(user_id), nx=True, ex=ttl_seconds)
    if acquired:
        return True
    current = await redis.get(key)
    return current == str(user_id)


async def release_slot(redis: aioredis.Redis, slot_id: int, user_id: int) -> bool:
    """Release a hold owned by *user_id*. Returns True if released."""
    key = _hold_key(slot_id)
    current = await redis.get(key)
    if current == str(user_id):
        await redis.delete(key)
        return True
    return False


async def get_hold(redis: aioredis.Redis, slot_id: int) -> str | None:
    """Return the user_id currently holding *slot_id*, or None."""
    return await redis.get(_hold_key(slot_id))

