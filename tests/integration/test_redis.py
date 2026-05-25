from __future__ import annotations

import asyncio

from src.infrastructure.repository.redis.client import RedisDB
from src.infrastructure.repository.redis.repository import RedisRepository

_KEY = "test:redis:"


async def test_health_check(redis_db: RedisDB) -> None:
    assert await redis_db.health_check() is True


async def test_set_and_get(redis_repo: RedisRepository) -> None:
    key = f"{_KEY}set_get"
    await redis_repo.set(key, "hello")
    assert await redis_repo.get(key) == "hello"
    await redis_repo.delete(key)


async def test_get_missing_key_returns_none(redis_repo: RedisRepository) -> None:
    assert await redis_repo.get(f"{_KEY}missing_xyz_abc") is None


async def test_set_with_expire_and_ttl(redis_repo: RedisRepository) -> None:
    key = f"{_KEY}ttl"
    await redis_repo.set(key, "temp", expire=100)
    ttl = await redis_repo.ttl(key)
    assert 0 < ttl <= 100
    await redis_repo.delete(key)


async def test_key_expires_after_ttl(redis_repo: RedisRepository) -> None:
    key = f"{_KEY}expire"
    await redis_repo.set(key, "gone", expire=1)
    assert await redis_repo.exists(key) is True
    await asyncio.sleep(1.1)
    assert await redis_repo.exists(key) is False


async def test_delete_existing_key_returns_true(redis_repo: RedisRepository) -> None:
    key = f"{_KEY}delete"
    await redis_repo.set(key, "v")
    assert await redis_repo.delete(key) is True


async def test_delete_missing_key_returns_false(redis_repo: RedisRepository) -> None:
    assert await redis_repo.delete(f"{_KEY}no_such_key_xyz") is False


async def test_exists_true_after_set(redis_repo: RedisRepository) -> None:
    key = f"{_KEY}exists"
    await redis_repo.set(key, "y")
    assert await redis_repo.exists(key) is True
    await redis_repo.delete(key)


async def test_exists_false_for_missing_key(redis_repo: RedisRepository) -> None:
    assert await redis_repo.exists(f"{_KEY}nope_xyz_abc") is False


async def test_expire_updates_ttl(redis_repo: RedisRepository) -> None:
    key = f"{_KEY}re_expire"
    await redis_repo.set(key, "v")
    await redis_repo.expire(key, 200)
    ttl = await redis_repo.ttl(key)
    assert ttl > 100
    await redis_repo.delete(key)


async def test_get_many(redis_repo: RedisRepository) -> None:
    keys = [f"{_KEY}many_{i}" for i in range(3)]
    for k in keys:
        await redis_repo.set(k, k)
    result = await redis_repo.get_many(keys)
    assert result == {k: k for k in keys}
    await redis_repo.delete_many(keys)


async def test_get_many_empty_input(redis_repo: RedisRepository) -> None:
    assert await redis_repo.get_many([]) == {}


async def test_set_many_without_expire(redis_repo: RedisRepository) -> None:
    mapping = {f"{_KEY}sm_{i}": f"v{i}" for i in range(3)}
    assert await redis_repo.set_many(mapping) is True
    for k, v in mapping.items():
        assert await redis_repo.get(k) == v
    await redis_repo.delete_many(list(mapping.keys()))


async def test_set_many_with_expire(redis_repo: RedisRepository) -> None:
    mapping = {f"{_KEY}sme_{i}": f"v{i}" for i in range(2)}
    await redis_repo.set_many(mapping, expire=1)
    await asyncio.sleep(1.1)
    for k in mapping:
        assert await redis_repo.exists(k) is False


async def test_set_many_empty_input(redis_repo: RedisRepository) -> None:
    assert await redis_repo.set_many({}) is True


async def test_delete_many(redis_repo: RedisRepository) -> None:
    keys = [f"{_KEY}dm_{i}" for i in range(3)]
    for k in keys:
        await redis_repo.set(k, "v")
    assert await redis_repo.delete_many(keys) == 3


async def test_delete_many_empty_input(redis_repo: RedisRepository) -> None:
    assert await redis_repo.delete_many([]) == 0


async def test_increment_and_decrement(redis_repo: RedisRepository) -> None:
    key = f"{_KEY}counter"
    await redis_repo.set(key, "0")
    assert await redis_repo.increment(key, 5) == 5
    assert await redis_repo.decrement(key, 2) == 3
    await redis_repo.delete(key)


async def test_keys_by_pattern(redis_repo: RedisRepository) -> None:
    keys = [f"{_KEY}scan_{i}" for i in range(3)]
    for k in keys:
        await redis_repo.set(k, "v")
    found = await redis_repo.keys(f"{_KEY}scan_*")
    assert set(found) == set(keys)
    await redis_repo.delete_many(keys)


async def test_flush_db_clears_all_keys(redis_repo: RedisRepository) -> None:
    keys = [f"{_KEY}flush_{i}" for i in range(3)]
    for k in keys:
        await redis_repo.set(k, "v")
    assert await redis_repo.flush_db() is True
    for k in keys:
        assert await redis_repo.exists(k) is False
