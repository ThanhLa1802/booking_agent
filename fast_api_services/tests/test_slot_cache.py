"""Unit tests for Redis slot gate (fakeredis)."""
import pytest
import pytest_asyncio
import fakeredis.aioredis as fake_aioredis
from unittest.mock import patch


@pytest_asyncio.fixture
async def redis():
    r = fake_aioredis.FakeRedis(decode_responses=True)
    yield r
    await r.aclose()


class TestSlotCache:
    @pytest.mark.asyncio
    async def test_warm_and_hold(self, redis):
        with patch("fast_api_services.services.slot_cache._redis_client", redis):
            from fast_api_services.services.slot_cache import warm_slot, hold_slot

            await warm_slot(slot_id=1, available=3, capacity=3)
            result = await hold_slot(slot_id=1)
        assert result == 1  # held

    @pytest.mark.asyncio
    async def test_hold_decrements_counter(self, redis):
        with patch("fast_api_services.services.slot_cache._redis_client", redis):
            from fast_api_services.services.slot_cache import warm_slot, hold_slot, get_slot_availability

            await warm_slot(slot_id=2, available=2, capacity=2)
            await hold_slot(slot_id=2)
            available = await get_slot_availability(slot_id=2)
        assert available == 1

    @pytest.mark.asyncio
    async def test_hold_returns_zero_when_full(self, redis):
        with patch("fast_api_services.services.slot_cache._redis_client", redis):
            from fast_api_services.services.slot_cache import warm_slot, hold_slot

            await warm_slot(slot_id=3, available=1, capacity=1)
            await hold_slot(slot_id=3)  # first hold: available → 0
            result = await hold_slot(slot_id=3)  # second hold: fully booked
        assert result == 0

    @pytest.mark.asyncio
    async def test_hold_returns_minus1_on_cache_miss(self, redis):
        with patch("fast_api_services.services.slot_cache._redis_client", redis):
            from fast_api_services.services.slot_cache import hold_slot

            result = await hold_slot(slot_id=999)  # never warmed
        assert result == -1

    @pytest.mark.asyncio
    async def test_release_increments_counter(self, redis):
        with patch("fast_api_services.services.slot_cache._redis_client", redis):
            from fast_api_services.services.slot_cache import (
                warm_slot, hold_slot, release_slot, get_slot_availability
            )

            await warm_slot(slot_id=4, available=2, capacity=2)
            await hold_slot(slot_id=4)         # available → 1
            await release_slot(slot_id=4)       # available → 2
            available = await get_slot_availability(slot_id=4)
        assert available == 2

    @pytest.mark.asyncio
    async def test_release_does_not_exceed_capacity(self, redis):
        with patch("fast_api_services.services.slot_cache._redis_client", redis):
            from fast_api_services.services.slot_cache import (
                warm_slot, release_slot, get_slot_availability
            )

            await warm_slot(slot_id=5, available=2, capacity=2)
            await release_slot(slot_id=5)       # already at max — should not exceed
            available = await get_slot_availability(slot_id=5)
        assert available == 2
