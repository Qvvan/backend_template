from __future__ import annotations

from fastapi.testclient import TestClient

from tests.fakes.cache import InMemoryCacheRepository
from tests.fakes.uow import FakeUnitOfWork


async def test_in_memory_cache_behaves_like_redis_repository() -> None:
    cache = InMemoryCacheRepository()
    await cache.set("a:1", "1", expire=10)
    await cache.set("b:1", "x")

    assert await cache.get("a:1") == "1"
    assert await cache.ttl("a:1") == 10
    assert await cache.ttl("b:1") == -1
    assert await cache.ttl("missing") == -2
    assert await cache.increment("a:1", 4) == 5
    assert await cache.scan_keys("a:*") == ["a:1"]
    assert await cache.delete_many(["a:1", "b:1", "missing"]) == 2


async def test_fake_uow_counts_commits_and_rollbacks() -> None:
    uow = FakeUnitOfWork()
    async with uow.begin():
        pass
    try:
        async with uow.begin():
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert (uow.commits, uow.rollbacks) == (1, 1)


def test_api_client_fixture_serves_the_real_app(api_client: TestClient) -> None:
    assert api_client.get("/livez").json() == {"status": "ok"}
    assert api_client.get("/no-such-route").json()["code"] == "NOT_FOUND"
