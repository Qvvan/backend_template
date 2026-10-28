from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.repository.redis.repository import RedisRepository


@pytest.fixture
def mock_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def repo(mock_client: MagicMock) -> RedisRepository:
    return RedisRepository(client=mock_client)


# ── get ──────────────────────────────────────────────────────────────────────


async def test_get_returns_value(repo: RedisRepository, mock_client: MagicMock) -> None:
    mock_client.get = AsyncMock(return_value="value")
    assert await repo.get("key") == "value"
    mock_client.get.assert_called_once_with("key")


async def test_get_returns_none_when_missing(repo: RedisRepository, mock_client: MagicMock) -> None:
    mock_client.get = AsyncMock(return_value=None)
    assert await repo.get("missing") is None


# ── set ──────────────────────────────────────────────────────────────────────


async def test_set_without_expire_calls_set(repo: RedisRepository, mock_client: MagicMock) -> None:
    mock_client.set = AsyncMock(return_value=True)
    assert await repo.set("key", "value") is True
    mock_client.set.assert_called_once_with("key", "value")


async def test_set_with_expire_calls_setex(repo: RedisRepository, mock_client: MagicMock) -> None:
    mock_client.setex = AsyncMock(return_value=True)
    assert await repo.set("key", "value", expire=60) is True
    mock_client.setex.assert_called_once_with("key", 60, "value")


# ── delete ───────────────────────────────────────────────────────────────────


async def test_delete_existing_key_returns_true(repo: RedisRepository, mock_client: MagicMock) -> None:
    mock_client.delete = AsyncMock(return_value=1)
    assert await repo.delete("key") is True


async def test_delete_missing_key_returns_false(repo: RedisRepository, mock_client: MagicMock) -> None:
    mock_client.delete = AsyncMock(return_value=0)
    assert await repo.delete("missing") is False


# ── exists ───────────────────────────────────────────────────────────────────


async def test_exists_returns_true_when_key_present(repo: RedisRepository, mock_client: MagicMock) -> None:
    mock_client.exists = AsyncMock(return_value=1)
    assert await repo.exists("key") is True


async def test_exists_returns_false_when_key_absent(repo: RedisRepository, mock_client: MagicMock) -> None:
    mock_client.exists = AsyncMock(return_value=0)
    assert await repo.exists("missing") is False


# ── expire / ttl ──────────────────────────────────────────────────────────────


async def test_expire_delegates_to_client(repo: RedisRepository, mock_client: MagicMock) -> None:
    mock_client.expire = AsyncMock(return_value=True)
    assert await repo.expire("key", 120) is True
    mock_client.expire.assert_called_once_with("key", 120)


async def test_ttl_returns_remaining_seconds(repo: RedisRepository, mock_client: MagicMock) -> None:
    mock_client.ttl = AsyncMock(return_value=55)
    assert await repo.ttl("key") == 55


# ── get_many ──────────────────────────────────────────────────────────────────


async def test_get_many_returns_keyed_mapping(repo: RedisRepository, mock_client: MagicMock) -> None:
    mock_client.mget = AsyncMock(return_value=["v1", None])
    result = await repo.get_many(["k1", "k2"])
    assert result == {"k1": "v1", "k2": None}
    mock_client.mget.assert_called_once_with(["k1", "k2"])


async def test_get_many_empty_input_returns_empty_dict(repo: RedisRepository, mock_client: MagicMock) -> None:
    result = await repo.get_many([])
    assert result == {}
    mock_client.mget.assert_not_called()


# ── set_many ──────────────────────────────────────────────────────────────────


async def test_set_many_without_expire_calls_mset(repo: RedisRepository, mock_client: MagicMock) -> None:
    mock_client.mset = AsyncMock()
    assert await repo.set_many({"k1": "v1", "k2": "v2"}) is True
    mock_client.mset.assert_called_once_with({"k1": "v1", "k2": "v2"})


async def test_set_many_empty_mapping_returns_true_without_io(repo: RedisRepository, mock_client: MagicMock) -> None:
    mock_client.mset = AsyncMock()
    assert await repo.set_many({}) is True
    mock_client.mset.assert_not_called()


def _make_pipeline_cm(results: list[Any]) -> MagicMock:
    pipe = MagicMock()
    pipe.setex = MagicMock()
    pipe.execute = AsyncMock(return_value=results)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=pipe)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


async def test_set_many_with_expire_uses_pipeline(repo: RedisRepository, mock_client: MagicMock) -> None:
    cm = _make_pipeline_cm([True, True])
    mock_client.pipeline = MagicMock(return_value=cm)

    result = await repo.set_many({"k1": "v1", "k2": "v2"}, expire=30)

    assert result is True
    pipe = cm.__aenter__.return_value
    assert pipe.setex.call_count == 2


async def test_set_many_with_expire_returns_false_when_pipeline_has_errors(
    repo: RedisRepository, mock_client: MagicMock
) -> None:
    cm = _make_pipeline_cm([True, Exception("redis error")])
    mock_client.pipeline = MagicMock(return_value=cm)

    assert await repo.set_many({"k1": "v1", "k2": "v2"}, expire=30) is False


# ── delete_many ───────────────────────────────────────────────────────────────


async def test_delete_many_returns_deleted_count(repo: RedisRepository, mock_client: MagicMock) -> None:
    mock_client.delete = AsyncMock(return_value=2)
    assert await repo.delete_many(["k1", "k2"]) == 2
    mock_client.delete.assert_called_once_with("k1", "k2")


async def test_delete_many_empty_input_returns_zero_without_io(repo: RedisRepository, mock_client: MagicMock) -> None:
    mock_client.delete = AsyncMock()
    assert await repo.delete_many([]) == 0
    mock_client.delete.assert_not_called()


# ── increment / decrement ─────────────────────────────────────────────────────


async def test_increment_delegates_to_incrby(repo: RedisRepository, mock_client: MagicMock) -> None:
    mock_client.incrby = AsyncMock(return_value=5)
    assert await repo.increment("counter", 3) == 5
    mock_client.incrby.assert_called_once_with("counter", 3)


async def test_decrement_delegates_to_decrby(repo: RedisRepository, mock_client: MagicMock) -> None:
    mock_client.decrby = AsyncMock(return_value=2)
    assert await repo.decrement("counter", 3) == 2
    mock_client.decrby.assert_called_once_with("counter", 3)


# ── scan_keys ─────────────────────────────────────────────────────────────────


async def test_scan_keys_collects_scan_iter_results(repo: RedisRepository, mock_client: MagicMock) -> None:
    async def _scan(*args: Any, **kwargs: Any) -> Any:
        for k in ["key1", "key2", "key3"]:
            yield k

    mock_client.scan_iter = MagicMock(return_value=_scan())
    result = await repo.scan_keys("key*")
    assert result == ["key1", "key2", "key3"]
    mock_client.scan_iter.assert_called_once_with("key*")


async def test_scan_keys_default_pattern_is_wildcard(repo: RedisRepository, mock_client: MagicMock) -> None:
    async def _scan(*args: Any, **kwargs: Any) -> Any:
        yield "a"

    mock_client.scan_iter = MagicMock(return_value=_scan())
    await repo.scan_keys()
    mock_client.scan_iter.assert_called_once_with("*")
