"""
Redis slot gate — atomic Lua scripts for hold/release.
Keys: slot:{slot_id}  value = available_capacity (integer)

hold_slot  → 1  (held), 0 (fully booked), -1 (cache miss → caller must DB fallback)
release_slot → always succeeds (idempotent)
warm_slot  → sets key if not present
"""
import redis.asyncio as aioredis
from fast_api_services.config import get_settings

# Lua: decrement if key exists and value > 0
_HOLD_SCRIPT = """
local key = KEYS[1]
local val = redis.call('GET', key)
if val == false then
    return -1
end
local n = tonumber(val)
if n <= 0 then
    return 0
end
redis.call('DECRBY', key, 1)
return 1
"""

# Lua: increment (release), cap at original capacity read from a separate key
_RELEASE_SCRIPT = """
local key = KEYS[1]
local cap_key = KEYS[2]
local cap = tonumber(redis.call('GET', cap_key))
if cap == nil then
    redis.call('INCR', key)
    return 1
end
local cur = tonumber(redis.call('GET', key) or '0')
if cur < cap then
    redis.call('INCR', key)
end
return 1
"""

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
    """Async-compatible alias for get_redis() — used by agent/memory.py."""
    return get_redis()


def _slot_key(slot_id: int) -> str:
    return f"slot:{slot_id}"


def _cap_key(slot_id: int) -> str:
    return f"slot:{slot_id}:cap"


async def warm_slot(slot_id: int, available: int, capacity: int) -> None:
    """Warm cache for a single slot. Safe to call multiple times (SET NX)."""
    r = get_redis()
    pipe = r.pipeline()
    pipe.set(_slot_key(slot_id), available, nx=True)
    pipe.set(_cap_key(slot_id), capacity, nx=True)
    await pipe.execute()


async def hold_slot(slot_id: int) -> int:
    """
    Atomically decrement slot counter.
    Returns: 1=held, 0=fully booked, -1=cache miss
    """
    r = get_redis()
    result = await r.eval(_HOLD_SCRIPT, 1, _slot_key(slot_id))  # type: ignore[arg-type]
    return int(result)


async def release_slot(slot_id: int) -> None:
    """Release a previously held slot (rollback on booking failure)."""
    r = get_redis()
    await r.eval(_RELEASE_SCRIPT, 2, _slot_key(slot_id), _cap_key(slot_id))  # type: ignore[arg-type]


async def get_slot_availability(slot_id: int) -> int | None:
    """Return current available count from cache, or None if not warmed."""
    r = get_redis()
    val = await r.get(_slot_key(slot_id))
    return int(val) if val is not None else None
